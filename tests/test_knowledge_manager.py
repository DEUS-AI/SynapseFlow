"""Tests for the knowledge manager service."""

import unittest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from application.knowledge_management import KnowledgeManagerService
from domain.event import KnowledgeEvent
from domain.roles import Role
from infrastructure.in_memory_backend import InMemoryGraphBackend


class TestKnowledgeManagerService(unittest.IsolatedAsyncioTestCase):
    async def test_handle_create_entity(self) -> None:
        backend = InMemoryGraphBackend()
        km = KnowledgeManagerService(backend)
        event = KnowledgeEvent(
            action="create_entity",
            data={"id": "a", "properties": {"name": "A"}},
            role=Role.DATA_ARCHITECT,
        )
        await km.handle_event(event)
        self.assertIn("a", backend.nodes)
        self.assertEqual(backend.nodes["a"]["name"], "A")

    async def test_handle_create_relationship_authorised(self) -> None:
        backend = InMemoryGraphBackend()
        km = KnowledgeManagerService(backend)
        # add source and target first
        await backend.add_entity("x", {})
        await backend.add_entity("y", {})
        event = KnowledgeEvent(
            action="create_relationship",
            data={"source": "x", "target": "y", "type": "RELATED", "properties": {}},
            role=Role.KNOWLEDGE_MANAGER,
        )
        await km.handle_event(event)
        self.assertIn("x", backend.edges)
        self.assertEqual(backend.edges["x"][0][1], "y")

    async def test_handle_create_relationship_unauthorised(self) -> None:
        backend = InMemoryGraphBackend()
        km = KnowledgeManagerService(backend)
        event = KnowledgeEvent(
            action="create_relationship",
            data={"source": "a", "target": "b", "type": "REL"},
            role=Role.DATA_ENGINEER,
        )
        with self.assertRaises(PermissionError):
            await km.handle_event(event)

    async def test_handle_unknown_action(self) -> None:
        backend = InMemoryGraphBackend()
        km = KnowledgeManagerService(backend)
        event = KnowledgeEvent(action="unknown", data={}, role=Role.DATA_ENGINEER)
        with self.assertRaises(ValueError):
            await km.handle_event(event)
