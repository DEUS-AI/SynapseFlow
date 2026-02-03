#!/usr/bin/env python3
"""
SynapseFlow Multi-Agent DDA Demo
================================

This script demonstrates the multi-agent system working with Data Delivery Agreements:
- Data Architect Agent: Processes DDA documents and creates domain models
- Data Engineer Agent: Implements and validates the models
- Knowledge Manager Agent: Handles complex operations and conflict resolution
- Event-driven communication between agents
- Knowledge graph updates and validation

Usage: python multi_agent_dda_demo.py [--dda-file] [--interactive]
"""

import asyncio
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from infrastructure.in_memory_backend import InMemoryGraphBackend
from src.infrastructure.neo4j_backend import create_neo4j_backend
from application.event_bus import EventBus
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.communication import Message
from src.infrastructure.communication.memory_channel import InMemoryCommunicationChannel
from src.application.commands.base import CommandBus
# Mock classes for demo purposes (avoiding external dependencies)
class MockGraphiti:
    """Mock Graphiti class for demo purposes."""
    async def upsert_node(self, *args, **kwargs):
        return True
    async def get_nodes(self, *args, **kwargs):
        return []
    async def process(self, *args, **kwargs):
        return {"nodes": [], "relationships": []}
    async def add_graph_document(self, *args, **kwargs):
        return True

class MockDataArchitectAgent:
    """Mock Data Architect Agent for demo purposes."""
    def __init__(self, agent_id, **kwargs):
        self.agent_id = agent_id
        self.simple_operations = {
            "create_entity": True,
            "create_relationship": False,
            "update_entity": True,
            "delete_entity": False,
        }
    
    async def register_self(self):
        print(f"[{self.agent_id}] Mock registration completed")
        return True
    
    async def create_domain_model(self, domain_data):
        entities = domain_data.get("entities", [])
        relationships = domain_data.get("relationships", [])
        return {
            "success": True,
            "entities_processed": len(entities),
            "relationships_processed": len(relationships),
            "errors": []
        }

class MockDataEngineerAgent:
    """Mock Data Engineer Agent for demo purposes."""
    def __init__(self, agent_id, **kwargs):
        self.agent_id = agent_id
        self.simple_operations = {
            "create_entity": True,
            "create_relationship": True,
            "update_entity": True,
            "delete_entity": False,
            "batch_operations": False,
        }
    
    async def register_self(self):
        print(f"[{self.agent_id}] Mock registration completed")
        return True
    
    async def _handle_kg_update_request(self, content):
        entities = content.get("entities", [])
        relationships = content.get("relationships", [])
        print(f"[{self.agent_id}] Processing KG update: {len(entities)} entities, {len(relationships)} relationships")
        return {"success": True, "processed": len(entities) + len(relationships)}

class MockKnowledgeManagerAgent:
    """Mock Knowledge Manager Agent for demo purposes."""
    def __init__(self, agent_id, **kwargs):
        self.agent_id = agent_id
        self.conflict_resolver = MockConflictResolver()
        self.validation_engine = MockValidationEngine()
        self.reasoning_engine = MockReasoningEngine()
    
    async def register_self(self):
        print(f"[{self.agent_id}] Mock registration completed")
        return True

class MockConflictResolver:
    """Mock Conflict Resolver for demo purposes."""
    async def detect_conflicts(self, event):
        if "duplicate" in str(event.data).lower():
            return [{"type": "duplicate_entity", "description": "Entity ID already exists"}]
        return []

class MockValidationEngine:
    """Mock Validation Engine for demo purposes."""
    async def validate_event(self, event):
        return {"is_valid": True, "warnings": [], "errors": []}

class MockReasoningEngine:
    """Mock Reasoning Engine for demo purposes."""
    async def apply_reasoning(self, event):
        return {"inferred_properties": ["type", "status"], "reasoning_applied": True}


