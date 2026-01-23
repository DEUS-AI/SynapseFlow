from domain.agent import Agent
from domain.communication import CommunicationChannel
from domain.command_bus import CommandBus
from graphiti_core import Graphiti
from typing import Optional, Dict, Any, List
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.kg_backends import KnowledgeGraphBackend
from application.event_bus import EventBus


class DataEngineerAgent(Agent):
    """
    The Data Engineer agent.
    Handles implementation and can challenge design decisions.
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        graph: Graphiti,
        url: str,
        kg_backend: Optional[KnowledgeGraphBackend] = None,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(
            agent_id, command_bus, communication_channel
        )
        self.graph = graph
        self.url = url
        self.kg_backend = kg_backend
        self.event_bus = event_bus
        
        # Knowledge management configuration - Data Engineers have more permissions
        self.simple_operations = {
            "create_entity": True,
            "create_relationship": True,  # Data Engineers can create relationships
            "update_entity": True,
            "delete_entity": False,  # Escalate to Knowledge Manager
            "batch_operations": False,  # Escalate to Knowledge Manager
        }

    async def register_self(self):
        """
        Registers the agent as a service in the knowledge graph.
        """
        try:
            await self.graph.upsert_node(
                "AgentService",
                self.agent_id,
                {"url": self.url, "capabilities": ["implementation", "kg_operations", "data_processing"]},
            )
        except Exception as e:
            print(f"[{self.agent_id}] Warning: Could not register with Graphiti: {e}")

    async def process_messages(self) -> None:
        """Process incoming messages and handle knowledge graph operations."""
        message = await self.receive_message()
        if not message:
            return
        
        try:
            if isinstance(message.content, dict):
                await self._handle_dict_message(message.content)
            else:
                print(f"[{self.agent_id}] Received unhandled message type: {type(message.content)}")
        except Exception as e:
            print(f"[{self.agent_id}] Error processing message: {e}")

    async def _handle_dict_message(self, content: Dict[str, Any]) -> None:
        """Handle dictionary-based messages."""
        message_type = content.get("type")
        
        if message_type == "kg_update_request":
            await self._handle_kg_update_request(content)
        elif message_type == "data_processing_request":
            await self._handle_data_processing_request(content)
        elif message_type == "validation_request":
            await self._handle_validation_request(content)
        else:
            print(f"[{self.agent_id}] Unknown message type: {message_type}")

    async def _handle_kg_update_request(self, content: Dict[str, Any]) -> None:
        """Handle knowledge graph update requests."""
        entities = content.get("entities", [])
        relationships = content.get("relationships", [])
        sender_id = content.get("sender_id")
        
        print(f"[{self.agent_id}] Processing KG update request: {len(entities)} entities, {len(relationships)} relationships")
        
        result = await self.update_knowledge_graph(entities, relationships)
        
        # Send response back to sender
        if sender_id:
            await self.send_message(sender_id, {
                "type": "kg_update_response",
                "request_id": content.get("request_id"),
                "result": result
            })

    async def _handle_data_processing_request(self, content: Dict[str, Any]) -> None:
        """Handle data processing requests."""
        data_source = content.get("data_source")
        processing_type = content.get("processing_type")
        sender_id = content.get("sender_id")
        
        print(f"[{self.agent_id}] Processing data: {data_source} - {processing_type}")
        
        # Process data and extract entities/relationships
        extracted_data = await self._process_data(data_source, processing_type)
        
        # Update knowledge graph with extracted data
        if extracted_data:
            result = await self.update_knowledge_graph(
                extracted_data.get("entities", []),
                extracted_data.get("relationships", [])
            )
            
            # Send response back to sender
            if sender_id:
                await self.send_message(sender_id, {
                    "type": "data_processing_response",
                    "request_id": content.get("request_id"),
                    "result": result,
                    "extracted_data": extracted_data
                })

    async def _handle_validation_request(self, content: Dict[str, Any]) -> None:
        """Handle validation requests."""
        data_to_validate = content.get("data")
        validation_type = content.get("validation_type")
        sender_id = content.get("sender_id")
        
        print(f"[{self.agent_id}] Validating data: {validation_type}")
        
        validation_result = await self._validate_data(data_to_validate, validation_type)
        
        # Send validation response back to sender
        if sender_id:
            await self.send_message(sender_id, {
                "type": "validation_response",
                "request_id": content.get("request_id"),
                "result": validation_result
            })

    # Knowledge Graph Update Methods
    async def update_knowledge_graph(self, entities: List[Dict[str, Any]], 
                                   relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update the knowledge graph with extracted entities and relationships.
        Automatically escalates complex operations to the Knowledge Manager.
        """
        result = {
            "success": True,
            "entities_processed": 0,
            "relationships_processed": 0,
            "escalated_operations": [],
            "errors": []
        }
        
        try:
            # Process entities
            for entity in entities:
                entity_result = await self._process_entity(entity)
                if entity_result["success"]:
                    result["entities_processed"] += 1
                elif entity_result.get("escalate"):
                    result["escalated_operations"].append(entity_result["operation"])
                else:
                    result["errors"].append(entity_result["error"])
            
            # Process relationships
            for relationship in relationships:
                rel_result = await self._process_relationship(relationship)
                if rel_result["success"]:
                    result["relationships_processed"] += 1
                elif rel_result.get("escalate"):
                    result["escalated_operations"].append(rel_result["operation"])
                else:
                    result["errors"].append(rel_result["error"])
            
            # Escalate complex operations if needed
            if result["escalated_operations"]:
                await self._escalate_operations(result["escalated_operations"])
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Knowledge graph update failed: {str(e)}")
        
        return result

    async def _process_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single entity, escalating if complex."""
        try:
            # Check if this is a simple operation
            if self.simple_operations.get("create_entity", False):
                # Direct update
                if self.kg_backend:
                    await self.kg_backend.add_entity(
                        entity.get("id"),
                        entity.get("properties", {})
                    )
                return {"success": True}
            else:
                # Escalate to Knowledge Manager
                return {
                    "success": False,
                    "escalate": True,
                    "operation": {
                        "action": "create_entity",
                        "data": entity,
                        "role": Role.DATA_ENGINEER
                    }
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _process_relationship(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single relationship, escalating if complex."""
        try:
            # Check if this is a simple operation
            if self.simple_operations.get("create_relationship", False):
                # Direct update
                if self.kg_backend:
                    await self.kg_backend.add_relationship(
                        relationship.get("source"),
                        relationship.get("type"),
                        relationship.get("target"),
                        relationship.get("properties", {})
                    )
                return {"success": True}
            else:
                # Escalate to Knowledge Manager
                return {
                    "success": False,
                    "escalate": True,
                    "operation": {
                        "action": "create_relationship",
                        "data": relationship,
                        "role": Role.DATA_ENGINEER
                    }
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _escalate_operations(self, operations: List[Dict[str, Any]]) -> None:
        """Escalate complex operations to the Knowledge Manager."""
        if not self.event_bus:
            print(f"[{self.agent_id}] Warning: No event bus available for escalation")
            return
        
        # Find Knowledge Manager agent
        km_agent_id = await self._find_knowledge_manager()
        if not km_agent_id:
            print(f"[{self.agent_id}] Warning: No Knowledge Manager found for escalation")
            return
        
        # Send escalation message
        escalation_message = {
            "type": "escalate_operations",
            "agent_id": self.agent_id,
            "operations": operations,
            "reason": "Complex operations requiring advanced validation and reasoning"
        }
        
        await self.send_message(km_agent_id, escalation_message)
        print(f"[{self.agent_id}] Escalated {len(operations)} operations to Knowledge Manager")

    async def _find_knowledge_manager(self) -> Optional[str]:
        """Find the Knowledge Manager agent."""
        try:
            # Query the knowledge graph for Knowledge Manager agents
            if self.kg_backend:
                result = await self.kg_backend.query(
                    "MATCH (n:AgentService {capabilities: 'complex_kg_operations'}) RETURN n.id"
                )
                if result and len(result) > 0:
                    return result[0].get("id")
            
            # Fallback: look for agents with knowledge management capabilities
            return await self.discover_agent("knowledge_management")
        except Exception:
            return None

    async def _process_data(self, data_source: str, processing_type: str) -> Optional[Dict[str, Any]]:
        """Process data and extract entities/relationships."""
        try:
            # This is a placeholder for data processing logic
            # In a real implementation, this would:
            # 1. Read data from the source
            # 2. Apply processing based on type
            # 3. Extract entities and relationships
            # 4. Return structured data
            
            print(f"[{self.agent_id}] Processing data from {data_source} with type {processing_type}")
            
            # Mock extracted data for demonstration
            extracted_data = {
                "entities": [
                    {"id": f"entity_{data_source}_{processing_type}", "properties": {"source": data_source, "type": processing_type}}
                ],
                "relationships": []
            }
            
            return extracted_data
            
        except Exception as e:
            print(f"[{self.agent_id}] Data processing failed: {e}")
            return None

    async def _validate_data(self, data: Any, validation_type: str) -> Dict[str, Any]:
        """Validate data based on the specified validation type."""
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        try:
            if validation_type == "entity":
                validation_result = await self._validate_entity_data(data)
            elif validation_type == "relationship":
                validation_result = await self._validate_relationship_data(data)
            elif validation_type == "batch":
                validation_result = await self._validate_batch_data(data)
            else:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Unknown validation type: {validation_type}")
                
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Validation failed: {str(e)}")
        
        return validation_result

    async def _validate_entity_data(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Validate entity data."""
        result = {"is_valid": True, "warnings": [], "errors": []}
        
        if not entity.get("id"):
            result["is_valid"] = False
            result["errors"].append("Entity missing ID")
        
        if not isinstance(entity.get("properties"), dict):
            result["warnings"].append("Entity properties should be a dictionary")
        
        return result

    async def _validate_relationship_data(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        """Validate relationship data."""
        result = {"is_valid": True, "warnings": [], "errors": []}
        
        required_fields = ["source", "target", "type"]
        for field in required_fields:
            if not relationship.get(field):
                result["is_valid"] = False
                result["errors"].append(f"Relationship missing {field}")
        
        return result

    async def _validate_batch_data(self, batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate batch data."""
        result = {"is_valid": True, "warnings": [], "errors": []}
        
        if not isinstance(batch_data, list):
            result["is_valid"] = False
            result["errors"].append("Batch data must be a list")
            return result
        
        if len(batch_data) > 1000:
            result["warnings"].append("Large batch detected (>1000 items) - consider breaking into smaller batches")
        
        for i, item in enumerate(batch_data):
            if not isinstance(item, dict):
                result["errors"].append(f"Item {i}: Not a dictionary")
                result["is_valid"] = False
        
        return result 