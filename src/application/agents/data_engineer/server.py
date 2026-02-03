from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from application.commands.base import CommandBus
from domain.agent_definition import AgentDefinition
from application.services.tool_service import command_to_tool_definition


class A2ATask(BaseModel):
    tool_name: str
    parameters: dict

def create_app(command_bus: CommandBus) -> FastAPI:
    app = FastAPI(
        title="Data Engineer Agent",
        description="Agent responsible for implementation and challenging design decisions.",
        version="0.1.0",
    )

    def get_command_bus():
        return command_bus

    @app.get("/.well-known/agent.json", response_model=AgentDefinition)
    async def get_agent_definition(bus: CommandBus = Depends(get_command_bus)):
        """
        Serves the agent's definition, including its tools.
        """
        tool_definitions = [
            command_to_tool_definition(cmd) for cmd in bus.handlers
        ]
        return AgentDefinition(
            name=app.title,
            description=app.description,
            version=app.version,
            tools=tool_definitions,
        )

    @app.post("/v1/tasks/send")
    async def send_task(
        task: A2ATask,
        bus: CommandBus = Depends(get_command_bus),
    ):
        """
        This endpoint receives a generic A2A task and dispatches it
        to the appropriate command handler.
        """
        command_class = next(
            (cmd for cmd in bus.handlers if cmd.__name__ == task.tool_name), None
        )

        if not command_class:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{task.tool_name}' not found."
            )

        try:
            command_instance = command_class(**task.parameters)
            await bus.dispatch(command_instance)
            return {"status": "success", "message": f"{task.tool_name} dispatched."}
        except TypeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters for tool '{task.tool_name}': {e}"
            )

    @app.get("/")
    async def root():
        return {"message": "Data Engineer Agent is running."}
    
    return app 