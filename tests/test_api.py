"""Tests for the FastAPI knowledge event endpoint."""

import unittest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from fastapi.testclient import TestClient  # noqa: E402

from interfaces.kg_api import app, get_backend  # noqa: E402


class TestAPI(unittest.TestCase):
    def test_publish_create_entity(self) -> None:
        client = TestClient(app)
        payload = {
            "action": "create_entity",
            "data": {"id": "n1", "properties": {"title": "Node1"}},
            "role": "data_architect",
        }
        response = client.post("/events", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "accepted"})
        # verify entity was added to the backend
        backend = get_backend()
        self.assertIn("n1", backend.nodes)
        self.assertEqual(backend.nodes["n1"]["title"], "Node1")

    def test_publish_invalid_role(self) -> None:
        client = TestClient(app)
        payload = {
            "action": "create_entity",
            "data": {"id": "n2"},
            "role": "unknown_role",
        }
        # FastAPI/Pydantic will reject invalid enum values with 422 Unprocessable Entity
        response = client.post("/events", json=payload)
        self.assertEqual(response.status_code, 422)
