import asyncio
from pydantic import BaseModel
from .base import CommandHandler
from domain.commands import Command


class ShellCommandResult(BaseModel):
    """The result of a shell command execution."""

    return_code: int
    stdout: str
    stderr: str


class ExecuteShellCommand(Command, BaseModel):
    """A command to execute a shell command."""

    command: str


class ExecuteShellCommandHandler(CommandHandler[ExecuteShellCommand]):
    """The handler for the ExecuteShellCommand."""

    async def handle(self, command: ExecuteShellCommand) -> ShellCommandResult:
        """
        Handles the ExecuteShellCommand by running it in a subprocess.

        Args:
            command: The ExecuteShellCommand instance.

        Returns:
            A ShellCommandResult containing the execution details.
        """
        process = await asyncio.create_subprocess_shell(
            command.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        return ShellCommandResult(
            return_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout.decode().strip(),
            stderr=stderr.decode().strip(),
        )

