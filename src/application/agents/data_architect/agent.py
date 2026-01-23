from domain.agent import Agent
from application.commands.agent_commands import StartProjectCommand
from graphiti_core import Graphiti
from langchain_core.documents import Document
from typing import Optional, Dict, Any, List
from domain.communication import CommunicationChannel
from domain.command_bus import CommandBus
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.kg_backends import KnowledgeGraphBackend
from application.event_bus import EventBus


class DataArchitectAgent(Agent):
    """
    The Data Architect agent.
    Focuses on high-level design and problem-solving.
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        graph: Graphiti,
        llm: Graphiti,
        url: str,
        kg_backend: Optional[KnowledgeGraphBackend] = None,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            command_bus=command_bus,
            communication_channel=communication_channel,
        )
        self.graph = graph
        self.llm = llm
        self.url = url
        self.kg_backend = kg_backend
        self.event_bus = event_bus
        
        # Knowledge management configuration
        self.simple_operations = {
            "create_entity": True,
            "create_relationship": False,  # Escalate to Knowledge Manager
            "update_entity": True,
            "delete_entity": False,  # Escalate to Knowledge Manager
        }

    async def register_self(self):
        """
        Registers the agent as a service in the knowledge graph.
        """
        await self.graph.upsert_node(
            "AgentService",
            self.agent_id,
            {"url": self.url, "capabilities": ["design", "planning", "simple_kg_updates"]},
        )

    async def discover_agent(self, capability: str) -> Optional[str]:
        """
        Discovers an agent with a specific capability by querying the
        knowledge graph. Returns the agent's URL.
        """
        nodes = await self.graph.get_nodes(
            "AgentService", {"capability": capability}
        )
        if nodes:
            # For simplicity, return the first agent found
            return nodes[0].properties.get("url")
        return None

    async def process_messages(self) -> None:
        """Processes incoming messages, looking for new project goals."""
        message = await self.receive_message()
        if not message:
            return

        if isinstance(message.content, StartProjectCommand):
            project_goal = message.content.project_goal
            print(f"[{self.agent_id}] Received new project goal: '{project_goal}'")

            # 1. Use llm to create a plan.
            graph_document = self.llm.process(project_goal)
            
            # 2. Persist the plan to the graph.
            self.graph.add_graph_document(graph_document)
            
            print(f"[{self.agent_id}] Plan created and saved to the graph.")
            print(f"  - Nodes created: {len(graph_document.nodes)}")
            print(f"  - Relationships created: {len(graph_document.relationships)}")

            # TODO: Send the first task to the DataEngineerAgent.
        else:
            print(
                f"[{self.agent_id}] Received unhandled message type: {type(message.content)}"
            )

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
                else:
                    result["errors"].append(entity_result["error"])
            
            # Process relationships
            for relationship in relationships:
                rel_result = await self._process_relationship(relationship)
                if rel_result["success"]:
                    result["relationships_processed"] += 1
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
                        "role": Role.DATA_ARCHITECT
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
                        "role": Role.DATA_ARCHITECT
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

    async def create_domain_model(self, domain_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a domain model and update the knowledge graph.
        This is a complex operation that may require escalation.
        """
        try:
            # Extract entities and relationships from domain data
            entities = domain_data.get("entities", [])
            relationships = domain_data.get("relationships", [])
            
            # Update knowledge graph
            result = await self.update_knowledge_graph(entities, relationships)
            
            if result["success"]:
                print(f"[{self.agent_id}] Domain model created successfully")
                print(f"  - Entities: {result['entities_processed']}")
                print(f"  - Relationships: {result['relationships_processed']}")
            else:
                print(f"[{self.agent_id}] Domain model creation had issues:")
                for error in result["errors"]:
                    print(f"  - Error: {error}")
            
            return result
            
        except Exception as e:
            error_msg = f"Domain model creation failed: {str(e)}"
            print(f"[{self.agent_id}] {error_msg}")
            return {"success": False, "error": error_msg}

    async def validate_domain_model(self, domain_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a domain model before creation.
        This is a simple operation that can be done directly.
        """
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Basic validation
        entities = domain_data.get("entities", [])
        relationships = domain_data.get("relationships", [])
        
        # Check for required fields
        for i, entity in enumerate(entities):
            if not entity.get("id"):
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Entity {i}: Missing ID")
        
        for i, rel in enumerate(relationships):
            required_fields = ["source", "target", "type"]
            for field in required_fields:
                if not rel.get(field):
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(f"Relationship {i}: Missing {field}")
        
        # Check for circular references
        for rel in relationships:
            if rel.get("source") == rel.get("target"):
                validation_result["warnings"].append(f"Circular relationship: {rel.get('source')} -> {rel.get('target')}")
        
        return validation_result 