"""Simple asynchronous event bus.

The event bus allows publishers to emit events identified by an action
string.  Subscribers register callback coroutines for specific actions.
When an event is published the bus awaits each subscriber in turn.  This
implementation stores subscribers in memory and is suitable for unit
testing and small deployments.  A production system would integrate
RabbitMQ or a similar message broker and support delivery guarantees,
retry policies and dead‑letter queues.
"""

from typing import Awaitable, Callable, Dict, List

from domain.event import KnowledgeEvent


class EventBus:
    """In‑memory event bus for knowledge events."""

    def __init__(self) -> None:
        # Map event action names to lists of subscriber coroutines
        self._subscribers: Dict[str, List[Callable[[KnowledgeEvent], Awaitable[None]]]] = {}

    async def subscribe(self, action: str, handler: Callable[[KnowledgeEvent], Awaitable[None]]) -> None:
        """Subscribe a coroutine to a specific action.

        Args:
            action: The name of the event action to subscribe to.
            handler: An async callable that accepts a ``KnowledgeEvent``.
        """
        if action not in self._subscribers:
            self._subscribers[action] = []
        self._subscribers[action].append(handler)

    async def publish(self, event: KnowledgeEvent) -> None:
        """Publish an event to all subscribed handlers.

        Subscribers are awaited sequentially.  Errors raised by one handler
        will propagate to the publisher and prevent subsequent handlers
        from running.  This behaviour is deliberate for simplicity but may
        need to be adjusted for production use.

        Args:
            event: The event to publish.
        """
        handlers = self._subscribers.get(event.action, [])
        for handler in handlers:
            await handler(event)