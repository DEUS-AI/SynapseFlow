from abc import ABC, abstractmethod
from typing import Any, Type

from domain.commands import Command


class CommandBus(ABC):
    """Abstract base class for a command bus."""

    @abstractmethod
    def register(self, command: Type[Command], handler: Any) -> None:
        """Register a handler for a command."""
        raise NotImplementedError

    @abstractmethod
    def dispatch(self, command: Command) -> Any:
        """Dispatch a command to its handler."""
        raise NotImplementedError 