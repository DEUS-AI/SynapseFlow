"""Tests for the application event bus."""

import unittest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from application.event_bus import EventBus
from domain.event import KnowledgeEvent
from domain.roles import Role


class TestEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_publish_and_subscribe(self) -> None:
        bus = EventBus()
        handled = []

        async def handler(event: KnowledgeEvent) -> None:
            handled.append(event)

        bus.subscribe("create_entity", handler)
        event = KnowledgeEvent(action="create_entity", data={"id": "n"}, role=Role.DATA_ARCHITECT)
        await bus.publish(event)
        self.assertEqual(len(handled), 1)
        self.assertEqual(handled[0].data["id"], "n")
