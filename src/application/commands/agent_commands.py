from pydantic import BaseModel

from application.agent_runner import AgentRunner
from application.commands.base import CommandHandler
from domain.commands import Command


class RunAgentCommand(Command, BaseModel):
    role: str


class StartProjectCommand(Command, BaseModel):
    project_goal: str


class RunAgentHandler(CommandHandler):
    """
    Handles the execution of an agent based on its role.
    """

    def __init__(self, agent_runner: AgentRunner):
        self.agent_runner = agent_runner

    async def handle(self, command: RunAgentCommand) -> None:
        """
        Starts the agent runner.

        This will block until the runner is stopped or cancelled.
        """
        print(f"Handler received command to run agent with role: {command.role}")
        await self.agent_runner.run()
