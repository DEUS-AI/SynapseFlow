import os
import pytest
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-fake-key")


@pytest.fixture
def command_registry():
    from application.commands.registry import create_default_registry
    return create_default_registry()
