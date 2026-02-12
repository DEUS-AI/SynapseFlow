"""
Eval Runner - Framework de evaluación de agentes.

Este paquete proporciona las herramientas para ejecutar evaluaciones
automatizadas del agente médico:

- models: Modelos Pydantic para snapshots, diffs, y resultados
- scenario_models: Modelos para escenarios YAML
- memory_inspector: Cliente para captura de snapshots y cálculo de diffs
- scenario_loader: Carga y parseo de escenarios YAML
- test_orchestrator: Orquestador de pruebas de evaluación
- evaluators: Evaluadores determinísticos y LLM-as-Judge (TODO)
"""

from .models import (
    # Enums
    DIKWLayer,
    MemoryLayer,
    AssertionSeverity,
    # Entity/Relationship models
    MemoryEntity,
    MemoryRelationship,
    Mem0Memory,
    # Layer snapshots
    RedisLayerSnapshot,
    Mem0LayerSnapshot,
    GraphitiLayerSnapshot,
    Neo4jDIKWLayerSnapshot,
    # Full snapshot
    MemorySnapshot,
    # Diff models
    EntityChange,
    MemoryDiff,
    # Result models
    AssertionResult,
    TurnResult,
    EvalResult,
    # Utility functions
    normalize_text,
    entities_match,
    relationships_match,
)

from .memory_inspector import (
    MemoryInspector,
    MemoryInspectorError,
    QuiescenceTimeoutError,
)

from .scenario_models import (
    # Enums
    ScenarioSeverity,
    ScenarioCategory,
    # Assertion models
    DeterministicAssertion,
    JudgeAssertion,
    ResponseAssertions,
    EntityAssertion,
    RelationshipAssertion,
    PropertyAssertion,
    LayerAssertion,
    DiffAssertion,
    StateAssertions,
    # Turn and scenario
    ScenarioTurn,
    InitialStateEntity,
    InitialStateRelationship,
    InitialState,
    Scenario,
    PatientStateFixture,
    ScenarioSuite,
)

from .scenario_loader import (
    ScenarioLoader,
    ScenarioLoaderError,
    ScenarioValidationError,
    FixtureNotFoundError,
)

from .scenario_orchestrator import (
    ScenarioOrchestrator,
    OrchestratorError,
    SetupError,
    TurnExecutionError,
)

__all__ = [
    # Enums
    "DIKWLayer",
    "MemoryLayer",
    "AssertionSeverity",
    "ScenarioSeverity",
    "ScenarioCategory",
    # Models
    "MemoryEntity",
    "MemoryRelationship",
    "Mem0Memory",
    "RedisLayerSnapshot",
    "Mem0LayerSnapshot",
    "GraphitiLayerSnapshot",
    "Neo4jDIKWLayerSnapshot",
    "MemorySnapshot",
    "EntityChange",
    "MemoryDiff",
    "AssertionResult",
    "TurnResult",
    "EvalResult",
    # Scenario models
    "DeterministicAssertion",
    "JudgeAssertion",
    "ResponseAssertions",
    "EntityAssertion",
    "RelationshipAssertion",
    "PropertyAssertion",
    "LayerAssertion",
    "DiffAssertion",
    "StateAssertions",
    "ScenarioTurn",
    "InitialStateEntity",
    "InitialStateRelationship",
    "InitialState",
    "Scenario",
    "PatientStateFixture",
    "ScenarioSuite",
    # Inspector
    "MemoryInspector",
    "MemoryInspectorError",
    "QuiescenceTimeoutError",
    # Loader
    "ScenarioLoader",
    "ScenarioLoaderError",
    "ScenarioValidationError",
    "FixtureNotFoundError",
    # Orchestrator
    "ScenarioOrchestrator",
    "OrchestratorError",
    "SetupError",
    "TurnExecutionError",
    # Utilities
    "normalize_text",
    "entities_match",
    "relationships_match",
]
