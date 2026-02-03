from pydantic import BaseModel
from pathlib import Path
from .base import CommandHandler
from domain.commands import Command


class CreateFileCommand(Command, BaseModel):
    """A command to create a file with specified content."""

    path: str
    content: str


class CreateFileCommandHandler(CommandHandler[CreateFileCommand]):
    """The handler for the CreateFileCommand."""

    async def handle(self, command: CreateFileCommand) -> str:
        """Handles the command by creating a new file."""
        file_path = Path(command.path)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(command.content, encoding="utf-8")
            # Return the resolved, absolute path for consistency
            return f"File created at: {file_path.resolve()}"
        except Exception as e:
            return f"Error creating file: {e}"


class ReadFileCommand(Command, BaseModel):
    """A command to read the content of a file."""

    path: str


class ReadFileCommandHandler(CommandHandler[ReadFileCommand]):
    """The handler for the ReadFileCommand."""

    async def handle(self, command: ReadFileCommand) -> str:
        """Handles the command by reading a file and returning its content."""
        try:
            with open(command.path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: File not found at {command.path}"
        except Exception as e:
            return f"Error reading file: {e}"
