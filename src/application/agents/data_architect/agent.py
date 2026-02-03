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
import logging

logger = logging.getLogger(__name__)


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

    async def process_dda(self, file_path: str) -> Dict[str, Any]:
        """
        Process a DDA (Data Domain Architecture) file.

        This is the main entry point for DDA processing through the agent.
        Creates entities in the PERCEPTION layer and publishes events for
        downstream processing by Data Engineer and Knowledge Manager.

        Args:
            file_path: Path to the DDA markdown file

        Returns:
            Dictionary with processing results
        """
        from infrastructure.parsers.markdown_parser import MarkdownDDAParser

        logger.info(f"[{self.agent_id}] Processing DDA file: {file_path}")

        result = {
            "success": True,
            "domain": None,
            "entities_created": [],
            "relationships_created": [],
            "events_published": 0,
            "errors": []
        }

        try:
            # Step 1: Parse the DDA file
            parser = MarkdownDDAParser()
            dda_document = await parser.parse(file_path)
            result["domain"] = dda_document.domain

            logger.info(f"[{self.agent_id}] Parsed DDA for domain: {dda_document.domain}")

            # Step 2: Create Catalog entity in PERCEPTION layer
            catalog_entity = await self._create_catalog_entity(dda_document)
            if catalog_entity:
                result["entities_created"].append(catalog_entity)
                await self._publish_entity_created_event(catalog_entity)
                result["events_published"] += 1

            # Step 3: Create Schema entity
            schema_entity = await self._create_schema_entity(dda_document)
            if schema_entity:
                result["entities_created"].append(schema_entity)
                await self._publish_entity_created_event(schema_entity)
                result["events_published"] += 1

            # Step 4: Create Table and Column entities
            for entity in dda_document.entities:
                table_entity = await self._create_table_entity(dda_document.domain, entity)
                if table_entity:
                    result["entities_created"].append(table_entity)
                    await self._publish_entity_created_event(table_entity)
                    result["events_published"] += 1

                # Create columns for this table
                for attr in entity.attributes:
                    column_entity = await self._create_column_entity(entity.name, attr)
                    if column_entity:
                        result["entities_created"].append(column_entity)
                        # Batch column events to reduce noise

            # Step 5: Create relationships (escalated to Knowledge Manager)
            for rel in dda_document.relationships:
                rel_result = await self._create_relationship(rel)
                if rel_result.get("success"):
                    result["relationships_created"].append(rel_result.get("data"))
                elif rel_result.get("escalate"):
                    # Escalation will be handled asynchronously
                    pass
                else:
                    result["errors"].append(rel_result.get("error"))

            # Step 6: Extract and store business rules for REASONING layer
            await self._process_business_rules(dda_document)

            logger.info(
                f"[{self.agent_id}] DDA processing complete: "
                f"{len(result['entities_created'])} entities, "
                f"{len(result['relationships_created'])} relationships, "
                f"{result['events_published']} events published"
            )

        except Exception as e:
            logger.error(f"[{self.agent_id}] DDA processing failed: {e}", exc_info=True)
            result["success"] = False
            result["errors"].append(str(e))

        return result

    async def _create_catalog_entity(self, dda_document) -> Optional[Dict[str, Any]]:
        """Create a Catalog entity from DDA document."""
        if not self.kg_backend:
            return None

        try:
            catalog_query = """
            MERGE (c:Catalog {name: $domain})
            SET c.data_owner = $data_owner,
                c.business_context = $business_context,
                c.layer = 'PERCEPTION',
                c.status = 'pending_validation',
                c.source_type = 'dda',
                c.source_agent = $agent_id,
                c.updated_at = datetime(),
                c.created_at = COALESCE(c.created_at, datetime())
            RETURN elementId(c) as id, c.name as name
            """
            result = await self.kg_backend.query_raw(catalog_query, {
                "domain": dda_document.domain,
                "data_owner": dda_document.data_owner,
                "business_context": dda_document.business_context,
                "agent_id": self.agent_id
            })

            if result:
                return {
                    "id": result[0].get("id"),
                    "name": result[0].get("name"),
                    "type": "Catalog",
                    "layer": "PERCEPTION"
                }
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to create Catalog: {e}")

        return None

    async def _create_schema_entity(self, dda_document) -> Optional[Dict[str, Any]]:
        """Create a Schema entity from DDA document."""
        if not self.kg_backend:
            return None

        schema_name = f"{dda_document.domain}_schema"

        try:
            schema_query = """
            MATCH (c:Catalog {name: $domain})
            MERGE (s:Schema {name: $schema_name})
            MERGE (c)-[:CONTAINS_SCHEMA]->(s)
            SET s.layer = 'PERCEPTION',
                s.status = 'pending_validation',
                s.source_type = 'dda',
                s.source_agent = $agent_id,
                s.updated_at = datetime(),
                s.created_at = COALESCE(s.created_at, datetime())
            RETURN elementId(s) as id, s.name as name
            """
            result = await self.kg_backend.query_raw(schema_query, {
                "domain": dda_document.domain,
                "schema_name": schema_name,
                "agent_id": self.agent_id
            })

            if result:
                return {
                    "id": result[0].get("id"),
                    "name": result[0].get("name"),
                    "type": "Schema",
                    "layer": "PERCEPTION"
                }
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to create Schema: {e}")

        return None

    async def _create_table_entity(self, domain: str, entity) -> Optional[Dict[str, Any]]:
        """Create a Table entity from DDA entity definition."""
        if not self.kg_backend:
            return None

        schema_name = f"{domain}_schema"

        try:
            table_query = """
            MATCH (s:Schema {name: $schema_name})
            MERGE (t:Table {name: $table_name})
            MERGE (s)-[:CONTAINS_TABLE]->(t)
            SET t.description = $description,
                t.primary_key = $primary_key,
                t.business_rules = $business_rules,
                t.layer = 'PERCEPTION',
                t.status = 'pending_validation',
                t.source_type = 'dda',
                t.source_agent = $agent_id,
                t.confidence = 0.7,
                t.updated_at = datetime(),
                t.created_at = COALESCE(t.created_at, datetime())
            RETURN elementId(t) as id, t.name as name
            """
            result = await self.kg_backend.query_raw(table_query, {
                "schema_name": schema_name,
                "table_name": entity.name,
                "description": entity.description,
                "primary_key": entity.primary_key,
                "business_rules": entity.business_rules,
                "agent_id": self.agent_id
            })

            if result:
                return {
                    "id": result[0].get("id"),
                    "name": result[0].get("name"),
                    "type": "Table",
                    "layer": "PERCEPTION"
                }
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to create Table {entity.name}: {e}")

        return None

    async def _create_column_entity(self, table_name: str, attribute: str) -> Optional[Dict[str, Any]]:
        """Create a Column entity from table attribute."""
        if not self.kg_backend:
            return None

        # Parse attribute (format might be "column_name (type)" or just "column_name")
        attr_name = attribute.split('(')[0].strip() if '(' in attribute else attribute.strip()
        attr_type = "VARCHAR"  # Default type
        if '(' in attribute and ')' in attribute:
            type_part = attribute.split('(')[1].split(')')[0].strip()
            if type_part not in ['Primary Key', 'Foreign Key']:
                attr_type = type_part

        is_primary = 'Primary Key' in attribute
        is_foreign = 'Foreign Key' in attribute

        try:
            column_query = """
            MATCH (t:Table {name: $table_name})
            MERGE (col:Column {name: $column_name, table: $table_name})
            MERGE (t)-[:HAS_COLUMN]->(col)
            SET col.data_type = $data_type,
                col.is_primary_key = $is_primary,
                col.is_foreign_key = $is_foreign,
                col.layer = 'PERCEPTION',
                col.status = 'pending_validation',
                col.source_type = 'dda',
                col.source_agent = $agent_id,
                col.confidence = 0.7,
                col.updated_at = datetime(),
                col.created_at = COALESCE(col.created_at, datetime())
            RETURN elementId(col) as id, col.name as name
            """
            result = await self.kg_backend.query_raw(column_query, {
                "table_name": table_name,
                "column_name": attr_name,
                "data_type": attr_type,
                "is_primary": is_primary,
                "is_foreign": is_foreign,
                "agent_id": self.agent_id
            })

            if result:
                return {
                    "id": result[0].get("id"),
                    "name": result[0].get("name"),
                    "type": "Column",
                    "layer": "PERCEPTION"
                }
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to create Column {attr_name}: {e}")

        return None

    async def _create_relationship(self, rel) -> Dict[str, Any]:
        """Create a relationship between tables (escalated to Knowledge Manager)."""
        if not self.kg_backend:
            return {"success": False, "error": "No backend available"}

        # Relationships are escalated to Knowledge Manager for validation
        # But we still create them in PERCEPTION layer as pending
        try:
            rel_query = """
            MATCH (source:Table {name: $source_name})
            MATCH (target:Table {name: $target_name})
            MERGE (source)-[r:RELATES_TO {type: $rel_type}]->(target)
            SET r.description = $description,
                r.cardinality = $rel_type,
                r.layer = 'PERCEPTION',
                r.status = 'pending_validation',
                r.source_type = 'dda',
                r.source_agent = $agent_id,
                r.confidence = 0.7,
                r.updated_at = datetime(),
                r.created_at = COALESCE(r.created_at, datetime())
            RETURN type(r) as rel_type
            """
            await self.kg_backend.query_raw(rel_query, {
                "source_name": rel.source_entity,
                "target_name": rel.target_entity,
                "rel_type": rel.relationship_type,
                "description": rel.description,
                "agent_id": self.agent_id
            })

            # Escalate to Knowledge Manager for validation
            return {
                "success": True,
                "escalate": True,
                "data": {
                    "source": rel.source_entity,
                    "target": rel.target_entity,
                    "type": rel.relationship_type
                },
                "operation": {
                    "action": "validate_relationship",
                    "data": {
                        "source": rel.source_entity,
                        "target": rel.target_entity,
                        "type": rel.relationship_type,
                        "description": rel.description
                    },
                    "role": Role.DATA_ARCHITECT
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _process_business_rules(self, dda_document) -> None:
        """
        Extract business rules from DDA and prepare them for REASONING layer.

        Business rules are stored as separate nodes that will be converted to
        executable rules by the Knowledge Manager.
        """
        if not self.kg_backend:
            return

        for entity in dda_document.entities:
            if not entity.business_rules:
                continue

            # Parse business rules (can be a list or string)
            rules = entity.business_rules if isinstance(entity.business_rules, list) else [entity.business_rules]

            for i, rule_text in enumerate(rules):
                if not rule_text or not rule_text.strip():
                    continue

                try:
                    # Store business rule as a pending rule node
                    rule_query = """
                    MATCH (t:Table {name: $table_name})
                    CREATE (r:BusinessRule {
                        name: $rule_name,
                        rule_text: $rule_text,
                        subject_entity: $table_name,
                        layer: 'PERCEPTION',
                        status: 'pending_conversion',
                        source_type: 'dda',
                        source_agent: $agent_id,
                        created_at: datetime()
                    })
                    CREATE (t)-[:HAS_RULE]->(r)
                    RETURN elementId(r) as id
                    """
                    await self.kg_backend.query_raw(rule_query, {
                        "table_name": entity.name,
                        "rule_name": f"{entity.name}_rule_{i+1}",
                        "rule_text": rule_text.strip(),
                        "agent_id": self.agent_id
                    })

                    logger.debug(f"[{self.agent_id}] Created business rule for {entity.name}")

                except Exception as e:
                    logger.warning(f"[{self.agent_id}] Failed to create business rule: {e}")

    async def _publish_entity_created_event(self, entity: Dict[str, Any]) -> None:
        """Publish an entity_created event for downstream processing."""
        if not self.event_bus:
            return

        try:
            event = KnowledgeEvent(
                action="entity_created",
                data={
                    "entity_id": entity.get("id"),
                    "entity_name": entity.get("name"),
                    "entity_type": entity.get("type"),
                    "layer": entity.get("layer"),
                    "source_agent": self.agent_id,
                    "source_type": "dda"
                },
                role=Role.DATA_ARCHITECT
            )
            await self.event_bus.publish(event)
            logger.debug(f"[{self.agent_id}] Published entity_created event for {entity.get('name')}")
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to publish event: {e}")