"""Tests for the in‑memory knowledge graph backend."""

import unittest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from infrastructure.in_memory_backend import InMemoryGraphBackend


class TestInMemoryGraphBackend(unittest.IsolatedAsyncioTestCase):
    async def test_add_entity(self) -> None:
        backend = InMemoryGraphBackend()
        await backend.add_entity("node1", {"name": "test"})
        self.assertIn("node1", backend.nodes)
        self.assertEqual(backend.nodes["node1"]["name"], "test")

    async def test_add_relationship(self) -> None:
        backend = InMemoryGraphBackend()
        await backend.add_entity("n1", {})
        await backend.add_entity("n2", {})
        await backend.add_relationship("n1", "KNOWS", "n2", {"since": 2020})
        self.assertIn("n1", backend.edges)
        rel_type, target, props = backend.edges["n1"][0]
        self.assertEqual(rel_type, "KNOWS")
        self.assertEqual(target, "n2")
        self.assertEqual(props["since"], 2020)

    async def test_rollback(self) -> None:
        backend = InMemoryGraphBackend()
        await backend.add_entity("e1", {})
        await backend.add_entity("e2", {})
        # Rollback should remove last entity e2
        await backend.rollback()
        self.assertNotIn("e2", backend.nodes)
        # Rollback again should remove e1
        await backend.rollback()
        self.assertNotIn("e1", backend.nodes)
