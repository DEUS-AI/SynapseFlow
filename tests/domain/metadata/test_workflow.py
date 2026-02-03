"""Tests for workflow metadata models."""

import unittest
from datetime import datetime, timezone
from domain.metadata.workflow import User, AirflowDag


class TestUser(unittest.TestCase):
    """Test cases for User model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User(
            name="Test User",
            username="testuser",
            role="data_engineer"
        )
    
    def test_user_creation(self):
        """Test that user is created with correct attributes."""
        self.assertEqual(self.user.name, "Test User")
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.role, "data_engineer")
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.permissions, [])
        self.assertEqual(self.user.read_entities, [])
        self.assertEqual(self.user.write_entities, [])
        self.assertEqual(self.user.owned_entities, [])
    
    def test_user_default_values(self):
        """Test user default values."""
        minimal_user = User(
            name="minimal_user",
            username="minimal_user",
            role="viewer"  # Required field
        )
        self.assertTrue(minimal_user.is_active)
        self.assertEqual(minimal_user.permissions, [])
        self.assertEqual(minimal_user.read_entities, [])
        self.assertEqual(minimal_user.write_entities, [])
        self.assertEqual(minimal_user.owned_entities, [])
        self.assertEqual(minimal_user.email, None)
        self.assertEqual(minimal_user.full_name, None)
        self.assertEqual(minimal_user.department, None)
    
    def test_user_with_custom_properties(self):
        """Test user with custom properties."""
        user = User(
            name="Custom User",
            username="customuser",
            role="admin"
        )
        user.set_property("department", "IT")
        user.set_property("location", "HQ")
        
        self.assertEqual(user.get_property("department"), "IT")
        self.assertEqual(user.get_property("location"), "HQ")
    
    def test_add_permission(self):
        """Test adding permission to user."""
        self.user.add_permission("read")
        self.user.add_permission("write")
        self.assertIn("read", self.user.permissions)
        self.assertIn("write", self.user.permissions)
    
    def test_remove_permission(self):
        """Test removing permission from user."""
        self.user.add_permission("read")
        self.user.add_permission("write")
        self.user.remove_permission("read")
        
        self.assertNotIn("read", self.user.permissions)
        self.assertIn("write", self.user.permissions)
    
    def test_add_read_entity(self):
        """Test adding read entity to user."""
        self.user.add_read_entity("table-001")
        self.user.add_read_entity("table-002")
        self.assertIn("table-001", self.user.read_entities)
        self.assertIn("table-002", self.user.read_entities)
    
    def test_remove_read_entity(self):
        """Test removing read entity from user."""
        self.user.add_read_entity("table-001")
        self.user.add_read_entity("table-002")
        self.user.remove_read_entity("table-001")
        
        self.assertNotIn("table-001", self.user.read_entities)
        self.assertIn("table-002", self.user.read_entities)
    
    def test_add_write_entity(self):
        """Test adding write entity to user."""
        self.user.add_write_entity("table-001")
        self.user.add_write_entity("table-002")
        self.assertIn("table-001", self.user.write_entities)
        self.assertIn("table-002", self.user.write_entities)
    
    def test_remove_write_entity(self):
        """Test removing write entity from user."""
        self.user.add_write_entity("table-001")
        self.user.add_write_entity("table-002")
        self.user.remove_write_entity("table-001")
        
        self.assertNotIn("table-001", self.user.write_entities)
        self.assertIn("table-002", self.user.write_entities)
    
    def test_add_owned_entity(self):
        """Test adding owned entity to user."""
        self.user.add_owned_entity("table-001")
        self.user.add_owned_entity("table-002")
        self.assertIn("table-001", self.user.owned_entities)
        self.assertIn("table-002", self.user.owned_entities)
    
    def test_remove_owned_entity(self):
        """Test removing owned entity from user."""
        self.user.add_owned_entity("table-001")
        self.user.add_owned_entity("table-002")
        self.user.remove_owned_entity("table-001")
        
        self.assertNotIn("table-001", self.user.owned_entities)
        self.assertIn("table-002", self.user.owned_entities)
    
    def test_update_last_login(self):
        """Test updating last login timestamp."""
        old_login = self.user.last_login
        self.user.update_last_login()
        self.assertNotEqual(self.user.last_login, old_login)
    
    def test_activate_deactivate(self):
        """Test activating and deactivating user."""
        self.user.deactivate()
        self.assertFalse(self.user.is_active)
        
        self.user.activate()
        self.assertTrue(self.user.is_active)
    
    def test_permission_checks(self):
        """Test permission checking methods."""
        self.user.add_permission("read")
        self.user.add_permission("write")
        
        self.assertTrue(self.user.has_permission("read"))
        self.assertTrue(self.user.has_permission("write"))
        self.assertFalse(self.user.has_permission("execute"))
    
    def test_entity_access_checks(self):
        """Test entity access checking methods."""
        self.user.add_read_entity("table-001")
        self.user.add_write_entity("table-002")
        self.user.add_owned_entity("table-003")
        
        self.assertTrue(self.user.can_read("table-001"))
        self.assertTrue(self.user.can_write("table-002"))
        self.assertTrue(self.user.owns("table-003"))
        
        self.assertFalse(self.user.can_read("table-999"))
        self.assertFalse(self.user.can_write("table-999"))
        self.assertFalse(self.user.owns("table-999"))


class TestAirflowDag(unittest.TestCase):
    """Test cases for AirflowDag model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.dag = AirflowDag(
            name="test_dag",
            dag_id="test_dag_id",
            owner="testuser"
        )
    
    def test_dag_creation(self):
        """Test that DAG is created with correct attributes."""
        self.assertEqual(self.dag.name, "test_dag")
        self.assertEqual(self.dag.dag_id, "test_dag_id")
        self.assertEqual(self.dag.owner, "testuser")
        self.assertTrue(self.dag.is_active)
        self.assertEqual(self.dag.read_tables, [])
        self.assertEqual(self.dag.write_tables, [])
        self.assertEqual(self.dag.owned_tables, [])
        self.assertEqual(self.dag.retries, 3)
    
    def test_dag_default_values(self):
        """Test DAG default values."""
        minimal_dag = AirflowDag(
            name="minimal_dag",
            dag_id="minimal_dag_id",
            owner="minimal_user"  # Required field
        )
        self.assertTrue(minimal_dag.is_active)
        self.assertEqual(minimal_dag.read_tables, [])
        self.assertEqual(minimal_dag.write_tables, [])
        self.assertEqual(minimal_dag.owned_tables, [])
        self.assertEqual(minimal_dag.retries, 3)
        self.assertEqual(minimal_dag.schedule_interval, None)
        self.assertEqual(minimal_dag.last_run, None)
        self.assertEqual(minimal_dag.next_run, None)
    
    def test_dag_with_custom_properties(self):
        """Test DAG with custom properties."""
        dag = AirflowDag(
            name="Custom DAG",
            dag_id="custom_dag_id",
            owner="customuser"
        )
        dag.set_property("environment", "production")
        dag.set_property("team", "data_engineering")
        
        self.assertEqual(dag.get_property("environment"), "production")
        self.assertEqual(dag.get_property("team"), "data_engineering")
    
    def test_add_read_table(self):
        """Test adding read table to DAG."""
        self.dag.add_read_table("table-001")
        self.dag.add_read_table("table-002")
        self.assertIn("table-001", self.dag.read_tables)
        self.assertIn("table-002", self.dag.read_tables)
    
    def test_remove_read_table(self):
        """Test removing read table from DAG."""
        self.dag.add_read_table("table-001")
        self.dag.add_read_table("table-002")
        self.dag.remove_read_table("table-001")
        
        self.assertNotIn("table-001", self.dag.read_tables)
        self.assertIn("table-002", self.dag.read_tables)
    
    def test_add_write_table(self):
        """Test adding write table to DAG."""
        self.dag.add_write_table("table-001")
        self.dag.add_write_table("table-002")
        self.assertIn("table-001", self.dag.write_tables)
        self.assertIn("table-002", self.dag.write_tables)
    
    def test_remove_write_table(self):
        """Test removing write table from DAG."""
        self.dag.add_write_table("table-001")
        self.dag.add_write_table("table-002")
        self.dag.remove_write_table("table-001")
        
        self.assertNotIn("table-001", self.dag.write_tables)
        self.assertIn("table-002", self.dag.write_tables)
    
    def test_add_owned_table(self):
        """Test adding owned table to DAG."""
        self.dag.add_owned_table("table-001")
        self.dag.add_owned_table("table-002")
        self.assertIn("table-001", self.dag.owned_tables)
        self.assertIn("table-002", self.dag.owned_tables)
    
    def test_remove_owned_table(self):
        """Test removing owned table from DAG."""
        self.dag.add_owned_table("table-001")
        self.dag.add_owned_table("table-002")
        self.dag.remove_owned_table("table-001")
        
        self.assertNotIn("table-001", self.dag.owned_tables)
        self.assertIn("table-002", self.dag.owned_tables)
    
    def test_update_last_run(self):
        """Test updating last run timestamp."""
        old_run = self.dag.last_run
        self.dag.update_last_run()
        self.assertNotEqual(self.dag.last_run, old_run)
    
    def test_set_next_run(self):
        """Test setting next run timestamp."""
        next_run = datetime.now()
        self.dag.set_next_run(next_run)
        self.assertEqual(self.dag.next_run, next_run)
    
    def test_activate_deactivate(self):
        """Test activating and deactivating DAG."""
        self.dag.deactivate()
        self.assertFalse(self.dag.is_active)
        
        self.dag.activate()
        self.assertTrue(self.dag.is_active)
    
    def test_get_table_count(self):
        """Test getting table count."""
        self.assertEqual(self.dag.get_table_count(), 0)
        
        self.dag.add_read_table("table-001")
        self.dag.add_write_table("table-002")
        self.dag.add_owned_table("table-003")
        
        self.assertEqual(self.dag.get_table_count(), 3)
    
    def test_table_access_checks(self):
        """Test table access checking methods."""
        self.dag.add_read_table("table-001")
        self.dag.add_write_table("table-002")
        self.dag.add_owned_table("table-003")
        
        self.assertTrue(self.dag.is_reading_table("table-001"))
        self.assertTrue(self.dag.is_writing_table("table-002"))
        self.assertTrue(self.dag.owns_table("table-003"))
        
        self.assertFalse(self.dag.is_reading_table("table-999"))
        self.assertFalse(self.dag.is_writing_table("table-999"))
        self.assertFalse(self.dag.owns_table("table-999"))