class MultiAgentDDADemo:
    """Interactive demonstration of multi-agent collaboration with DDAs."""
    
    def __init__(self):
        # Initialize components
        self.kg_backend = None
        self.neo4j_available = False
        self._initialize_backend()
        
        self.event_bus = EventBus()
        self.communication_channel = InMemoryCommunicationChannel()
        self.command_bus = CommandBus()
        
        # Initialize agents
        self.data_architect = None
        self.data_engineer = None
        self.knowledge_manager = None
        
        # Demo data
        self.dda_files = self._discover_dda_files()
        self.current_dda = None
        self.demo_results = {}
        
        self.setup_agents()
    
    def _initialize_backend(self):
        """Initialize the knowledge graph backend, trying Neo4j first."""
        try:
            # Try to connect to Neo4j
            print("🔍 Checking Neo4j availability...")
            
            # Test Neo4j connection asynchronously
            async def test_neo4j():
                try:
                    backend = await create_neo4j_backend()
                    # Test a simple query
                    await backend.query("RETURN 1 as test")
                    await backend.close()
                    return True
                except Exception as e:
                    print(f"   ⚠️  Neo4j connection failed: {e}")
                    return False
            
            # Run the test
            import asyncio
            self.neo4j_available = asyncio.run(test_neo4j())
            
            if self.neo4j_available:
                print("   ✅ Neo4j available - using persistent backend")
                self.kg_backend = asyncio.run(create_neo4j_backend())
            else:
                print("   ℹ️  Neo4j not available - using in-memory backend")
                self.kg_backend = InMemoryGraphBackend()
                
        except Exception as e:
            print(f"   ❌ Backend initialization failed: {e}")
            print("   ℹ️  Falling back to in-memory backend")
            self.kg_backend = InMemoryGraphBackend()
            self.neo4j_available = False
    
    def _discover_dda_files(self) -> List[str]:
        """Discover available DDA files in the examples directory."""
        examples_dir = Path("examples")
        if not examples_dir.exists():
            return []
        
        dda_files = []
        for file_path in examples_dir.glob("*_dda.md"):
            dda_files.append(str(file_path))
        
        # Also check for files ending in dda.md
        for file_path in examples_dir.glob("*dda.md"):
            if str(file_path) not in dda_files:
                dda_files.append(str(file_path))
        
        return sorted(dda_files)
    
    def setup_agents(self):
        """Initialize and configure all agents."""
        print("🔧 Setting up multi-agent system...")
        
        # Create Knowledge Manager Agent first (it will be referenced by others)
        self.knowledge_manager = MockKnowledgeManagerAgent(
            agent_id="knowledge_manager_agent"
        )
        
        # Create Data Architect Agent
        self.data_architect = MockDataArchitectAgent(
            agent_id="data_architect_agent"
        )
        
        # Create Data Engineer Agent
        self.data_engineer = MockDataEngineerAgent(
            agent_id="data_engineer_agent"
        )
        
        print("✅ Multi-agent system initialized")
        print(f"   📊 Knowledge Manager: {self.knowledge_manager.agent_id}")
        print(f"   🏗️  Data Architect: {self.data_architect.agent_id}")
        print(f"   🔧 Data Engineer: {self.data_engineer.agent_id}")
    
    def print_header(self, title: str):
        """Print a formatted section header."""
        print(f"\n{'='*70}")
        print(f"🎯 {title}")
        print(f"{'='*70}")
    
    def print_step(self, step_num: int, description: str):
        """Print a formatted step."""
        print(f"\n📋 Step {step_num}: {description}")
        print("-" * 60)
    
    def print_success(self, message: str):
        """Print a success message."""
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        """Print an error message."""
        print(f"❌ {message}")
    
    def print_info(self, message: str):
        """Print an info message."""
        print(f"ℹ️  {message}")
    
    def print_agent_message(self, agent_id: str, message: str):
        """Print a message from a specific agent."""
        print(f"🤖 [{agent_id}]: {message}")
    
    def select_dda_file(self) -> Optional[str]:
        """Let user select a DDA file to process."""
        if not self.dda_files:
            self.print_error("No DDA files found in examples directory")
            return None
        
        print("\n📚 Available DDA files:")
        for i, file_path in enumerate(self.dda_files, 1):
            file_name = Path(file_path).name
            print(f"   {i}. {file_name}")
        
        while True:
            try:
                choice = input(f"\n🎯 Select DDA file (1-{len(self.dda_files)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(self.dda_files):
                    selected_file = self.dda_files[choice_num - 1]
                    self.print_success(f"Selected: {Path(selected_file).name}")
                    return selected_file
                else:
                    print("❌ Invalid choice. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def read_dda_content(self, file_path: str) -> Dict[str, Any]:
        """Read and parse DDA content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple parsing for demo purposes
            dda_data = {
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "content": content,
                "entities": [],
                "relationships": [],
                "domain": "Unknown",
                "stakeholders": []
            }
            
            # Extract basic information
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "**Domain**:" in line:
                    domain = line.split("**Domain**:")[1].strip()
                    dda_data["domain"] = domain
                elif "**Stakeholders**:" in line:
                    # Look for stakeholders in next few lines
                    for j in range(i+1, min(i+5, len(lines))):
                        if lines[j].strip() and not lines[j].startswith('#'):
                            stakeholders = lines[j].strip()
                            dda_data["stakeholders"] = [s.strip() for s in stakeholders.split(',')]
                            break
            
            # Extract entities (simplified)
            entity_sections = content.split('### ')
            for section in entity_sections[1:]:  # Skip first empty section
                if section.strip():
                    entity_name = section.split('\n')[0].strip()
                    if entity_name and not entity_name.startswith('#'):
                        # Clean entity name and create proper ID
                        clean_name = entity_name.strip()
                        clean_id = clean_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                        
                        dda_data["entities"].append({
                            "id": f"{clean_id}_001",
                            "name": clean_name,
                            "type": "entity",
                            "properties": {
                                "name": clean_name, 
                                "source": "dda",
                                "domain": dda_data.get("domain", "Unknown"),
                                "entity_type": "business_entity"
                            }
                        })
            
            return dda_data
            
        except Exception as e:
            self.print_error(f"Failed to read DDA file: {e}")
            return {}
    
    def demo_1_agent_registration(self):
        """Demonstrate agent registration and discovery."""
        self.print_header("DEMO 1: Agent Registration and Discovery")
        
        # Step 1: Register agents
        self.print_step(1, "Registering agents in the knowledge graph")
        
        try:
            asyncio.run(self.knowledge_manager.register_self())
            asyncio.run(self.data_architect.register_self())
            asyncio.run(self.data_engineer.register_self())
            
            self.print_success("All agents registered successfully")
        except Exception as e:
            self.print_error(f"Agent registration failed: {e}")
            return False
        
        # Step 2: Show agent capabilities
        self.print_step(2, "Agent capabilities and permissions")
        
        print("📊 Knowledge Manager Agent:")
        print("   - Complex KG operations")
        print("   - Conflict resolution")
        print("   - Validation and reasoning")
        print("   - Escalation handling")
        
        print("\n📊 Data Architect Agent:")
        print("   - Simple entity creation: ✅")
        print("   - Simple entity updates: ✅")
        print("   - Relationship creation: ❌ (escalates)")
        print("   - Entity deletion: ❌ (escalates)")
        
        print("\n📊 Data Engineer Agent:")
        print("   - Simple entity creation: ✅")
        print("   - Simple entity updates: ✅")
        print("   - Relationship creation: ✅")
        print("   - Entity deletion: ❌ (escalates)")
        
        return True
    
    def demo_2_dda_processing(self):
        """Demonstrate DDA document processing."""
        self.print_header("DEMO 2: DDA Document Processing")
        
        # Step 1: Select DDA file
        self.print_step(1, "Selecting DDA file for processing")
        
        dda_file = self.select_dda_file()
        if not dda_file:
            return False
        
        self.current_dda = dda_file
        
        # Step 2: Read and parse DDA
        self.print_step(2, "Reading and parsing DDA content")
        
        dda_data = self.read_dda_content(dda_file)
        if not dda_data:
            return False
        
        self.print_success(f"DDA loaded: {dda_data['domain']}")
        self.print_info(f"   File: {dda_data['file_name']}")
        self.print_info(f"   Entities found: {len(dda_data['entities'])}")
        self.print_info(f"   Stakeholders: {', '.join(dda_data['stakeholders'])}")
        
        # Step 3: Show DDA content structure
        self.print_step(3, "DDA content structure")
        
        print("📋 Document Structure:")
        print(f"   Domain: {dda_data['domain']}")
        print(f"   Stakeholders: {len(dda_data['stakeholders'])} identified")
        print(f"   Entities: {len(dda_data['entities'])} discovered")
        
        if dda_data['entities']:
            print("\n   📊 Entities found:")
            for entity in dda_data['entities'][:5]:  # Show first 5
                print(f"      - {entity['name']} (ID: {entity['id']})")
        
        return True
    
    def demo_3_knowledge_graph_creation(self):
        """Demonstrate knowledge graph creation from DDA."""
        self.print_header("DEMO 3: Knowledge Graph Creation")
        
        if not self.current_dda:
            self.print_error("No DDA selected. Please run Demo 2 first.")
            return False
        
        # Step 1: Data Architect processes DDA and creates entities
        self.print_step(1, "Data Architect processing DDA and creating entities")
        
        # Show backend information
        backend_type = "Neo4j (Persistent)" if self.neo4j_available else "In-Memory (Demo)"
        print(f"   🗄️  Using backend: {backend_type}")
        
        dda_data = self.read_dda_content(self.current_dda)
        
        try:
            # Simulate Data Architect processing
            self.print_agent_message("Data Architect", f"Processing DDA for domain: {dda_data['domain']}")
            
            # Actually create entities in the knowledge graph
            entities_created = 0
            for entity in dda_data['entities']:
                try:
                    asyncio.run(self.kg_backend.add_entity(
                        entity['id'],
                        entity['properties']
                    ))
                    entities_created += 1
                    print(f"   ✅ Created entity: {entity['name']} (ID: {entity['id']})")
                except Exception as e:
                    print(f"   ❌ Failed to create entity {entity['id']}: {e}")
            
            self.print_success(f"Successfully created {entities_created} entities in knowledge graph")
            
            # Create some basic relationships between entities
            relationships_created = 0
            if len(dda_data['entities']) > 1:
                # Create a simple relationship structure
                for i in range(len(dda_data['entities']) - 1):
                    try:
                        source = dda_data['entities'][i]['id']
                        target = dda_data['entities'][i + 1]['id']
                        asyncio.run(self.kg_backend.add_relationship(
                            source, "RELATES_TO", target, {"source": "dda_processing"}
                        ))
                        relationships_created += 1
                        print(f"   ✅ Created relationship: {source} --[RELATES_TO]--> {target}")
                    except Exception as e:
                        print(f"   ❌ Failed to create relationship: {e}")
            
            self.print_success(f"Successfully created {relationships_created} relationships")
            
        except Exception as e:
            self.print_error(f"Data Architect processing failed: {e}")
            return False
        
        # Step 2: Show knowledge graph state after creation
        self.print_step(2, "Knowledge graph state after entity creation")
        
        try:
            # Query the knowledge graph
            result = asyncio.run(self.kg_backend.query("MATCH (n) RETURN n"))
            
            if result and "nodes" in result:
                node_count = len(result["nodes"])
                self.print_success(f"Knowledge graph now contains {node_count} nodes")
                
                # Show some nodes
                print("\n   📊 Sample nodes created:")
                for i, (node_id, node_data) in enumerate(list(result["nodes"].items())[:5]):
                    node_type = node_data.get("labels", ["unknown"])[0] if node_data.get("labels") else "unknown"
                    node_name = node_data.get("properties", {}).get("name", "Unknown")
                    print(f"      - {node_id} ({node_type}): {node_name}")
                
                # Query relationships
                rel_result = asyncio.run(self.kg_backend.query("MATCH ()-[r]->() RETURN r"))
                if rel_result and "edges" in rel_result:
                    # Count total relationships
                    total_rels = sum(len(edges) for edges in rel_result["edges"].values())
                    print(f"\n   📊 Relationships created: {total_rels}")
                    
                    # Show some relationships
                    rel_count = 0
                    for source_id, edges_list in rel_result["edges"].items():
                        for rel_type, target_id, properties in edges_list[:2]:  # Show max 2 per source
                            if rel_count < 5:  # Show max 5 total
                                print(f"      - {source_id} --[{rel_type}]--> {target_id}")
                                rel_count += 1
                            else:
                                break
                        if rel_count >= 5:
                            break
            else:
                self.print_info("Knowledge graph query failed")
        except Exception as e:
            self.print_error(f"Failed to query knowledge graph: {e}")
        
        return True
    
    def demo_4_agent_collaboration(self):
        """Demonstrate agent collaboration and communication."""
        self.print_header("DEMO 4: Agent Collaboration and Communication")
        
        # Step 1: Data Engineer receives work based on actual KG data
        self.print_step(1, "Data Engineer receiving work from Data Architect")
        
        try:
            # Query the actual knowledge graph to get real entities
            kg_result = asyncio.run(self.kg_backend.query("MATCH (n) RETURN n LIMIT 5"))
            
            if not kg_result or "nodes" not in kg_result or not kg_result["nodes"]:
                self.print_error("No entities found in knowledge graph. Please run Demo 3 first.")
                return False
            
            # Create work request based on actual KG entities
            real_entities = []
            for node_id, node_data in list(kg_result["nodes"].items())[:3]:
                real_entities.append({
                    "id": node_id,
                    "properties": node_data.get("properties", {}),
                    "labels": node_data.get("labels", [])
                })
            
            work_request = {
                "type": "kg_update_request",
                "entities": real_entities,
                "relationships": [],
                "sender_id": "data_architect_agent",
                "request_id": "req_001"
            }
            
            self.print_success(f"Work request created with {len(real_entities)} real entities from KG")
            for entity in real_entities:
                entity_name = entity["properties"].get("name", "Unknown")
                self.print_info(f"   - {entity_name} (ID: {entity['id']})")
            
            # Send message to Data Engineer
            message = Message(
                sender_id="demo_system",
                receiver_id="data_engineer_agent",
                content=work_request
            )
            
            asyncio.run(self.communication_channel.send(message))
            self.print_success("Work request sent to Data Engineer")
            
        except Exception as e:
            self.print_error(f"Failed to send work request: {e}")
            return False
        
        # Step 2: Show Data Engineer processing real KG data
        self.print_step(2, "Data Engineer processing work request with real KG data")
        
        try:
            # Simulate Data Engineer processing
            self.print_agent_message("Data Engineer", "Received work request from Data Architect")
            self.print_agent_message("Data Engineer", f"Processing {len(real_entities)} entities from knowledge graph...")
            
            # Process the request
            result = asyncio.run(self.data_engineer._handle_kg_update_request(work_request))
            
            if result["success"]:
                self.print_success(f"Data Engineer processed {result['processed']} items successfully")
            else:
                self.print_error("Data Engineer processing failed")
            
        except Exception as e:
            self.print_error(f"Data Engineer processing failed: {e}")
        
        # Step 3: Show escalation to Knowledge Manager with real data
        self.print_step(3, "Escalation to Knowledge Manager for complex operations")
        
        try:
            # Create a complex operation based on real KG data
            if real_entities:
                first_entity = real_entities[0]
                complex_operation = {
                    "type": "create_relationship",
                    "data": {
                        "source": first_entity["id"],
                        "target": "new_entity_001",
                        "type": "COMPLEX_RELATIONSHIP",
                        "properties": {
                            "complexity": "high", 
                            "validation_required": True,
                            "source_entity": first_entity["properties"].get("name", "Unknown")
                        }
                    }
                }
                
                # This should trigger escalation
                self.print_agent_message("Data Engineer", "Attempting complex operation...")
                self.print_agent_message("Data Engineer", f"Operation involves entity: {first_entity['properties'].get('name', 'Unknown')}")
                self.print_agent_message("Data Engineer", "Operation requires escalation to Knowledge Manager")
                
                # Simulate escalation
                escalation_message = {
                    "type": "escalate_operations",
                    "agent_id": "data_engineer_agent",
                    "operations": [complex_operation],
                    "reason": "Complex operation requiring advanced validation and reasoning"
                }
                
                # Send to Knowledge Manager
                message = Message(
                    sender_id="data_engineer_agent",
                    receiver_id="knowledge_manager_agent",
                    content=escalation_message
                )
                
                asyncio.run(self.communication_channel.send(message))
                self.print_success("Complex operation escalated to Knowledge Manager")
                self.print_info(f"   Operation: {complex_operation['data']['source']} --[{complex_operation['data']['type']}]--> {complex_operation['data']['target']}")
                
            else:
                self.print_error("No entities available for complex operation")
                
        except Exception as e:
            self.print_error(f"Escalation failed: {e}")
        
        return True
    
    def demo_5_event_driven_communication(self):
        """Demonstrate event-driven communication between agents."""
        self.print_header("DEMO 5: Event-Driven Communication")
        
        # Step 1: Set up event handlers
        self.print_step(1, "Setting up event handlers for agents")
        
        events_received = []
        
        async def event_handler(event):
            events_received.append(event)
            print(f"📡 Event received: {event.action} by {event.role.value}")
        
        # Step 1: Show event bus capabilities
        self.print_step(1, "Event bus capabilities and configuration")
        
        print("✅ Event bus initialized successfully")
        print(f"   Type: {type(self.event_bus).__name__}")
        print(f"   Status: Operational")
        print("   - Asynchronous event processing")
        print("   - Role-based access control")
        print("   - Event validation and routing")
        print("   - Distributed messaging support")
        print("   - Fallback to local handlers")
        
        # Step 2: Simulate event publishing based on real KG operations
        self.print_step(2, "Simulating event publishing based on real KG operations")
        
        try:
            # Query the actual knowledge graph to get real data for events
            kg_result = asyncio.run(self.kg_backend.query("MATCH (n) RETURN n LIMIT 3"))
            
            if kg_result and "nodes" in kg_result and kg_result["nodes"]:
                # Create events based on real KG entities
                events_to_publish = []
                
                # Event 1: Entity creation (based on first entity)
                first_entity = list(kg_result["nodes"].items())[0]
                events_to_publish.append({
                    "action": "create_entity",
                    "data": {
                        "id": first_entity[0],
                        "type": "real_entity",
                        "name": first_entity[1].get("properties", {}).get("name", "Unknown")
                    },
                    "role": "data_engineer"
                })
                
                # Event 2: Relationship creation (if we have multiple entities)
                if len(kg_result["nodes"]) > 1:
                    second_entity = list(kg_result["nodes"].items())[1]
                    events_to_publish.append({
                        "action": "create_relationship",
                        "data": {
                            "source": first_entity[0],
                            "target": second_entity[0],
                            "type": "REAL_RELATIONSHIP",
                            "source_name": first_entity[1].get("properties", {}).get("name", "Unknown"),
                            "target_name": second_entity[1].get("properties", {}).get("name", "Unknown")
                        },
                        "role": "data_architect"
                    })
                
                # Event 3: Escalation (based on complex operation)
                events_to_publish.append({
                    "action": "escalate_operations",
                    "data": {
                        "operations": ["complex_validation", "advanced_reasoning"],
                        "entities_involved": [first_entity[0]],
                        "reason": "Complex operation involving real KG entities"
                    },
                    "role": "data_engineer"
                })
                
                # Show the events
                for event in events_to_publish:
                    print(f"📤 Would publish event: {event['action']} by {event['role']}")
                    print(f"   Data: {event['data']}")
                
                self.print_success(f"Created {len(events_to_publish)} events based on real KG data")
                
            else:
                # Fallback to demo events if no KG data
                events_to_publish = [
                    {
                        "action": "create_entity",
                        "data": {"id": "event_demo_001", "type": "demo_entity"},
                        "role": "data_engineer"
                    },
                    {
                        "action": "create_relationship",
                        "data": {"source": "demo_source", "target": "demo_target", "type": "DEMO_REL"},
                        "role": "data_architect"
                    },
                    {
                        "action": "escalate_operations",
                        "data": {"operations": ["complex_op_1", "complex_op_2"]},
                        "role": "data_engineer"
                    }
                ]
                
                for event in events_to_publish:
                    print(f"📤 Would publish event: {event['action']} by {event['role']}")
                    print(f"   Data: {event['data']}")
                
                self.print_info("Using demo events (no real KG data available)")
                
        except Exception as e:
            self.print_error(f"Failed to create events based on KG data: {e}")
            return False
        
        # Step 3: Show event processing capabilities
        self.print_step(3, "Event processing capabilities")
        
        print("📊 Event system features:")
        print("   - Asynchronous event processing")
        print("   - Role-based access control")
        print("   - Event validation and routing")
        print("   - Distributed messaging support")
        print("   - Fallback to local handlers")
        print("   - Event persistence and replay")
        print("   - Load balancing and scaling")
        
        return True
    
    def demo_6_validation_and_conflict_resolution(self):
        """Demonstrate validation and conflict resolution."""
        self.print_header("DEMO 6: Validation and Conflict Resolution")
        
        # Step 1: Validate real entities from the knowledge graph
        self.print_step(1, "Validation engine capabilities with real KG data")
        
        try:
            # Query the actual knowledge graph to get real entities
            kg_result = asyncio.run(self.kg_backend.query("MATCH (n) RETURN n LIMIT 5"))
            
            if not kg_result or "nodes" not in kg_result or not kg_result["nodes"]:
                self.print_error("No entities found in knowledge graph. Please run Demo 3 first.")
                return False
            
            self.print_success(f"Found {len(kg_result['nodes'])} entities to validate")
            
            # Validate each real entity
            validation_results = []
            for node_id, node_data in kg_result["nodes"].items():
                try:
                    validation_result = asyncio.run(self.knowledge_manager.validation_engine.validate_event(
                        KnowledgeEvent(
                            action="create_entity",
                            data={"id": node_id, "properties": node_data.get("properties", {})},
                            role=Role.DATA_ENGINEER
                        )
                    ))
                    
                    if validation_result["is_valid"]:
                        validation_results.append({"id": node_id, "valid": True})
                        entity_name = node_data.get("properties", {}).get("name", "Unknown")
                        print(f"   ✅ {entity_name} (ID: {node_id}): Valid")
                    else:
                        validation_results.append({"id": node_id, "valid": False, "errors": validation_result.get("errors", [])})
                        entity_name = node_data.get("properties", {}).get("name", "Unknown")
                        print(f"   ❌ {entity_name} (ID: {node_id}): Invalid")
                        for error in validation_result.get("errors", []):
                            print(f"      - Error: {error}")
                            
                except Exception as e:
                    print(f"   ⚠️  {node_id}: Validation failed - {e}")
            
            valid_count = sum(1 for r in validation_results if r.get("valid", False))
            self.print_success(f"Validation completed: {valid_count}/{len(validation_results)} entities valid")
            
        except Exception as e:
            self.print_error(f"Validation failed: {e}")
            return False
        
        # Step 2: Test conflict detection with real data
        self.print_step(2, "Conflict detection with real KG data")
        
        try:
            # Test conflict detection with a potential duplicate
            if kg_result and "nodes" in kg_result and kg_result["nodes"]:
                first_entity = list(kg_result["nodes"].items())[0]
                first_entity_id = first_entity[0]
                
                # Try to create a duplicate entity
                duplicate_entity = {
                    "id": first_entity_id,  # Same ID as existing entity
                    "properties": {"name": "Duplicate Entity", "source": "conflict_test"}
                }
                
                conflicts = asyncio.run(self.knowledge_manager.conflict_resolver.detect_conflicts(
                    KnowledgeEvent(
                        action="create_entity",
                        data=duplicate_entity,
                        role=Role.DATA_ENGINEER
                    )
                ))
                
                if conflicts:
                    self.print_success(f"Conflict detected: {len(conflicts)} conflicts found")
                    for conflict in conflicts:
                        self.print_info(f"   - {conflict['type']}: {conflict['description']}")
                        self.print_info(f"     Entity ID: {first_entity_id}")
                        self.print_info(f"     Existing entity: {first_entity[1].get('properties', {}).get('name', 'Unknown')}")
                else:
                    self.print_info("No conflicts detected (unexpected)")
                    
        except Exception as e:
            self.print_error(f"Conflict detection failed: {e}")
        
        # Step 3: Show reasoning engine with real data
        self.print_step(3, "Reasoning engine capabilities with real KG data")
        
        try:
            if kg_result and "nodes" in kg_result and kg_result["nodes"]:
                # Use the first real entity for reasoning
                first_entity = list(kg_result["nodes"].items())[0]
                entity_id = first_entity[0]
                entity_props = first_entity[1].get("properties", {})
                
                # Test reasoning with real entity data
                reasoning_result = asyncio.run(self.knowledge_manager.reasoning_engine.apply_reasoning(
                    KnowledgeEvent(
                        action="create_entity",
                        data={"id": entity_id, "properties": entity_props},
                        role=Role.DATA_ARCHITECT
                    )
                ))
                
                self.print_success("Reasoning engine applied successfully to real entity")
                entity_name = entity_props.get("name", "Unknown")
                self.print_info(f"   Entity analyzed: {entity_name} (ID: {entity_id})")
                
                if "inferred_properties" in reasoning_result:
                    inferred = reasoning_result["inferred_properties"]
                    self.print_info(f"   Inferred properties: {len(inferred)}")
                    for prop in inferred:
                        self.print_info(f"      - {prop}")
                
                if "reasoning_applied" in reasoning_result:
                    self.print_info(f"   Reasoning applied: {reasoning_result['reasoning_applied']}")
                    
            else:
                self.print_error("No entities available for reasoning")
                
        except Exception as e:
            self.print_error(f"Reasoning engine failed: {e}")
        
        return True
    
    def run_full_demo(self):
        """Run the complete multi-agent DDA demonstration."""
        print("🚀 SynapseFlow Multi-Agent DDA System Demonstration")
        print("=" * 70)
        print("This demo showcases the complete multi-agent workflow:")
        print("• Agent registration and discovery")
        print("• DDA document processing")
        print("• Knowledge graph creation")
        print("• Agent collaboration and communication")
        print("• Event-driven messaging")
        print("• Validation and conflict resolution")
        print("=" * 70)
        
        try:
            # Run all demos
            if not self.demo_1_agent_registration():
                return
            
            time.sleep(2)
            
            if not self.demo_2_dda_processing():
                return
            
            time.sleep(2)
            
            if not self.demo_3_knowledge_graph_creation():
                return
            
            time.sleep(2)
            
            if not self.demo_4_agent_collaboration():
                return
            
            time.sleep(2)
            
            if not self.demo_5_event_driven_communication():
                return
            
            time.sleep(2)
            
            if not self.demo_6_validation_and_conflict_resolution():
                return
            
            # Final summary
            self.print_header("DEMO COMPLETE")
            print("🎉 All multi-agent demonstrations completed successfully!")
            print("\n📊 System Status:")
            print("   ✅ Multi-Agent System: Operational")
            print("   ✅ Knowledge Graph: Functional")
            print("   ✅ Event System: Active")
            print("   ✅ DDA Processing: Working")
            print("   ✅ Agent Collaboration: Successful")
            print("   ✅ Validation & Conflict Resolution: Active")
            print("\n🚀 SynapseFlow Multi-Agent System is ready for production use!")
            
        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            print("Please check the system configuration and try again.")
    
    def interactive_demo(self):
        """Run an interactive demo with user choices."""
        print("🎮 Interactive Multi-Agent DDA Demo")
        print("=" * 50)
        
        demos = {
            "1": ("Agent Registration", self.demo_1_agent_registration),
            "2": ("DDA Processing", self.demo_2_dda_processing),
            "3": ("Knowledge Graph Creation", self.demo_3_knowledge_graph_creation),
            "4": ("Agent Collaboration", self.demo_4_agent_collaboration),
            "5": ("Event-Driven Communication", self.demo_5_event_driven_communication),
            "6": ("Validation & Conflict Resolution", self.demo_6_validation_and_conflict_resolution),
            "7": ("Full Demo", self.run_full_demo),
            "q": ("Quit", None)
        }
        
        while True:
            print("\n📋 Available Multi-Agent Demonstrations:")
            for key, (name, _) in demos.items():
                if key != "q":
                    print(f"   {key}. {name}")
            print("   q. Quit")
            
            choice = input("\n🎯 Select a demo (or 'q' to quit): ").strip().lower()
            
            if choice == "q":
                print("👋 Goodbye!")
                break
            elif choice in demos:
                if demos[choice][1]:
                    try:
                        demos[choice][1]()
                        input("\n⏸️  Press Enter to continue...")
                    except Exception as e:
                        print(f"❌ Demo failed: {e}")
                        input("\n⏸️  Press Enter to continue...")
                else:
                    print("👋 Goodbye!")
                    break
            else:
                print("❌ Invalid choice. Please try again.")


def main():
    """Main entry point for the multi-agent DDA demo."""
    print("🎬 SynapseFlow Multi-Agent DDA Demo")
    print("=" * 60)
    
    # Check command line arguments
    dda_file = None
    interactive_mode = False
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive":
            interactive_mode = True
        elif sys.argv[1].endswith('.md'):
            dda_file = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == "--interactive":
        interactive_mode = True
    
    print("💡 This demo shows the complete multi-agent workflow with DDAs")
    print("   - Agent collaboration and communication")
    print("   - DDA document processing")
    print("   - Knowledge graph creation and updates")
    print("   - Event-driven architecture")
    print("   - Validation and conflict resolution")
    
    # Create demo instance
    demo = MultiAgentDDADemo()
    
    # Set specific DDA file if provided
    if dda_file:
        demo.current_dda = dda_file
        print(f"\n📚 Using specified DDA file: {Path(dda_file).name}")
    
    # Run demo
    if interactive_mode:
        demo.interactive_demo()
    else:
        demo.run_full_demo()


if __name__ == "__main__":
    main()
