from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

from domain.command_bus import CommandBus as AbstractCommandBus
from domain.commands import Command

T = TypeVar("T", bound=Command)


class CommandHandler(ABC, Generic[T]):
    """Abstract base class for a command handler."""

    @abstractmethod
    async def handle(self, command: T) -> Any:
        """
        Handles the given command.

        Args:
            command: The command to handle.

        Returns:
            The result of the command execution.
        """
        pass


class CommandBus(AbstractCommandBus):
    """A simple command bus to dispatch commands to their handlers."""

    def __init__(self):
        self._handlers: Dict[type, CommandHandler] = {}

    @property
    def handlers(self) -> Dict[type, CommandHandler]:
        return self._handlers

    def register(self, command_type: type, handler: CommandHandler):
        """Registers a handler for a specific command type."""
        self._handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Any:
        """Executes a command by dispatching it to the registered handler."""
        handler = self._handlers.get(type(command))
        if not handler:
            raise TypeError(
                f"No handler registered for command type {type(command).__name__}"
            )
        return await handler.handle(command)
