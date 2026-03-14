"""FastAPI interface for knowledge management events.

This module defines a lightweight HTTP API exposing a single `/events` endpoint.
Clients can POST a JSON payload describing a knowledge event along with the
role of the caller.  The event is published to the application layer's
event bus, which in turn dispatches it to the knowledge manager service.

Usage example::

    import requests
    payload = {
        "action": "create_entity",
        "data": {"id": "node1", "properties": {"name": "Example"}},
        "role": "data_architect"
    }
    resp = requests.post("http://localhost:8000/events", json=payload)
    print(resp.json())
"""

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from domain.event import KnowledgeEvent
from domain.roles import Role
from application.knowledge_management import KnowledgeManagerService
from application.event_bus import EventBus
from infrastructure.in_memory_backend import InMemoryGraphBackend


class EventRequest(BaseModel):
    """Request model for publishing a knowledge event via HTTP."""

    action: str = Field(..., description="Name of the action, e.g. create_entity")
    data: Dict[str, Any] = Field(..., description="Payload for the event")
    role: Role = Field(..., description="Role of the caller")


app = FastAPI(title="Knowledge Management API")

# Create global backend, manager and bus for the API
_backend = InMemoryGraphBackend()
_manager = KnowledgeManagerService(_backend)
_bus = EventBus()

# Subscribe the knowledge manager to both entity and relationship events
import asyncio as _asyncio

async def _setup_subscriptions() -> None:
    await _bus.subscribe("create_entity", _manager.handle_event)
    await _bus.subscribe("create_relationship", _manager.handle_event)

try:
    _loop = _asyncio.get_event_loop()
    if _loop.is_running():
        _loop.create_task(_setup_subscriptions())
    else:
        _loop.run_until_complete(_setup_subscriptions())
except RuntimeError:
    pass


@app.post("/events")
async def publish_event(request: EventRequest) -> JSONResponse:
    """Publish a knowledge event.

    The event is delivered to the event bus and processed asynchronously by
    the subscribed knowledge manager.  On success, the endpoint returns
    ``{"status": "accepted"}``.

    Raises:
        HTTPException: If event processing fails.
    """
    try:
        event = KnowledgeEvent(action=request.action, data=request.data, role=request.role)
        # Await the bus to ensure event is processed before responding
        await _bus.publish(event)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"status": "accepted"})


def get_backend() -> InMemoryGraphBackend:
    """Return the in‑memory backend used by the API.

    This helper is exposed for unit tests to inspect the graph state after
    performing API calls.
    """
    return _backend
