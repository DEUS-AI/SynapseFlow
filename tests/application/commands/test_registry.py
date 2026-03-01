"""Tests for CommandRegistry: serialization, deserialization, and agent routing."""

import pytest
from pydantic import BaseModel

from application.commands.registry import (
    CommandRegistry,
    CommandDeserializationError,
    COMMAND_TYPE_FIELD,
    create_default_registry,
)
from application.commands.echo_command import EchoCommand
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand
from domain.commands import Command


@pytest.fixture
def tmp_dda_file(tmp_path):
    """Create a real .md file for commands that validate file existence."""
    dda = tmp_path / "test.md"
    dda.write_text("# Test DDA\n## Data Entities\n### Customer\n")
    return str(dda)


# --- Serialization ---


def test_serialize_echo_command(command_registry):
    cmd = EchoCommand(text="hello")
    data = command_registry.serialize(cmd)
    assert data[COMMAND_TYPE_FIELD] == "EchoCommand"
    assert data["text"] == "hello"


def test_serialize_modeling_command(command_registry, tmp_dda_file):
    cmd = ModelingCommand(dda_path=tmp_dda_file, domain="Analytics")
    data = command_registry.serialize(cmd)
    assert data[COMMAND_TYPE_FIELD] == "ModelingCommand"
    assert data["dda_path"] == tmp_dda_file
    assert data["domain"] == "Analytics"


# --- Deserialization ---


def test_deserialize_echo_command(command_registry):
    data = {COMMAND_TYPE_FIELD: "EchoCommand", "text": "world"}
    cmd = command_registry.deserialize(data)
    assert isinstance(cmd, EchoCommand)
    assert cmd.text == "world"


def test_deserialize_modeling_command(command_registry, tmp_dda_file):
    data = {
        COMMAND_TYPE_FIELD: "ModelingCommand",
        "dda_path": tmp_dda_file,
        "domain": "Sales",
        "update_existing": False,
        "validate_only": False,
        "output_path": None,
    }
    cmd = command_registry.deserialize(data)
    assert isinstance(cmd, ModelingCommand)
    assert cmd.dda_path == tmp_dda_file
    assert cmd.domain == "Sales"


# --- Round-trips ---


def test_round_trip_echo_command(command_registry):
    original = EchoCommand(text="round-trip")
    data = command_registry.serialize(original)
    restored = command_registry.deserialize(data)
    assert isinstance(restored, EchoCommand)
    assert restored.text == original.text


def test_round_trip_modeling_command(command_registry, tmp_dda_file):
    original = ModelingCommand(dda_path=tmp_dda_file, domain="Test")
    data = command_registry.serialize(original)
    restored = command_registry.deserialize(data)
    assert isinstance(restored, ModelingCommand)
    assert restored.dda_path == original.dda_path
    assert restored.domain == original.domain


def test_round_trip_generate_metadata_command(command_registry, tmp_dda_file):
    original = GenerateMetadataCommand(dda_path=tmp_dda_file, domain="Meta")
    data = command_registry.serialize(original)
    restored = command_registry.deserialize(data)
    assert isinstance(restored, GenerateMetadataCommand)
    assert restored.dda_path == original.dda_path
    assert restored.domain == original.domain


# --- Error cases ---


def test_deserialize_unknown_type_raises(command_registry):
    data = {COMMAND_TYPE_FIELD: "NonExistentCommand", "x": 1}
    with pytest.raises(CommandDeserializationError, match="NonExistentCommand"):
        command_registry.deserialize(data)


def test_deserialize_missing_type_field_raises(command_registry):
    data = {"text": "no type field"}
    with pytest.raises(CommandDeserializationError, match="missing"):
        command_registry.deserialize(data)


def test_serialize_unregistered_command_raises():
    class FakeCommand(Command, BaseModel):
        val: int = 1

    registry = CommandRegistry()
    with pytest.raises(CommandDeserializationError, match="FakeCommand"):
        registry.serialize(FakeCommand())


# --- Agent role routing ---


def test_get_agent_role_returns_correct_roles(command_registry):
    assert command_registry.get_agent_role(EchoCommand) == "echo"
    assert command_registry.get_agent_role(ModelingCommand) == "data_architect"
    assert command_registry.get_agent_role(GenerateMetadataCommand) == "data_engineer"


def test_get_agent_role_returns_none_for_unknown():
    registry = CommandRegistry()
    assert registry.get_agent_role(EchoCommand) is None


# --- Result serialization ---


@pytest.mark.parametrize(
    "value",
    [None, "hello", 42, {"key": "val", "n": 1}, [1, "two", 3]],
    ids=["none", "str", "int", "dict", "list"],
)
def test_serialize_deserialize_result_round_trip(command_registry, value):
    encoded = command_registry.serialize_result(value)
    decoded = command_registry.deserialize_result(encoded)
    assert decoded == value


def test_serialize_deserialize_result_pydantic_model(command_registry):
    class ResultModel(BaseModel):
        status: str = "ok"
        count: int = 5

    encoded = command_registry.serialize_result(ResultModel())
    decoded = command_registry.deserialize_result(encoded)
    assert decoded == {"status": "ok", "count": 5}
