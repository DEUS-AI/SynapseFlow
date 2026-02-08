"""
Test Orchestrator - Ejecuta escenarios de evaluación contra el API.

Este módulo proporciona el ScenarioOrchestrator que ejecuta escenarios
completos de conversación, captura snapshots de memoria, y evalúa
las aserciones definidas en cada turno.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import (
    AssertionResult,
    AssertionSeverity,
    EvalResult,
    MemoryDiff,
    MemorySnapshot,
    TurnResult,
)
from .memory_inspector import MemoryInspector
from .scenario_models import (
    DeterministicAssertion,
    DiffAssertion,
    EntityAssertion,
    InitialState,
    JudgeAssertion,
    LayerAssertion,
    PropertyAssertion,
    RelationshipAssertion,
    ResponseAssertions,
    Scenario,
    ScenarioTurn,
    StateAssertions,
)
from .evaluators import DeterministicEvaluator, LLMJudgeEvaluator

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Error durante la ejecución del orchestrator."""
    pass


class SetupError(OrchestratorError):
    """Error durante la configuración inicial del escenario."""
    pass


class TurnExecutionError(OrchestratorError):
    """Error durante la ejecución de un turno."""
    pass


class ScenarioOrchestrator:
    """
    Orquestador de pruebas de evaluación.

    Ejecuta escenarios completos de conversación contra el API,
    capturando snapshots de memoria y evaluando aserciones.

    Features:
    - Seed de estado inicial desde fixtures
    - Ejecución de turnos de conversación
    - Captura de snapshots antes/después de cada turno
    - Evaluación de aserciones determinísticas
    - Evaluación con LLM-as-Judge (pluggable)
    - Timeouts configurables
    - Hooks para extensibilidad
    """

    def __init__(
        self,
        memory_inspector: MemoryInspector,
        deterministic_evaluator: Optional[DeterministicEvaluator] = None,
        judge_evaluator: Optional[LLMJudgeEvaluator] = None,
        turn_timeout: float = 30.0,
        quiescence_timeout: float = 60.0,
        reset_before_scenario: bool = True,
        embedding_fn: Optional[Callable] = None,
    ):
        """
        Inicializa el ScenarioOrchestrator.

        Args:
            memory_inspector: Cliente para interactuar con el API de evaluación
            deterministic_evaluator: Evaluador para aserciones determinísticas (se crea por defecto)
            judge_evaluator: Evaluador LLM-as-Judge para criterios subjetivos
            turn_timeout: Timeout por turno en segundos
            quiescence_timeout: Timeout para quiescence en segundos
            reset_before_scenario: Si resetear el paciente antes de cada escenario
            embedding_fn: Función de embeddings para similarity semántica
        """
        self.inspector = memory_inspector
        # Create default deterministic evaluator if not provided
        self.deterministic_evaluator = deterministic_evaluator or DeterministicEvaluator(
            embedding_fn=embedding_fn
        )
        self.judge_evaluator = judge_evaluator
        self.turn_timeout = turn_timeout
        self.quiescence_timeout = quiescence_timeout
        self.reset_before_scenario = reset_before_scenario

        # Hooks para extensibilidad
        self._before_scenario_hooks: List[Callable] = []
        self._after_scenario_hooks: List[Callable] = []
        self._before_turn_hooks: List[Callable] = []
        self._after_turn_hooks: List[Callable] = []

        logger.info(
            f"ScenarioOrchestrator initialized: turn_timeout={turn_timeout}s, "
            f"quiescence_timeout={quiescence_timeout}s"
        )

    # ========================================
    # Scenario Execution
    # ========================================

    async def run_scenario(self, scenario: Scenario) -> EvalResult:
        """
        Ejecuta un escenario completo de evaluación.

        Args:
            scenario: Escenario a ejecutar

        Returns:
            EvalResult con los resultados de todos los turnos
        """
        start_time = time.time()
        error_message: Optional[str] = None
        turn_results: List[TurnResult] = []

        # Generar patient_id
        patient_id = self._get_patient_id(scenario)

        logger.info(
            f"Starting scenario: {scenario.id} ({scenario.name}) "
            f"with patient_id={patient_id}"
        )

        try:
            # Run before hooks
            await self._run_hooks(self._before_scenario_hooks, scenario, patient_id)

            # Setup: reset y seed estado inicial
            await self._setup_scenario(scenario, patient_id)

            # Ejecutar cada turno
            for turn in scenario.turns:
                turn_result = await self._execute_turn(turn, patient_id)
                turn_results.append(turn_result)

                # Si el turno falla en aserciones críticas, podemos parar
                if not turn_result.passed and self._has_critical_failure(turn_result):
                    logger.warning(
                        f"Critical failure in turn {turn.turn}, stopping scenario"
                    )
                    break

            # Run after hooks
            await self._run_hooks(self._after_scenario_hooks, scenario, patient_id)

        except Exception as e:
            error_message = str(e)
            logger.error(f"Scenario {scenario.id} failed with error: {e}")

        # Calcular resultado global
        duration = time.time() - start_time
        passed = (
            error_message is None and
            all(t.passed for t in turn_results)
        )

        result = EvalResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            category=scenario.category,
            severity=scenario.severity,
            passed=passed,
            turns=turn_results,
            duration_seconds=duration,
            timestamp=datetime.utcnow(),
            error=error_message,
        )

        logger.info(
            f"Scenario {scenario.id} completed: passed={passed}, "
            f"duration={duration:.2f}s, turns={len(turn_results)}"
        )

        return result

    async def run_scenarios(
        self,
        scenarios: List[Scenario],
        stop_on_failure: bool = False,
        parallel: bool = False,
        max_parallel: int = 3,
    ) -> List[EvalResult]:
        """
        Ejecuta múltiples escenarios.

        Args:
            scenarios: Lista de escenarios a ejecutar
            stop_on_failure: Parar al primer fallo
            parallel: Ejecutar en paralelo
            max_parallel: Máximo de escenarios en paralelo

        Returns:
            Lista de resultados
        """
        results: List[EvalResult] = []

        if parallel:
            # Ejecutar en paralelo con semáforo
            semaphore = asyncio.Semaphore(max_parallel)

            async def run_with_semaphore(scenario: Scenario) -> EvalResult:
                async with semaphore:
                    return await self.run_scenario(scenario)

            tasks = [run_with_semaphore(s) for s in scenarios]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convertir excepciones a EvalResult con error
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(EvalResult(
                        scenario_id=scenarios[i].id,
                        scenario_name=scenarios[i].name,
                        category=scenarios[i].category,
                        severity=scenarios[i].severity,
                        passed=False,
                        turns=[],
                        duration_seconds=0.0,
                        timestamp=datetime.utcnow(),
                        error=str(result),
                    ))
                else:
                    processed_results.append(result)
            results = processed_results

        else:
            # Ejecutar secuencialmente
            for scenario in scenarios:
                result = await self.run_scenario(scenario)
                results.append(result)

                if stop_on_failure and not result.passed:
                    logger.warning(f"Stopping after failed scenario: {scenario.id}")
                    break

        return results

    # ========================================
    # Setup
    # ========================================

    async def _setup_scenario(self, scenario: Scenario, patient_id: str) -> None:
        """
        Configura el estado inicial del escenario.

        Args:
            scenario: Escenario a configurar
            patient_id: ID del paciente
        """
        logger.debug(f"Setting up scenario {scenario.id} for patient {patient_id}")

        try:
            # Reset paciente si está configurado
            if self.reset_before_scenario:
                await self.inspector.reset_patient(patient_id)
                logger.debug(f"Reset patient {patient_id}")

            # Seed estado inicial si existe
            if scenario.initial_state:
                await self._seed_initial_state(scenario.initial_state, patient_id)

            # Esperar quiescence después del seed
            quiescent = await self.inspector.wait_for_quiescence(
                timeout_seconds=self.quiescence_timeout
            )
            if not quiescent:
                raise SetupError(
                    f"Failed to reach quiescence after setup (timeout={self.quiescence_timeout}s)"
                )

        except Exception as e:
            raise SetupError(f"Failed to setup scenario: {e}") from e

    async def _seed_initial_state(
        self,
        initial_state: InitialState,
        patient_id: str,
    ) -> None:
        """
        Siembra el estado inicial en la memoria del paciente.

        Args:
            initial_state: Estado inicial a sembrar
            patient_id: ID del paciente
        """
        if not initial_state.entities and not initial_state.relationships:
            logger.debug("No initial state to seed")
            return

        # Convertir entidades al formato esperado por el API
        entities = []
        for entity in initial_state.entities:
            entities.append({
                "name": entity.name,
                "type": entity.type,
                "properties": entity.properties,
                "dikw_layer": entity.dikw_layer,
                "confidence": entity.confidence,
            })

        # Convertir relaciones
        relationships = []
        for rel in initial_state.relationships:
            relationships.append({
                "from": rel.from_entity,
                "to": rel.to_entity,
                "type": rel.type,
                "properties": rel.properties,
            })

        logger.debug(
            f"Seeding {len(entities)} entities and {len(relationships)} relationships"
        )

        await self.inspector.seed_state(
            patient_id=patient_id,
            entities=entities,
            relationships=relationships,
        )

    # ========================================
    # Turn Execution
    # ========================================

    async def _execute_turn(
        self,
        turn: ScenarioTurn,
        patient_id: str,
    ) -> TurnResult:
        """
        Ejecuta un turno de conversación.

        Args:
            turn: Turno a ejecutar
            patient_id: ID del paciente

        Returns:
            TurnResult con los resultados del turno
        """
        logger.debug(f"Executing turn {turn.turn}: {turn.patient_message[:50]}...")

        start_time = time.time()

        try:
            # Run before hooks
            await self._run_hooks(self._before_turn_hooks, turn, patient_id)

            # Tomar snapshot antes
            snapshot_before = await self.inspector.take_snapshot(patient_id)

            # Enviar mensaje y obtener respuesta
            chat_response = await asyncio.wait_for(
                self.inspector.send_chat(patient_id, turn.patient_message),
                timeout=self.turn_timeout,
            )

            agent_response = chat_response.get("response", "")
            detected_intent = chat_response.get("intent", "")

            # Flush pipelines y esperar quiescence
            await self.inspector.flush_pipelines()
            await self.inspector.wait_for_quiescence(
                timeout_seconds=self.quiescence_timeout
            )

            # Tomar snapshot después
            snapshot_after = await self.inspector.take_snapshot(patient_id)

            # Calcular diff
            memory_diff = self.inspector.compute_diff(snapshot_before, snapshot_after)

            # Evaluar aserciones de respuesta
            response_assertions = await self._evaluate_response_assertions(
                turn.response_assertions,
                agent_response,
                turn.patient_message,
                detected_intent=detected_intent,
            )

            # Evaluar aserciones de estado
            state_assertions = await self._evaluate_state_assertions(
                turn.state_assertions,
                snapshot_after,
                memory_diff,
            )

            # Run after hooks
            await self._run_hooks(self._after_turn_hooks, turn, patient_id)

            # Calcular si el turno pasó
            all_passed = (
                all(a.passed for a in response_assertions) and
                all(a.passed for a in state_assertions)
            )

            response_time = (time.time() - start_time) * 1000  # ms

            return TurnResult(
                turn_number=turn.turn,
                patient_message=turn.patient_message,
                agent_response=agent_response,
                response_assertions=response_assertions,
                state_assertions=state_assertions,
                memory_diff=memory_diff,
                response_time_ms=response_time,
                passed=all_passed,
            )

        except asyncio.TimeoutError:
            return TurnResult(
                turn_number=turn.turn,
                patient_message=turn.patient_message,
                agent_response="[TIMEOUT]",
                response_assertions=[
                    AssertionResult(
                        assertion_type="timeout",
                        passed=False,
                        reason="Turn execution timed out",
                        details=f"Timeout after {self.turn_timeout}s",
                        severity=AssertionSeverity.CRITICAL,
                    )
                ],
                state_assertions=[],
                memory_diff=MemoryDiff(),
                response_time_ms=self.turn_timeout * 1000,
                passed=False,
            )

        except Exception as e:
            logger.error(f"Turn {turn.turn} failed: {e}")
            return TurnResult(
                turn_number=turn.turn,
                patient_message=turn.patient_message,
                agent_response=f"[ERROR: {e}]",
                response_assertions=[
                    AssertionResult(
                        assertion_type="error",
                        passed=False,
                        reason="Turn execution error",
                        details=str(e),
                        severity=AssertionSeverity.CRITICAL,
                    )
                ],
                state_assertions=[],
                memory_diff=MemoryDiff(),
                response_time_ms=(time.time() - start_time) * 1000,
                passed=False,
            )

    # ========================================
    # Assertion Evaluation
    # ========================================

    async def _evaluate_response_assertions(
        self,
        assertions: Optional[ResponseAssertions],
        agent_response: str,
        patient_message: str,
        detected_intent: Optional[str] = None,
    ) -> List[AssertionResult]:
        """
        Evalúa las aserciones sobre la respuesta del agente.

        Args:
            assertions: Aserciones a evaluar
            agent_response: Respuesta del agente
            patient_message: Mensaje original del paciente
            detected_intent: Intent detectado por el agente (opcional)

        Returns:
            Lista de resultados de aserciones
        """
        if not assertions:
            return []

        results: List[AssertionResult] = []

        # Build context for evaluators
        context = {
            "patient_message": patient_message,
            "detected_intent": detected_intent or "",
        }

        # Evaluar aserciones determinísticas usando DeterministicEvaluator
        for assertion in assertions.deterministic:
            result = self.deterministic_evaluator.evaluate(
                assertion, agent_response, context
            )
            results.append(result)

        # Evaluar con LLM-as-Judge
        if self.judge_evaluator and assertions.llm_judge:
            # Use async batch evaluation for efficiency
            judge_results = await self.judge_evaluator.evaluate_batch_async(
                assertions.llm_judge,
                agent_response,
                patient_message,
                context,
            )
            results.extend(judge_results)
        elif assertions.llm_judge:
            # No judge evaluator configured - skip with warning
            for assertion in assertions.llm_judge:
                results.append(AssertionResult(
                    assertion_type="llm_judge",
                    passed=True,  # Pass by default when no judge
                    reason=f"LLM Judge skipped: {assertion.criterion}",
                    details="No judge evaluator configured",
                    severity=AssertionSeverity.LOW,
                ))

        return results

    async def _evaluate_state_assertions(
        self,
        assertions: Optional[StateAssertions],
        snapshot: MemorySnapshot,
        diff: MemoryDiff,
    ) -> List[AssertionResult]:
        """
        Evalúa las aserciones sobre el estado de memoria.

        Args:
            assertions: Aserciones a evaluar
            snapshot: Snapshot actual de memoria
            diff: Diff de cambios

        Returns:
            Lista de resultados de aserciones
        """
        if not assertions:
            return []

        results: List[AssertionResult] = []

        # Entities must exist
        for assertion in assertions.entities_must_exist:
            result = self._check_entity_exists(assertion, snapshot)
            results.append(result)

        # Entities must NOT exist
        for assertion in assertions.entities_must_not_exist:
            result = self._check_entity_not_exists(assertion, snapshot)
            results.append(result)

        # Relationships must exist
        for assertion in assertions.relationships_must_exist:
            result = self._check_relationship_exists(assertion, snapshot)
            results.append(result)

        # Relationships must NOT exist
        for assertion in assertions.relationships_must_not_exist:
            result = self._check_relationship_not_exists(assertion, snapshot)
            results.append(result)

        # Property checks
        for assertion in assertions.entity_property_check:
            result = self._check_entity_property(assertion, snapshot)
            results.append(result)

        # DIKW layer checks
        for assertion in assertions.dikw_layer_check:
            result = self._check_dikw_layer(assertion, snapshot)
            results.append(result)

        # Memory diff check
        if assertions.memory_diff_check:
            result = self._check_memory_diff(assertions.memory_diff_check, diff)
            results.append(result)

        return results

    # ========================================
    # State Assertion Evaluators
    # ========================================

    def _check_entity_exists(
        self,
        assertion: EntityAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica que una entidad existe en la memoria."""
        import re

        found = False

        for entity in snapshot.all_entities():
            # Check by name
            if assertion.name:
                if entity.name.lower() == assertion.name.lower():
                    if assertion.type is None or entity.entity_type.lower() == assertion.type.lower():
                        found = True
                        break
            # Check by pattern
            elif assertion.name_pattern:
                if re.search(assertion.name_pattern, entity.name, re.IGNORECASE):
                    if assertion.type is None or entity.entity_type.lower() == assertion.type.lower():
                        found = True
                        break

        return AssertionResult(
            assertion_type="entity_must_exist",
            passed=found,
            reason=assertion.reason,
            details="" if found else f"Entity not found: {assertion.name or assertion.name_pattern}",
            severity=AssertionSeverity.HIGH,
        )

    def _check_entity_not_exists(
        self,
        assertion: EntityAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica que una entidad NO existe en la memoria."""
        import re

        found = False
        found_name = ""

        for entity in snapshot.all_entities():
            if assertion.name:
                if entity.name.lower() == assertion.name.lower():
                    if assertion.type is None or entity.entity_type.lower() == assertion.type.lower():
                        found = True
                        found_name = entity.name
                        break
            elif assertion.name_pattern:
                if re.search(assertion.name_pattern, entity.name, re.IGNORECASE):
                    if assertion.type is None or entity.entity_type.lower() == assertion.type.lower():
                        found = True
                        found_name = entity.name
                        break

        return AssertionResult(
            assertion_type="entity_must_not_exist",
            passed=not found,
            reason=assertion.reason,
            details="" if not found else f"Entity found but should not exist: {found_name}",
            severity=AssertionSeverity.HIGH,
        )

    def _check_relationship_exists(
        self,
        assertion: RelationshipAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica que una relación existe en la memoria."""
        import re

        found = False

        for rel in snapshot.all_relationships():
            # Match from
            from_match = True
            if assertion.from_name:
                from_match = rel.from_name.lower() == assertion.from_name.lower()
            elif assertion.from_pattern:
                from_match = bool(re.search(assertion.from_pattern, rel.from_name, re.IGNORECASE))

            # Match to
            to_match = True
            if assertion.to_name:
                to_match = rel.to_name.lower() == assertion.to_name.lower()
            elif assertion.to_pattern:
                to_match = bool(re.search(assertion.to_pattern, rel.to_name, re.IGNORECASE))

            # Match type
            type_match = True
            if assertion.type_name:
                type_match = rel.relationship_type.upper() == assertion.type_name.upper()
            elif assertion.type_pattern:
                type_match = bool(re.search(assertion.type_pattern, rel.relationship_type, re.IGNORECASE))

            if from_match and to_match and type_match:
                found = True
                break

        return AssertionResult(
            assertion_type="relationship_must_exist",
            passed=found,
            reason=assertion.reason,
            details="" if found else f"Relationship not found",
            severity=AssertionSeverity.MEDIUM,
        )

    def _check_relationship_not_exists(
        self,
        assertion: RelationshipAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica que una relación NO existe en la memoria."""
        import re

        found = False

        for rel in snapshot.all_relationships():
            from_match = True
            if assertion.from_name:
                from_match = rel.from_name.lower() == assertion.from_name.lower()
            elif assertion.from_pattern:
                from_match = bool(re.search(assertion.from_pattern, rel.from_name, re.IGNORECASE))

            to_match = True
            if assertion.to_name:
                to_match = rel.to_name.lower() == assertion.to_name.lower()
            elif assertion.to_pattern:
                to_match = bool(re.search(assertion.to_pattern, rel.to_name, re.IGNORECASE))

            type_match = True
            if assertion.type_name:
                type_match = rel.relationship_type.upper() == assertion.type_name.upper()
            elif assertion.type_pattern:
                type_match = bool(re.search(assertion.type_pattern, rel.relationship_type, re.IGNORECASE))

            if from_match and to_match and type_match:
                found = True
                break

        return AssertionResult(
            assertion_type="relationship_must_not_exist",
            passed=not found,
            reason=assertion.reason,
            details="" if not found else "Relationship found but should not exist",
            severity=AssertionSeverity.MEDIUM,
        )

    def _check_entity_property(
        self,
        assertion: PropertyAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica el valor de una propiedad de entidad."""
        entity = snapshot.get_entity_by_name(assertion.name)

        if not entity:
            return AssertionResult(
                assertion_type="entity_property_check",
                passed=False,
                reason=assertion.reason,
                details=f"Entity not found: {assertion.name}",
                severity=AssertionSeverity.MEDIUM,
            )

        actual_value = entity.properties.get(assertion.property)
        expected_value = assertion.expected

        # Comparación flexible (case-insensitive para strings)
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            passed = actual_value.lower() == expected_value.lower()
        else:
            passed = actual_value == expected_value

        return AssertionResult(
            assertion_type="entity_property_check",
            passed=passed,
            reason=assertion.reason,
            details="" if passed else f"Property mismatch: {assertion.property}={actual_value}, expected={expected_value}",
            severity=AssertionSeverity.MEDIUM,
        )

    def _check_dikw_layer(
        self,
        assertion: LayerAssertion,
        snapshot: MemorySnapshot,
    ) -> AssertionResult:
        """Verifica la capa DIKW de una entidad."""
        entity = snapshot.get_entity_by_name(assertion.name)

        if not entity:
            return AssertionResult(
                assertion_type="dikw_layer_check",
                passed=False,
                reason=assertion.reason,
                details=f"Entity not found: {assertion.name}",
                severity=AssertionSeverity.MEDIUM,
            )

        actual_layer = entity.dikw_layer.value if entity.dikw_layer else None
        expected_layer = assertion.expected_layer.upper()

        if assertion.must_be_in:
            passed = actual_layer == expected_layer
            details = "" if passed else f"Layer mismatch: {actual_layer} != {expected_layer}"
        else:
            passed = actual_layer != expected_layer
            details = "" if passed else f"Entity should not be in layer {expected_layer}"

        return AssertionResult(
            assertion_type="dikw_layer_check",
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )

    def _check_memory_diff(
        self,
        assertion: DiffAssertion,
        diff: MemoryDiff,
    ) -> AssertionResult:
        """Verifica que no haya cambios inesperados en memoria."""
        unexpected_entities = len(diff.entities_added)
        unexpected_rels = len(diff.relationships_added)

        passed = (
            unexpected_entities <= assertion.max_unexpected_entities and
            unexpected_rels <= assertion.max_unexpected_relationships
        )

        details = ""
        if not passed:
            details = (
                f"Unexpected changes: {unexpected_entities} entities "
                f"(max {assertion.max_unexpected_entities}), "
                f"{unexpected_rels} relationships "
                f"(max {assertion.max_unexpected_relationships})"
            )

        return AssertionResult(
            assertion_type="memory_diff_check",
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.HIGH,
        )

    # ========================================
    # Helpers
    # ========================================

    def _get_patient_id(self, scenario: Scenario) -> str:
        """Obtiene el patient_id para el escenario."""
        if scenario.initial_state and scenario.initial_state.patient_id:
            return scenario.initial_state.patient_id
        # Generar ID único basado en el escenario
        return f"eval-{scenario.id}-{int(time.time())}"

    def _has_critical_failure(self, turn_result: TurnResult) -> bool:
        """Verifica si hay una falla crítica en el turno."""
        for assertion in turn_result.all_assertions:
            if not assertion.passed and assertion.severity == AssertionSeverity.CRITICAL:
                return True
        return False

    async def _call_evaluator(
        self,
        evaluator: Callable,
        assertion: Any,
        response: str,
        patient_message: str,
    ) -> AssertionResult:
        """Llama a un evaluador (sync o async)."""
        if asyncio.iscoroutinefunction(evaluator):
            return await evaluator(assertion, response, patient_message)
        else:
            return evaluator(assertion, response, patient_message)

    async def _run_hooks(
        self,
        hooks: List[Callable],
        *args,
        **kwargs,
    ) -> None:
        """Ejecuta una lista de hooks."""
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(*args, **kwargs)
                else:
                    hook(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Hook error: {e}")

    # ========================================
    # Hook Registration
    # ========================================

    def add_before_scenario_hook(self, hook: Callable) -> None:
        """Registra un hook para antes de cada escenario."""
        self._before_scenario_hooks.append(hook)

    def add_after_scenario_hook(self, hook: Callable) -> None:
        """Registra un hook para después de cada escenario."""
        self._after_scenario_hooks.append(hook)

    def add_before_turn_hook(self, hook: Callable) -> None:
        """Registra un hook para antes de cada turno."""
        self._before_turn_hooks.append(hook)

    def add_after_turn_hook(self, hook: Callable) -> None:
        """Registra un hook para después de cada turno."""
        self._after_turn_hooks.append(hook)
