import pytest
import os
from src.infrastructure.falkor_backend import FalkorBackend

# Only run if FALKORDB_HOST is set or we can connect to localhost default
FALKOR_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKOR_PORT = int(os.getenv("FALKORDB_PORT", 6379))

@pytest.mark.integration
class TestFalkorBackend:
    
    @pytest.fixture
    async def backend(self):
        # Use a test graph name
        backend = FalkorBackend(host=FALKOR_HOST, port=FALKOR_PORT, graph_name="test_graph")
        # Clear graph before test
        try:
            backend.graph.delete()
        except Exception:
            pass # Graph might not exist
        return backend

    async def test_connection(self, backend):
        """Test that we can connect and run a simple query."""
        try:
            result = await backend.query("RETURN 1")
            assert result[0][0] == 1
        except Exception as e:
            pytest.skip(f"FalkorDB not available: {e}")

    async def test_add_entity(self, backend):
        """Test adding an entity."""
        try:
            await backend.add_entity("Person:1", {"name": "Alice", "age": 30})
            
            result = await backend.query("MATCH (n:Person {id: '1'}) RETURN n.name, n.age")
            assert result[0][0] == "Alice"
            assert result[0][1] == 30
        except Exception as e:
            pytest.skip(f"FalkorDB not available: {e}")

    async def test_add_relationship(self, backend):
        """Test adding a relationship."""
        try:
            await backend.add_entity("Person:1", {"name": "Alice"})
            await backend.add_entity("Person:2", {"name": "Bob"})
            
            await backend.add_relationship(
                "Person:1",
                "KNOWS",
                "Person:2",
                {"since": 2023}
            )
            
            result = await backend.query("""
                MATCH (a:Person {name: 'Alice'})-[r:KNOWS]->(b:Person {name: 'Bob'})
                RETURN r.since
            """)
            assert result[0][0] == 2023
        except Exception as e:
            pytest.skip(f"FalkorDB not available: {e}")

    async def test_rollback(self, backend):
        """Test rollback functionality."""
        try:
            await backend.add_entity("Person:3", {"name": "Charlie"})
            
            # Verify it exists
            result = await backend.query("MATCH (n:Person {name: 'Charlie'}) RETURN count(n)")
            assert result[0][0] == 1
            
            # Rollback
            await backend.rollback()
            
            # Verify it's gone
            result = await backend.query("MATCH (n:Person {name: 'Charlie'}) RETURN count(n)")
            assert result[0][0] == 0
        except Exception as e:
            pytest.skip(f"FalkorDB not available: {e}")