class TestWorkflowIntegration(unittest.TestCase):
    """Test cases for workflow integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User(
            name="Test User",
            username="testuser",
            role="data_engineer"
        )
        
        self.dag = AirflowDag(
            name="Test DAG",
            dag_id="test_dag_id",
            owner="testuser"
        )
    
    def test_user_dag_access(self):
        """Test that user can access DAG."""
        # User can read and write to DAG
        self.user.add_read_entity(self.dag.id)
        self.user.add_write_entity(self.dag.id)
        
        self.assertTrue(self.user.can_read(self.dag.id))
        self.assertTrue(self.user.can_write(self.dag.id))
    
    def test_dag_task_management(self):
        """Test DAG task management."""
        # DAG reads from source table
        self.dag.add_read_table("source_table")
        
        # DAG writes to target table
        self.dag.add_write_table("target_table")
        
        # Verify table associations
        self.assertTrue(self.dag.is_reading_table("source_table"))
        self.assertTrue(self.dag.is_writing_table("target_table"))
        self.assertEqual(self.dag.get_table_count(), 2)
    
    def test_dag_dependency_management(self):
        """Test DAG dependency management."""
        # DAG reads from multiple source tables
        self.dag.add_read_table("customer_table")
        self.dag.add_read_table("order_table")
        
        # DAG writes to aggregated table
        self.dag.add_write_table("customer_orders_agg")
        
        # Verify all table associations
        self.assertTrue(self.dag.is_reading_table("customer_table"))
        self.assertTrue(self.dag.is_reading_table("order_table"))
        self.assertTrue(self.dag.is_writing_table("customer_orders_agg"))
        self.assertEqual(self.dag.get_table_count(), 3)
    
    def test_dag_scheduling_and_ownership(self):
        """Test DAG scheduling and ownership."""
        # Set next run time
        next_run = datetime.now()
        self.dag.set_next_run(next_run)
        self.assertEqual(self.dag.next_run, next_run)
        
        # Verify ownership
        self.assertEqual(self.dag.owner, "testuser")
    
    def test_user_permissions_and_dag_access(self):
        """Test user permissions and DAG access."""
        # Add permissions to user
        self.user.add_permission("read")
        self.user.add_permission("write")
        self.user.add_permission("execute")
        
        # Verify permissions
        self.assertIn("read", self.user.permissions)
        self.assertIn("write", self.user.permissions)
        self.assertIn("execute", self.user.permissions)
        
        # Add DAG to user's accessed entities
        self.user.add_read_entity(self.dag.id)
        self.user.add_write_entity(self.dag.id)
        
        # Verify access
        self.assertTrue(self.user.can_read(self.dag.id))
        self.assertTrue(self.user.can_write(self.dag.id))
    
    def test_workflow_validation(self):
        """Test workflow validation."""
        # Test user validation
        self.assertTrue(self.user.name)
        self.assertTrue(self.user.username)
        self.assertTrue(self.user.role)
        
        # Test DAG validation
        self.assertTrue(self.dag.name)
        self.assertTrue(self.dag.dag_id)
        
        # Test DAG state
        self.assertTrue(self.dag.is_active)
    
    def test_workflow_serialization(self):
        """Test workflow serialization."""
        # Test user serialization
        user_dict = self.user.model_dump()
        self.assertIn("name", user_dict)
        self.assertIn("username", user_dict)
        self.assertIn("role", user_dict)
        
        # Test DAG serialization
        dag_dict = self.dag.model_dump()
        self.assertIn("name", dag_dict)
        self.assertIn("dag_id", dag_dict)
        self.assertIn("owner", dag_dict)
    
    def test_workflow_state_management(self):
        """Test workflow state management."""
        # Test user state changes
        self.user.deactivate()
        self.assertFalse(self.user.is_active)
        self.user.activate()
        self.assertTrue(self.user.is_active)
        
        # Test DAG state changes
        self.dag.deactivate()
        self.assertFalse(self.dag.is_active)
        self.dag.activate()
        self.assertTrue(self.dag.is_active)


if __name__ == "__main__":
    unittest.main()
