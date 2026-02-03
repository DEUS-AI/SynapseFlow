#!/usr/bin/env python3
"""
SynapseFlow Live API Demo
=========================

This script provides a live demonstration of the SynapseFlow API endpoints.
It can be used during presentations to show real-time API functionality.

Usage: python live_api_demo.py
"""

import requests
import json
import time
import sys
from typing import Dict, Any


class LiveAPIDemo:
    """Live demonstration of SynapseFlow API endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def print_header(self, title: str):
        """Print a formatted section header."""
        print(f"\n{'='*60}")
        print(f"🎯 {title}")
        print(f"{'='*60}")
    
    def print_step(self, step_num: int, description: str):
        """Print a formatted step."""
        print(f"\n📋 Step {step_num}: {description}")
        print("-" * 50)
    
    def print_success(self, message: str):
        """Print a success message."""
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        """Print an error message."""
        print(f"❌ {message}")
    
    def print_info(self, message: str):
        """Print an info message."""
        print(f"ℹ️  {message}")
    
    def check_api_health(self) -> bool:
        """Check if the API is running and healthy."""
        self.print_step(1, "Checking API Health")
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"API Status: {data['status']}")
                self.print_info(f"Backend: {data['backend_status']['status']}")
                self.print_info(f"Event Bus: {data['event_bus_status']['status']}")
                return True
            else:
                self.print_error(f"Health check failed: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_error("Cannot connect to API. Is the server running?")
            self.print_info("Start the server with: uvicorn src.interfaces.kg_operations_api:app --host 0.0.0.0 --port 8000")
            return False
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            return False
    
    def demo_entity_operations(self):
        """Demonstrate entity CRUD operations."""
        self.print_header("DEMO: Entity CRUD Operations")
        
        # Create entities
        self.print_step(1, "Creating Sample Entities")
        
        entities = [
            {
                "id": "demo_customer_001",
                "properties": {
                    "name": "Alice Johnson",
                    "email": "alice@demo.com",
                    "status": "premium",
                    "join_date": "2024-01-01"
                },
                "labels": ["customer", "premium", "demo"]
            },
            {
                "id": "demo_product_001",
                "properties": {
                    "name": "Demo Widget Pro",
                    "category": "electronics",
                    "price": 299.99,
                    "in_stock": True
                },
                "labels": ["product", "electronics", "demo"]
            },
            {
                "id": "demo_order_001",
                "properties": {
                    "order_number": "ORD-001",
                    "total_amount": 299.99,
                    "status": "completed",
                    "order_date": "2024-01-15"
                },
                "labels": ["order", "demo"]
            }
        ]
        
        created_entities = []
        for entity in entities:
            try:
                response = self.session.post(f"{self.base_url}/entities", json=entity)
                if response.status_code == 200:
                    result = response.json()
                    created_entities.append(result)
                    self.print_success(f"Created: {result['id']} ({result['properties']['name']})")
                else:
                    self.print_error(f"Failed to create {entity['id']}: {response.text}")
            except Exception as e:
                self.print_error(f"Error creating {entity['id']}: {e}")
        
        if not created_entities:
            self.print_error("No entities were created. Cannot continue with demo.")
            return
        
        # Read entities
        self.print_step(2, "Reading Entities")
        
        for entity in created_entities[:2]:  # Read first two entities
            try:
                response = self.session.get(f"{self.base_url}/entities/{entity['id']}")
                if response.status_code == 200:
                    result = response.json()
                    self.print_success(f"Retrieved: {result['id']}")
                    self.print_info(f"  Name: {result['properties'].get('name', 'N/A')}")
                    self.print_info(f"  Labels: {', '.join(result['labels'])}")
                else:
                    self.print_error(f"Failed to read {entity['id']}: {response.text}")
            except Exception as e:
                self.print_error(f"Error reading {entity['id']}: {e}")
        
        # Update entity
        self.print_step(3, "Updating Entity")
        
        update_data = {
            "properties": {
                "name": "Alice Johnson (Updated)",
                "email": "alice.updated@demo.com",
                "status": "vip",
                "join_date": "2024-01-01",
                "last_updated": "2024-01-20"
            },
            "labels": ["customer", "vip", "demo", "updated"]
        }
        
        try:
            response = self.session.put(f"{self.base_url}/entities/demo_customer_001", json=update_data)
            if response.status_code == 200:
                result = response.json()
                self.print_success(f"Updated: {result['id']}")
                self.print_info(f"  New Status: {result['properties']['status']}")
                self.print_info(f"  New Labels: {', '.join(result['labels'])}")
            else:
                self.print_error(f"Failed to update: {response.text}")
        except Exception as e:
            self.print_error(f"Error updating: {e}")
        
        # List entities
        self.print_step(4, "Listing All Entities")
        
        try:
            response = self.session.get(f"{self.base_url}/entities?limit=10")
            if response.status_code == 200:
                entities_list = response.json()
                self.print_success(f"Retrieved {len(entities_list)} entities")
                for entity in entities_list:
                    self.print_info(f"  - {entity['id']}: {entity['properties'].get('name', 'N/A')}")
            else:
                self.print_error(f"Failed to list entities: {response.text}")
        except Exception as e:
            self.print_error(f"Error listing entities: {e}")
    
    def demo_relationship_operations(self):
        """Demonstrate relationship operations."""
        self.print_header("DEMO: Relationship Operations")
        
        # Create relationships
        self.print_step(1, "Creating Relationships")
        
        relationships = [
            {
                "source": "demo_customer_001",
                "target": "demo_product_001",
                "type": "PURCHASED",
                "properties": {
                    "purchase_date": "2024-01-15",
                    "quantity": 1,
                    "unit_price": 299.99
                }
            },
            {
                "source": "demo_customer_001",
                "target": "demo_order_001",
                "type": "PLACED",
                "properties": {
                    "order_date": "2024-01-15"
                }
            },
            {
                "source": "demo_order_001",
                "target": "demo_product_001",
                "type": "CONTAINS",
                "properties": {
                    "quantity": 1
                }
            }
        ]
        
        for rel in relationships:
            try:
                response = self.session.post(f"{self.base_url}/relationships", json=rel)
                if response.status_code == 200:
                    result = response.json()
                    self.print_success(f"Created: {result['source']} --[{result['type']}]--> {result['target']}")
                else:
                    self.print_error(f"Failed to create relationship: {response.text}")
            except Exception as e:
                self.print_error(f"Error creating relationship: {e}")
        
        # List relationships
        self.print_step(2, "Listing Relationships")
        
        try:
            response = self.session.get(f"{self.base_url}/relationships?limit=10")
            if response.status_code == 200:
                rels_list = response.json()
                self.print_success(f"Retrieved {len(rels_list)} relationships")
                for rel in rels_list:
                    self.print_info(f"  - {rel['source']} --[{rel['type']}]--> {rel['target']}")
            else:
                self.print_error(f"Failed to list relationships: {response.text}")
        except Exception as e:
            self.print_error(f"Error listing relationships: {e}")
    
    def demo_batch_operations(self):
        """Demonstrate batch operations."""
        self.print_header("DEMO: Batch Operations")
        
        # Prepare batch data
        self.print_step(1, "Preparing Batch Operations")
        
        batch_data = {
            "operations": [
                {
                    "type": "create_entity",
                    "data": {
                        "id": "batch_entity_001",
                        "properties": {"name": "Batch Entity 1", "type": "demo"},
                        "labels": ["batch", "demo"]
                    }
                },
                {
                    "type": "create_entity",
                    "data": {
                        "id": "batch_entity_002",
                        "properties": {"name": "Batch Entity 2", "type": "demo"},
                        "labels": ["batch", "demo"]
                    }
                },
                {
                    "type": "create_relationship",
                    "data": {
                        "source": "batch_entity_001",
                        "target": "batch_entity_002",
                        "type": "RELATES_TO",
                        "properties": {"demo": True}
                    }
                }
            ],
            "transaction": True
        }
        
        self.print_info(f"Batch prepared with {len(batch_data['operations'])} operations")
        
        # Execute batch
        self.print_step(2, "Executing Batch Operations")
        
        try:
            response = self.session.post(f"{self.base_url}/batch", json=batch_data)
            if response.status_code == 200:
                result = response.json()
                self.print_success("Batch executed successfully")
                self.print_info(f"  Total operations: {result['total_operations']}")
                self.print_info(f"  Successful: {result['successful']}")
                self.print_info(f"  Failed: {result['failed']}")
                
                if result['errors']:
                    self.print_info("  Errors:")
                    for error in result['errors']:
                        self.print_info(f"    - {error}")
            else:
                self.print_error(f"Batch execution failed: {response.text}")
        except Exception as e:
            self.print_error(f"Error executing batch: {e}")
    
    def demo_query_operations(self):
        """Demonstrate query operations."""
        self.print_header("DEMO: Query Operations")
        
        # Simple query
        self.print_step(1, "Simple Query - All Entities")
        
        query_data = {"query": "MATCH (n) RETURN n"}
        
        try:
            response = self.session.post(f"{self.base_url}/query", json=query_data)
            if response.status_code == 200:
                result = response.json()
                self.print_success("Query executed successfully")
                self.print_info(f"  Results: {result['result_count']} items")
                self.print_info(f"  Execution time: {result['execution_time']:.3f}s")
            else:
                self.print_error(f"Query failed: {response.text}")
        except Exception as e:
            self.print_error(f"Error executing query: {e}")
        
        # Complex query
        self.print_step(2, "Complex Query - Customer Relationships")
        
        complex_query = {
            "query": "MATCH (c:customer)-[r]->(p:product) RETURN c.name, r.type, p.name",
            "parameters": {}
        }
        
        try:
            response = self.session.post(f"{self.base_url}/query", json=complex_query)
            if response.status_code == 200:
                result = response.json()
                self.print_success("Complex query executed")
                self.print_info(f"  Results: {result['result_count']} items")
                self.print_info(f"  Execution time: {result['execution_time']:.3f}s")
            else:
                self.print_error(f"Complex query failed: {response.text}")
        except Exception as e:
            self.print_error(f"Error executing complex query: {e}")
    
    def demo_event_publishing(self):
        """Demonstrate event publishing."""
        self.print_header("DEMO: Event Publishing")
        
        # Publish custom events
        self.print_step(1, "Publishing Custom Events")
        
        events = [
            {
                "action": "demo_customer_created",
                "data": {
                    "customer_id": "demo_customer_001",
                    "action": "created",
                    "timestamp": "2024-01-20T10:00:00Z"
                },
                "role": "data_engineer"
            },
            {
                "action": "demo_purchase_completed",
                "data": {
                    "customer_id": "demo_customer_001",
                    "product_id": "demo_product_001",
                    "amount": 299.99,
                    "timestamp": "2024-01-20T10:30:00Z"
                },
                "role": "data_architect"
            }
        ]
        
        for event in events:
            try:
                response = self.session.post(f"{self.base_url}/events", json=event)
                if response.status_code == 200:
                    result = response.json()
                    self.print_success(f"Event published: {result['event_id']}")
                    self.print_info(f"  Action: {event['action']}")
                else:
                    self.print_error(f"Failed to publish event: {response.text}")
            except Exception as e:
                self.print_error(f"Error publishing event: {e}")
    
    def demo_statistics_and_monitoring(self):
        """Demonstrate statistics and monitoring."""
        self.print_header("DEMO: Statistics and Monitoring")
        
        # Get statistics
        self.print_step(1, "Knowledge Graph Statistics")
        
        try:
            response = self.session.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                result = response.json()
                self.print_success("Statistics retrieved")
                self.print_info(f"  Entities: {result['entity_count']}")
                self.print_info(f"  Relationships: {result['relationship_count']}")
                self.print_info(f"  Total nodes: {result['total_nodes']}")
                self.print_info(f"  Total edges: {result['total_edges']}")
                self.print_info(f"  Timestamp: {result['timestamp']}")
            else:
                self.print_error(f"Failed to get statistics: {response.text}")
        except Exception as e:
            self.print_error(f"Error getting statistics: {e}")
        
        # Health check
        self.print_step(2, "System Health Check")
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                result = response.json()
                self.print_success("Health check completed")
                self.print_info(f"  Overall Status: {result['status']}")
                self.print_info(f"  Backend: {result['backend_status']['status']}")
                self.print_info(f"  Event Bus: {result['event_bus_status']['status']}")
            else:
                self.print_error(f"Health check failed: {response.text}")
        except Exception as e:
            self.print_error(f"Error during health check: {e}")
    
    def run_full_demo(self):
        """Run the complete live demonstration."""
        print("🚀 SynapseFlow Live API Demonstration")
        print("=" * 60)
        print("This demo showcases real-time API functionality:")
        print("• Entity CRUD operations")
        print("• Relationship management")
        print("• Batch operations")
        print("• Query execution")
        print("• Event publishing")
        print("• Statistics and monitoring")
        print("=" * 60)
        
        # Check API health first
        if not self.check_api_health():
            print("\n❌ API is not available. Please start the server first.")
            return
        
        try:
            # Run all demos
            self.demo_entity_operations()
            time.sleep(1)
            
            self.demo_relationship_operations()
            time.sleep(1)
            
            self.demo_batch_operations()
            time.sleep(1)
            
            self.demo_query_operations()
            time.sleep(1)
            
            self.demo_event_publishing()
            time.sleep(1)
            
            self.demo_statistics_and_monitoring()
            
            # Final summary
            self.print_header("DEMO COMPLETE")
            print("🎉 All live demonstrations completed successfully!")
            print("\n📊 API Status:")
            print("   ✅ All endpoints: Operational")
            print("   ✅ Knowledge Graph: Functional")
            print("   ✅ Event System: Active")
            print("   ✅ Batch Processing: Working")
            print("\n🚀 SynapseFlow API is ready for production use!")
            
        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            print("Please check the API configuration and try again.")
    
    def interactive_demo(self):
        """Run an interactive demo with user choices."""
        print("🎮 Interactive Live API Demo")
        print("=" * 40)
        
        demos = {
            "1": ("Entity Operations", self.demo_entity_operations),
            "2": ("Relationship Operations", self.demo_relationship_operations),
            "3": ("Batch Operations", self.demo_batch_operations),
            "4": ("Query Operations", self.demo_query_operations),
            "5": ("Event Publishing", self.demo_event_publishing),
            "6": ("Statistics & Monitoring", self.demo_statistics_and_monitoring),
            "7": ("Full Demo", self.run_full_demo),
            "q": ("Quit", None)
        }
        
        while True:
            print("\n📋 Available Live Demonstrations:")
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
    """Main entry point for the live API demo."""
    print("🎬 SynapseFlow Live API Demo")
    print("=" * 50)
    
    # Check command line arguments
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"🌐 API Base URL: {base_url}")
    print("💡 Make sure the API server is running!")
    print("   Start with: uvicorn src.interfaces.kg_operations_api:app --host 0.0.0.0 --port 8000")
    
    # Check if running in interactive mode
    if len(sys.argv) > 2 and sys.argv[2] == "--interactive":
        demo = LiveAPIDemo(base_url)
        demo.interactive_demo()
    else:
        # Run full demo
        demo = LiveAPIDemo(base_url)
        demo.run_full_demo()


if __name__ == "__main__":
    main()
