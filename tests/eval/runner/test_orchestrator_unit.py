"""
Unit tests for ScenarioOrchestrator class.

Tests the orchestration logic without requiring a live API.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from tests.eval.runner.scenario_orchestrator import (
    ScenarioOrchestrator,
    OrchestratorError,
    SetupError,
    TurnExecutionError,
)
from tests.eval.runner.models import (
    AssertionResult,
    AssertionSeverity,
    EvalResult,
    MemoryDiff,
    MemorySnapshot,
    MemoryEntity,
    DIKWLayer,
    TurnResult,
    RedisLayerSnapshot,
    Mem0LayerSnapshot,
    GraphitiLayerSnapshot,
    Neo4jDIKWLayerSnapshot,
)
from tests.eval.runner.scenario_models import (
    Scenario,
    ScenarioTurn,
    InitialState,
    InitialStateEntity,
    InitialStateRelationship,
    ResponseAssertions,
    StateAssertions,
    DeterministicAssertion,
    EntityAssertion,
    DiffAssertion,
)


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def mock_memory_inspector():
    """Create a mock MemoryInspector."""
    inspector = AsyncMock()

    # Default implementations
    inspector.take_snapshot = AsyncMock(return_value=MemorySnapshot(
        patient_id="test-patient",
        timestamp=datetime.now(UTC),
    ))
    inspector.compute_diff = MagicMock(return_value=MemoryDiff())
    inspector.flush_pipelines = AsyncMock(return_value={"success": True})
    inspector.wait_for_quiescence = AsyncMock(return_value=True)
    inspector.seed_state = AsyncMock(return_value={"success": True})
    inspector.reset_patient = AsyncMock(return_value={"success": True})
    inspector.send_chat = AsyncMock(return_value={
        "response": "Hello! How can I help you?",
        "intent": "greeting",
    })

    return inspector


@pytest.fixture
def test_orchestrator(mock_memory_inspector):
    """Create a ScenarioOrchestrator with mocked dependencies."""
    return ScenarioOrchestrator(
        memory_inspector=mock_memory_inspector,
        turn_timeout=10.0,
        quiescence_timeout=30.0,
        reset_before_scenario=True,
    )


@pytest.fixture
def simple_scenario():
    """Create a simple test scenario."""
    return Scenario(
        id="test_scenario",
        name="Test Scenario",
        description="A simple test scenario",
        category="test",
        severity="medium",
        turns=[
            ScenarioTurn(
                turn=1,
                patient_message="Hello",
                response_assertions=ResponseAssertions(
                    deterministic=[
                        DeterministicAssertion(
                            type="not_empty",
                            reason="Response should not be empty",
                        )
                    ],
                ),
            )
        ],
    )


@pytest.fixture
def scenario_with_initial_state():
    """Create a scenario with initial state."""
    return Scenario(
        id="scenario_with_state",
        name="Scenario with Initial State",
        category="test",
        severity="high",
        initial_state=InitialState(
            patient_id="test-patient-123",
            entities=[
                InitialStateEntity(
                    name="Metformina",
                    type="Medication",
                    properties={"dosage": "500mg"},
                    dikw_layer="SEMANTIC",
                    confidence=0.9,
                )
            ],
            relationships=[
                InitialStateRelationship(
                    from_entity="Metformina",
                    to_entity="Diabetes",
                    type="TREATS",
                )
            ],
        ),
        turns=[
            ScenarioTurn(
                turn=1,
                patient_message="What medications am I taking?",
                state_assertions=StateAssertions(
                    entities_must_exist=[
                        EntityAssertion(
                            name="Metformina",
                            type="Medication",
                            reason="Should exist from initial state",
                        )
                    ],
                ),
            )
        ],
    )


@pytest.fixture
def multi_turn_scenario():
    """Create a multi-turn scenario."""
    return Scenario(
        id="multi_turn",
        name="Multi-Turn Scenario",
        category="test",
        severity="medium",
        turns=[
            ScenarioTurn(
                turn=1,
                patient_message="First message",
                response_assertions=ResponseAssertions(
                    deterministic=[
                        DeterministicAssertion(
                            type="not_empty",
                            reason="Response should not be empty",
                        )
                    ],
                ),
            ),
            ScenarioTurn(
                turn=2,
                patient_message="Second message",
                response_assertions=ResponseAssertions(
                    deterministic=[
                        DeterministicAssertion(
                            type="not_empty",
                            reason="Response should not be empty",
                        )
                    ],
                ),
            ),
        ],
    )


# ========================================
# Basic Orchestration Tests
# ========================================

class TestBasicOrchestration:
    """Tests for basic orchestration functionality."""

    @pytest.mark.asyncio
    async def test_run_simple_scenario(self, test_orchestrator, simple_scenario):
        """Test running a simple scenario."""
        result = await test_orchestrator.run_scenario(simple_scenario)

        assert result.scenario_id == "test_scenario"
        assert result.passed
        assert len(result.turns) == 1
        assert result.turns[0].passed
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_scenario_calls_reset(
        self,
        test_orchestrator,
        mock_memory_inspector,
        simple_scenario,
    ):
        """Test that running a scenario resets the patient."""
        await test_orchestrator.run_scenario(simple_scenario)

        mock_memory_inspector.reset_patient.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scenario_without_reset(
        self,
        mock_memory_inspector,
        simple_scenario,
    ):
        """Test running a scenario without reset."""
        orchestrator = ScenarioOrchestrator(
            memory_inspector=mock_memory_inspector,
            reset_before_scenario=False,
        )

        await orchestrator.run_scenario(simple_scenario)

        mock_memory_inspector.reset_patient.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_multi_turn_scenario(
        self,
        test_orchestrator,
        multi_turn_scenario,
    ):
        """Test running a multi-turn scenario."""
        result = await test_orchestrator.run_scenario(multi_turn_scenario)

        assert len(result.turns) == 2
        assert result.turns[0].turn_number == 1
        assert result.turns[1].turn_number == 2
        assert all(t.passed for t in result.turns)

    @pytest.mark.asyncio
    async def test_run_scenarios_sequential(
        self,
        test_orchestrator,
        simple_scenario,
    ):
        """Test running multiple scenarios sequentially."""
        scenario2 = simple_scenario.model_copy(update={"id": "scenario_2"})

        results = await test_orchestrator.run_scenarios(
            [simple_scenario, scenario2],
            parallel=False,
        )

        assert len(results) == 2
        assert results[0].scenario_id == "test_scenario"
        assert results[1].scenario_id == "scenario_2"

    @pytest.mark.asyncio
    async def test_run_scenarios_stop_on_failure(
        self,
        mock_memory_inspector,
        simple_scenario,
    ):
        """Test stopping on first failure."""
        # Make the chat return empty response (will fail not_empty assertion)
        mock_memory_inspector.send_chat = AsyncMock(return_value={"response": ""})

        orchestrator = ScenarioOrchestrator(
            memory_inspector=mock_memory_inspector,
        )

        scenario2 = simple_scenario.model_copy(update={"id": "scenario_2"})

        results = await orchestrator.run_scenarios(
            [simple_scenario, scenario2],
            stop_on_failure=True,
        )

        # Should only have one result (stopped after first failure)
        assert len(results) == 1
        assert not results[0].passed


# ========================================
# Initial State Tests
# ========================================

class TestInitialStateSetup:
    """Tests for initial state setup."""

    @pytest.mark.asyncio
    async def test_seeds_initial_state(
        self,
        test_orchestrator,
        mock_memory_inspector,
        scenario_with_initial_state,
    ):
        """Test that initial state is seeded."""
        await test_orchestrator.run_scenario(scenario_with_initial_state)

        mock_memory_inspector.seed_state.assert_called_once()
        call_args = mock_memory_inspector.seed_state.call_args

        assert call_args[1]["patient_id"] == "test-patient-123"
        assert len(call_args[1]["entities"]) == 1
        assert call_args[1]["entities"][0]["name"] == "Metformina"

    @pytest.mark.asyncio
    async def test_waits_for_quiescence_after_setup(
        self,
        test_orchestrator,
        mock_memory_inspector,
        scenario_with_initial_state,
    ):
        """Test that orchestrator waits for quiescence after setup."""
        await test_orchestrator.run_scenario(scenario_with_initial_state)

        # Should be called after setup and after each turn
        assert mock_memory_inspector.wait_for_quiescence.call_count >= 1

    @pytest.mark.asyncio
    async def test_setup_failure_stops_scenario(
        self,
        mock_memory_inspector,
        scenario_with_initial_state,
    ):
        """Test that setup failure stops the scenario."""
        mock_memory_inspector.reset_patient = AsyncMock(
            side_effect=Exception("Reset failed")
        )

        orchestrator = ScenarioOrchestrator(
            memory_inspector=mock_memory_inspector,
        )

        result = await orchestrator.run_scenario(scenario_with_initial_state)

        assert not result.passed
        assert "Reset failed" in result.error


# ========================================
# Assertion Evaluation Tests
# ========================================

class TestDeterministicAssertions:
    """Tests for deterministic assertion evaluation."""

    @pytest.mark.asyncio
    async def test_must_contain_passes(self, mock_memory_inspector):
        """Test must_contain assertion passes when value is present."""
        mock_memory_inspector.send_chat = AsyncMock(return_value={
            "response": "I see you're taking Metformina",
        })

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="must_contain",
                                values=["Metformina"],
                                reason="Should mention medication",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert result.passed

    @pytest.mark.asyncio
    async def test_must_contain_fails(self, mock_memory_inspector):
        """Test must_contain assertion fails when value is missing."""
        mock_memory_inspector.send_chat = AsyncMock(return_value={
            "response": "I understand",
        })

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="must_contain",
                                values=["Metformina"],
                                reason="Should mention medication",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert not result.passed
        assert len(result.turns[0].failed_assertions) == 1

    @pytest.mark.asyncio
    async def test_must_not_contain_passes(self, mock_memory_inspector):
        """Test must_not_contain assertion passes."""
        mock_memory_inspector.send_chat = AsyncMock(return_value={
            "response": "I understand",
        })

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="must_not_contain",
                                values=["error", "invalid"],
                                reason="Should not contain error words",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert result.passed

    @pytest.mark.asyncio
    async def test_regex_match(self, mock_memory_inspector):
        """Test regex_match assertion."""
        mock_memory_inspector.send_chat = AsyncMock(return_value={
            "response": "Your dosage is 500mg twice daily",
        })

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="regex_match",
                                pattern=r"\d+mg",
                                reason="Should contain dosage",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert result.passed


# ========================================
# State Assertion Tests
# ========================================

class TestStateAssertions:
    """Tests for state assertion evaluation."""

    @pytest.mark.asyncio
    async def test_entity_must_exist_passes(self, mock_memory_inspector):
        """Test entity_must_exist assertion passes when entity exists."""
        # Create snapshot with the expected entity
        mock_memory_inspector.take_snapshot = AsyncMock(return_value=MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            graphiti=GraphitiLayerSnapshot(
                entities=[
                    MemoryEntity(
                        name="Metformina",
                        entity_type="Medication",
                    )
                ],
            ),
        ))

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    state_assertions=StateAssertions(
                        entities_must_exist=[
                            EntityAssertion(
                                name="Metformina",
                                type="Medication",
                                reason="Medication should exist",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert result.passed

    @pytest.mark.asyncio
    async def test_entity_must_not_exist_passes(self, mock_memory_inspector):
        """Test entity_must_not_exist assertion passes when entity is absent."""
        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    state_assertions=StateAssertions(
                        entities_must_not_exist=[
                            EntityAssertion(
                                name="Muriel",
                                type="Medication",
                                reason="Typo should not be stored",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert result.passed

    @pytest.mark.asyncio
    async def test_entity_must_not_exist_fails(self, mock_memory_inspector):
        """Test entity_must_not_exist assertion fails when entity exists."""
        mock_memory_inspector.take_snapshot = AsyncMock(return_value=MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            graphiti=GraphitiLayerSnapshot(
                entities=[
                    MemoryEntity(
                        name="Muriel",
                        entity_type="Medication",
                    )
                ],
            ),
        ))

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    state_assertions=StateAssertions(
                        entities_must_not_exist=[
                            EntityAssertion(
                                name="Muriel",
                                type="Medication",
                                reason="Typo should not be stored",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert not result.passed

    @pytest.mark.asyncio
    async def test_memory_diff_check(self, mock_memory_inspector):
        """Test memory diff assertion."""
        mock_memory_inspector.compute_diff = MagicMock(return_value=MemoryDiff(
            entities_added=[
                MemoryEntity(name="Unexpected", entity_type="Unknown"),
            ],
        ))

        orchestrator = ScenarioOrchestrator(memory_inspector=mock_memory_inspector)

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    state_assertions=StateAssertions(
                        memory_diff_check=DiffAssertion(
                            max_unexpected_entities=0,
                            reason="No unexpected entities",
                        ),
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert not result.passed


# ========================================
# Error Handling Tests
# ========================================

class TestErrorHandling:
    """Tests for error handling in orchestrator."""

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_memory_inspector):
        """Test that timeouts are handled gracefully."""
        import asyncio

        async def slow_chat(*args, **kwargs):
            await asyncio.sleep(100)  # Will timeout
            return {"response": "Never returned"}

        mock_memory_inspector.send_chat = slow_chat

        orchestrator = ScenarioOrchestrator(
            memory_inspector=mock_memory_inspector,
            turn_timeout=0.1,  # Very short timeout
        )

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="not_empty",
                                reason="Test",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert not result.passed
        assert result.turns[0].agent_response == "[TIMEOUT]"

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_memory_inspector):
        """Test that exceptions are handled gracefully."""
        mock_memory_inspector.send_chat = AsyncMock(
            side_effect=Exception("Chat failed")
        )

        orchestrator = ScenarioOrchestrator(
            memory_inspector=mock_memory_inspector,
        )

        scenario = Scenario(
            id="test",
            name="Test",
            category="test",
            turns=[
                ScenarioTurn(
                    turn=1,
                    patient_message="Test",
                    response_assertions=ResponseAssertions(
                        deterministic=[
                            DeterministicAssertion(
                                type="not_empty",
                                reason="Test",
                            )
                        ],
                    ),
                )
            ],
        )

        result = await orchestrator.run_scenario(scenario)

        assert not result.passed
        assert "Chat failed" in result.turns[0].agent_response


# ========================================
# Hook Tests
# ========================================

class TestHooks:
    """Tests for orchestrator hooks."""

    @pytest.mark.asyncio
    async def test_before_scenario_hook(
        self,
        test_orchestrator,
        simple_scenario,
    ):
        """Test before scenario hooks are called."""
        hook_called = []

        def before_hook(scenario, patient_id):
            hook_called.append(scenario.id)

        test_orchestrator.add_before_scenario_hook(before_hook)
        await test_orchestrator.run_scenario(simple_scenario)

        assert "test_scenario" in hook_called

    @pytest.mark.asyncio
    async def test_after_scenario_hook(
        self,
        test_orchestrator,
        simple_scenario,
    ):
        """Test after scenario hooks are called."""
        hook_called = []

        def after_hook(scenario, patient_id):
            hook_called.append(scenario.id)

        test_orchestrator.add_after_scenario_hook(after_hook)
        await test_orchestrator.run_scenario(simple_scenario)

        assert "test_scenario" in hook_called

    @pytest.mark.asyncio
    async def test_before_turn_hook(
        self,
        test_orchestrator,
        multi_turn_scenario,
    ):
        """Test before turn hooks are called for each turn."""
        hook_calls = []

        def before_turn(turn, patient_id):
            hook_calls.append(turn.turn)

        test_orchestrator.add_before_turn_hook(before_turn)
        await test_orchestrator.run_scenario(multi_turn_scenario)

        assert hook_calls == [1, 2]

    @pytest.mark.asyncio
    async def test_async_hooks(
        self,
        test_orchestrator,
        simple_scenario,
    ):
        """Test async hooks are properly awaited."""
        hook_called = []

        async def async_hook(scenario, patient_id):
            hook_called.append(scenario.id)

        test_orchestrator.add_before_scenario_hook(async_hook)
        await test_orchestrator.run_scenario(simple_scenario)

        assert "test_scenario" in hook_called
