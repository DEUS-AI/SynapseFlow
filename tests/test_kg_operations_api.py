"""Tests for the Knowledge Graph Operations API."""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from fastapi.testclient import TestClient
from interfaces.kg_operations_api import app, initialize_api
from infrastructure.in_memory_backend import InMemoryGraphBackend
from application.event_bus import EventBus


class TestKGOperationsAPI(unittest.TestCase):
    """Test cases for the Knowledge Graph Operations API."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test dependencies
        self.kg_backend = InMemoryGraphBackend()
        self.event_bus = EventBus()
        
        # Initialize the API with test dependencies
        initialize_api(self.kg_backend, self.event_bus)
        
        # Create test client
        self.client = TestClient(app)

    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("timestamp", data)
        self.assertIn("backend_status", data)
        self.assertIn("event_bus_status", data)
        
        # Backend should be healthy
        self.assertEqual(data["backend_status"]["status"], "healthy")

    def test_create_entity(self):
        """Test creating an entity."""
        entity_data = {
            "id": "test_entity_1",
            "properties": {"name": "Test Entity", "type": "test"},
            "labels": ["test", "entity"]
        }
        
        response = self.client.post("/entities", json=entity_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["id"], "test_entity_1")
        self.assertEqual(data["properties"]["name"], "Test Entity")
        self.assertEqual(data["labels"], ["test", "entity"])
        self.assertIn("created_at", data)

    def test_create_entity_invalid_id(self):
        """Test creating an entity with invalid ID."""
        entity_data = {
            "id": "",  # Empty ID
            "properties": {"name": "Test Entity"}
        }
        
        response = self.client.post("/entities", json=entity_data)
        self.assertEqual(response.status_code, 422)  # Validation error

    def test_get_entity(self):
        """Test getting an entity by ID."""
        # First create an entity
        entity_data = {
            "id": "test_entity_2",
            "properties": {"name": "Test Entity 2"}
        }
        self.client.post("/entities", json=entity_data)
        
        # Now get it
        response = self.client.get("/entities/test_entity_2")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["id"], "test_entity_2")
        self.assertEqual(data["properties"]["name"], "Test Entity 2")

    def test_get_entity_not_found(self):
        """Test getting a non-existent entity."""
        response = self.client.get("/entities/non_existent")
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"])

    def test_update_entity(self):
        """Test updating an entity."""
        # First create an entity
        entity_data = {
            "id": "test_entity_3",
            "properties": {"name": "Original Name"}
        }
        self.client.post("/entities", json=entity_data)
        
        # Update it
        update_data = {
            "properties": {"name": "Updated Name", "status": "active"},
            "labels": ["updated", "entity"]
        }
        
        response = self.client.put("/entities/test_entity_3", json=update_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["properties"]["name"], "Updated Name")
        self.assertEqual(data["properties"]["status"], "active")
        self.assertEqual(data["labels"], ["updated", "entity"])
        self.assertIn("updated_at", data)

    def test_update_entity_not_found(self):
        """Test updating a non-existent entity."""
        update_data = {
            "properties": {"name": "Updated Name"}
        }
        
        response = self.client.put("/entities/non_existent", json=update_data)
        self.assertEqual(response.status_code, 404)

    def test_delete_entity(self):
        """Test deleting an entity."""
        # First create an entity
        entity_data = {
            "id": "test_entity_4",
            "properties": {"name": "To Be Deleted"}
        }
        self.client.post("/entities", json=entity_data)
        
        # Delete it
        response = self.client.delete("/entities/test_entity_4")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("deleted successfully", data["message"])

    def test_delete_entity_not_found(self):
        """Test deleting a non-existent entity."""
        response = self.client.delete("/entities/non_existent")
        self.assertEqual(response.status_code, 404)

    def test_list_entities(self):
        """Test listing entities with pagination."""
        # Create multiple entities
        for i in range(5):
            entity_data = {
                "id": f"list_entity_{i}",
                "properties": {"name": f"Entity {i}"}
            }
            self.client.post("/entities", json=entity_data)
        
        # List entities with limit
        response = self.client.get("/entities?limit=3")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertLessEqual(len(data), 3)

    def test_create_relationship(self):
        """Test creating a relationship."""
        # First create source and target entities
        source_entity = {"id": "source_entity", "properties": {"name": "Source"}}
        target_entity = {"id": "target_entity", "properties": {"name": "Target"}}
        
        self.client.post("/entities", json=source_entity)
        self.client.post("/entities", json=target_entity)
        
        # Create relationship
        relationship_data = {
            "source": "source_entity",
            "target": "target_entity",
            "type": "RELATES_TO",
            "properties": {"strength": "high"}
        }
        
        response = self.client.post("/relationships", json=relationship_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["source"], "source_entity")
        self.assertEqual(data["target"], "target_entity")
        self.assertEqual(data["type"], "RELATES_TO")
        self.assertEqual(data["properties"]["strength"], "high")

    def test_create_relationship_missing_entity(self):
        """Test creating a relationship with missing source entity."""
        # Only create target entity
        target_entity = {"id": "target_entity", "properties": {"name": "Target"}}
        self.client.post("/entities", json=target_entity)
        
        # Try to create relationship with non-existent source
        relationship_data = {
            "source": "non_existent_source",
            "target": "target_entity",
            "type": "RELATES_TO"
        }
        
        response = self.client.post("/relationships", json=relationship_data)
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn("Source entity", data["detail"])

    def test_list_relationships(self):
        """Test listing relationships with filtering."""
        # Create entities and relationships
        for i in range(3):
            entity = {"id": f"rel_entity_{i}", "properties": {"name": f"Entity {i}"}}
            self.client.post("/entities", json=entity)
        
        # Create relationships
        relationships = [
            {"source": "rel_entity_0", "target": "rel_entity_1", "type": "RELATES_TO"},
            {"source": "rel_entity_1", "target": "rel_entity_2", "type": "RELATES_TO"},
            {"source": "rel_entity_0", "target": "rel_entity_2", "type": "DIFFERENT_TYPE"}
        ]
        
        for rel in relationships:
            self.client.post("/relationships", json=rel)
        
        # List relationships with type filter
        response = self.client.get("/relationships?rel_type=RELATES_TO")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertGreater(len(data), 0)
        
        # All returned relationships should have the correct type
        for rel in data:
            self.assertEqual(rel["type"], "RELATES_TO")

    def test_batch_operations(self):
        """Test batch operations."""
        batch_data = {
            "operations": [
                {
                    "type": "create_entity",
                    "data": {"id": "batch_entity_1", "properties": {"name": "Batch 1"}}
                },
                {
                    "type": "create_entity",
                    "data": {"id": "batch_entity_2", "properties": {"name": "Batch 2"}}
                },
                {
                    "type": "create_relationship",
                    "data": {
                        "source": "batch_entity_1",
                        "target": "batch_entity_2",
                        "type": "RELATES_TO"
                    }
                }
            ],
            "transaction": True
        }
        
        response = self.client.post("/batch", json=batch_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["total_operations"], 3)
        self.assertEqual(data["successful"], 3)
        self.assertEqual(data["failed"], 0)

    def test_batch_operations_with_errors(self):
        """Test batch operations with some failing operations."""
        batch_data = {
            "operations": [
                {
                    "type": "create_entity",
                    "data": {"id": "batch_entity_3", "properties": {"name": "Batch 3"}}
                },
                {
                    "type": "unknown_operation",  # This will fail
                    "data": {"id": "invalid"}
                }
            ]
        }
        
        response = self.client.post("/batch", json=batch_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["total_operations"], 2)
        self.assertEqual(data["successful"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertGreater(len(data["errors"]), 0)

    def test_execute_query(self):
        """Test executing a query."""
        # Create some test data
        entity_data = {"id": "query_entity", "properties": {"name": "Query Test"}}
        self.client.post("/entities", json=entity_data)
        
        query_data = {
            "query": "MATCH (n) RETURN n",
            "parameters": {}
        }
        
        response = self.client.post("/query", json=query_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("execution_time", data)
        self.assertIn("result_count", data)
        self.assertGreater(data["result_count"], 0)

    def test_publish_event(self):
        """Test publishing a custom event."""
        event_data = {
            "action": "custom_action",
            "data": {"custom": "data"},
            "role": "data_engineer"
        }
        
        response = self.client.post("/events", json=event_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("Event published successfully", data["message"])
        self.assertIn("event_id", data)

    def test_publish_event_invalid_role(self):
        """Test publishing an event with invalid role."""
        event_data = {
            "action": "custom_action",
            "data": {"custom": "data"},
            "role": "invalid_role"
        }
        
        response = self.client.post("/events", json=event_data)
        self.assertEqual(response.status_code, 400)
        
        data = response.json()
        self.assertIn("Invalid role", data["detail"])

    def test_get_statistics(self):
        """Test getting knowledge graph statistics."""
        # Create some test data
        for i in range(3):
            entity = {"id": f"stats_entity_{i}", "properties": {"name": f"Stats Entity {i}"}}
            self.client.post("/entities", json=entity)
        
        # Create a relationship
        relationship = {
            "source": "stats_entity_0",
            "target": "stats_entity_1",
            "type": "RELATES_TO"
        }
        self.client.post("/relationships", json=relationship)
        
        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("entity_count", data)
        self.assertIn("relationship_count", data)
        self.assertIn("total_nodes", data)
        self.assertIn("total_edges", data)
        self.assertIn("timestamp", data)
        
        # Should have at least 3 entities and 1 relationship
        self.assertGreaterEqual(data["entity_count"], 3)
        self.assertGreaterEqual(data["relationship_count"], 1)

    def test_api_documentation(self):
        """Test that API documentation is accessible."""
        # Test OpenAPI schema
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        
        # Test Swagger UI
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        
        # Test ReDoc
        response = self.client.get("/redoc")
        self.assertEqual(response.status_code, 200)

    def test_cors_headers(self):
        """Test that CORS headers are properly set."""
        # CORS preflight request requires Origin header
        response = self.client.options(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        # CORS preflight request should work
        self.assertIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
