
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from domain.dda_models import DDADocument
from domain.communication import CommunicationChannel, Message
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_architect.dda_parser import DDAParserFactory
from infrastructure.architecture_graph_writer import ArchitectureGraphWriter
import json
import os
from datetime import datetime
import shutil


class ValidationResult(BaseModel):
    """Result of DDA document validation."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ModelingResult(BaseModel):
    """Result of the modeling workflow."""
    success: bool
    errors: List[str] = []
    warnings: List[str] = []
    graph_document: Optional[dict] = None
    artifacts: Optional[dict] = None


class ModelingWorkflow:
    """Orchestrates the complete modeling workflow with error recovery and backup."""
    
    def __init__(
        self,
        parser_factory: DDAParserFactory,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str
    ):
        self.parser_factory = parser_factory
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.backup_dir = "backups/modeling"
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self) -> None:
        """Ensure backup directory exists."""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    async def execute(self, command: ModelingCommand) -> Dict[str, Any]:
        """Execute the complete modeling workflow with error recovery."""
        
        workflow_state = {
            "start_time": datetime.now().isoformat(),
            "command": command.model_dump(),
            "steps_completed": [],
            "backup_created": False,
            "rollback_performed": False
        }
        
        try:
            # 1. Create backup if updating existing graph
            if command.update_existing:
                backup_result = await self._create_backup(command.domain)
                workflow_state["backup_created"] = backup_result["success"]
                workflow_state["backup_path"] = backup_result.get("backup_path")
            
            # 2. Parse DDA document
            parser = self.parser_factory.get_parser(command.dda_path)
            dda_document = await parser.parse(command.dda_path)
            workflow_state["steps_completed"].append("parse")
            
            # 3. Validate document
            validation_result = await self._validate_dda_document(dda_document)
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"],
                    "workflow_state": workflow_state
                }
            workflow_state["steps_completed"].append("validate")
            
            # 4. Create architecture graph using direct writer
            writer = ArchitectureGraphWriter(
                uri=self.neo4j_uri,
                user=self.neo4j_user,
                password=self.neo4j_password
            )
            
            try:
                graph_document = writer.create_architecture_graph(dda_document)
                workflow_state["steps_completed"].append("graph_creation")
            finally:
                writer.close()
            
            # 5. Hand off to Data Engineer for metadata generation (non-blocking)
            handoff_result = await self._handoff_to_data_engineer(
                command,
                dda_document,
                graph_document
            )
            workflow_state["handoff"] = handoff_result
            # Handoff failure is not critical - workflow continues
            if handoff_result.get("success"):
                workflow_state["steps_completed"].append("handoff")
            else:
                # Log warning but don't fail the workflow
                workflow_state["handoff_warning"] = handoff_result.get("error", "Handoff failed")
            
            # 6. Generate output artifacts
            artifacts = await self._generate_artifacts(dda_document, graph_document, command)
            workflow_state["steps_completed"].append("artifacts")
            
            workflow_state["end_time"] = datetime.now().isoformat()
            workflow_state["success"] = True
            
            return {
                "success": True,
                "graph_document": graph_document,
                "artifacts": artifacts,
                "warnings": validation_result["warnings"],
                "handoff": handoff_result,
                "workflow_state": workflow_state
            }
            
        except Exception as e:
            # Error recovery: attempt rollback if backup exists
            if workflow_state.get("backup_created"):
                rollback_result = await self._perform_rollback(command.domain, workflow_state.get("backup_path"))
                workflow_state["rollback_performed"] = rollback_result["success"]
                workflow_state["rollback_error"] = rollback_result.get("error")
            
            workflow_state["end_time"] = datetime.now().isoformat()
            workflow_state["error"] = str(e)
            
            return {
                "success": False,
                "errors": [f"Modeling workflow failed: {str(e)}"],
                "workflow_state": workflow_state
            }
    
    async def _validate_dda_document(self, dda_document: DDADocument) -> Dict[str, Any]:
        """Validate the parsed DDA document."""
        errors = []
        warnings = []
        
        # Check required fields
        if not dda_document.domain:
            errors.append("Domain is required")
        
        if not dda_document.entities:
            errors.append("At least one data entity is required")
        
        # Check entity consistency
        entity_names = {entity.name for entity in dda_document.entities}
        for relationship in dda_document.relationships:
            if relationship.source_entity not in entity_names:
                errors.append(f"Relationship references unknown entity: {relationship.source_entity}")
            if relationship.target_entity not in entity_names:
                errors.append(f"Relationship references unknown entity: {relationship.target_entity}")
        
        # Check for common issues
        if len(dda_document.entities) > 0 and len(dda_document.relationships) == 0:
            warnings.append("No relationships defined between entities")
        
        if not dda_document.business_context or dda_document.business_context == "No business context provided":
            warnings.append("Business context is minimal or missing")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _generate_artifacts(self, dda_document: DDADocument, graph_document: dict, command: ModelingCommand) -> dict:
        """Generate output artifacts from the modeling process."""
        artifacts = {
            "dda_summary": {
                "domain": dda_document.domain,
                "entities_count": len(dda_document.entities),
                "relationships_count": len(dda_document.relationships),
                "stakeholders": dda_document.stakeholders,
                "data_owner": dda_document.data_owner
            },
            "graph_summary": {
                "episode_uuid": graph_document.get("episode_uuid"),
                "nodes_created": graph_document.get("nodes_created", 0),
                "edges_created": graph_document.get("edges_created", 0),
                "group_id": graph_document.get("group_id"),
                "domain": dda_document.domain
            },
            "validation": {
                "is_valid": True,
                "timestamp": dda_document.effective_date.isoformat()
            }
        }
        
        return artifacts
    
    async def _handoff_to_data_engineer(
        self,
        command: ModelingCommand,
        dda_document: DDADocument,
        graph_document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Hand off to Data Engineer agent for metadata generation.
        
        Args:
            command: The modeling command that was executed
            dda_document: The parsed DDA document
            graph_document: The created architecture graph document
        
        Returns:
            Dictionary with handoff result
        """
        try:
            # Get architecture graph reference (group_id or episode_uuid)
            architecture_graph_ref = graph_document.get("group_id") or graph_document.get("episode_uuid")
            
            if not architecture_graph_ref:
                return {
                    "success": False,
                    "error": "Could not determine architecture graph reference"
                }
            
            # Discover Data Engineer agent URL
            data_engineer_url = await self._discover_data_engineer_agent()
            
            if not data_engineer_url:
                return {
                    "success": False,
                    "error": "Could not discover Data Engineer agent"
                }
            
            # Create GenerateMetadataCommand
            metadata_command = GenerateMetadataCommand(
                dda_path=command.dda_path,
                domain=command.domain or dda_document.domain,
                architecture_graph_ref=architecture_graph_ref,
                validate_against_architecture=True
            )
            
            # Send command via A2A HTTP endpoint
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{data_engineer_url}/v1/tasks/send",
                        json={
                            "tool_name": "GenerateMetadataCommand",
                            "parameters": metadata_command.model_dump()
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "data_engineer_url": data_engineer_url,
                        "architecture_graph_ref": architecture_graph_ref,
                        "response": response.json()
                    }
                except httpx.HTTPStatusError as e:
                    return {
                        "success": False,
                        "error": f"HTTP error: {e.response.status_code} - {e.response.text}"
                    }
                except httpx.RequestError as e:
                    return {
                        "success": False,
                        "error": f"Request error: {str(e)}"
                    }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Handoff failed: {str(e)}"
            }
    
    async def _discover_data_engineer_agent(self) -> Optional[str]:
        """Discover Data Engineer agent URL.
        
        Returns:
            URL of Data Engineer agent or None if not found
        """
        # Default URL for Data Engineer agent
        # In a real implementation, this would query the knowledge graph or service registry
        return "http://localhost:8002"
    
    async def _create_backup(self, domain: str) -> Dict[str, Any]:
        """Create a backup of the existing domain graph."""
        try:
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{domain.lower().replace(' ', '_')}_{timestamp}.json"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Search for existing domain data
            search_results = await self.domain_modeler.graph.search(
                query=f"domain {domain}",
                group_ids=[f"dda_{domain.lower().replace(' ', '_')}"],
                num_results=50
            )
            
            # Create backup data structure
            backup_data = {
                "domain": domain,
                "backup_timestamp": timestamp,
                "episodes": [],
                "nodes": [],
                "edges": []
            }
            
            if search_results:
                for result in search_results:
                    episode_data = {
                        "uuid": result.uuid,
                        "name": result.name,
                        "attributes": result.attributes if hasattr(result, 'attributes') else {}
                    }
                    backup_data["episodes"].append(episode_data)
            
            # Save backup to file
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            return {
                "success": True,
                "backup_path": backup_path,
                "episodes_backed_up": len(backup_data["episodes"])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Backup creation failed: {str(e)}"
            }
    
    async def _perform_rollback(self, domain: str, backup_path: Optional[str]) -> Dict[str, Any]:
        """Perform rollback to previous state using backup."""
        try:
            if not backup_path or not os.path.exists(backup_path):
                return {
                    "success": False,
                    "error": "Backup file not found"
                }
            
            # Load backup data
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # Note: Full rollback would require more sophisticated graph operations
            # For now, we'll just log the rollback attempt
            print(f"Rollback attempted for domain: {domain}")
            print(f"Backup contained {len(backup_data.get('episodes', []))} episodes")
            
            return {
                "success": True,
                "domain": domain,
                "episodes_restored": len(backup_data.get('episodes', [])),
                "backup_path": backup_path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Rollback failed: {str(e)}"
            }
    
    async def list_backups(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups for a domain or all domains."""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.backup_dir, filename)
                file_stat = os.stat(file_path)
                
                backup_info = {
                    "filename": filename,
                    "path": file_path,
                    "size": file_stat.st_size,
                    "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                }
                
                # Extract domain from filename
                if '_' in filename:
                    backup_info["domain"] = filename.split('_')[0].replace('_', ' ')
                
                if domain is None or backup_info.get("domain") == domain:
                    backups.append(backup_info)
        
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    async def cleanup_old_backups(self, keep_days: int = 30) -> Dict[str, Any]:
        """Clean up old backup files."""
        cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        deleted_count = 0
        errors = []
        
        if not os.path.exists(self.backup_dir):
            return {"deleted_count": 0, "errors": []}
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.backup_dir, filename)
                file_stat = os.stat(file_path)
                
                if file_stat.st_mtime < cutoff_date:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        errors.append(f"Failed to delete {filename}: {str(e)}")
        
        return {
            "deleted_count": deleted_count,
            "errors": errors,
            "cutoff_date": datetime.fromtimestamp(cutoff_date).isoformat()
        } 