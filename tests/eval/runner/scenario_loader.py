"""
Scenario Loader - Carga y parseo de escenarios YAML.

Este módulo proporciona la clase ScenarioLoader que carga escenarios
de evaluación desde archivos YAML, resuelve fixtures, y valida
la estructura de los escenarios.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from pydantic import ValidationError

from .scenario_models import (
    Scenario,
    ScenarioTurn,
    InitialState,
    InitialStateEntity,
    InitialStateRelationship,
    ResponseAssertions,
    StateAssertions,
    DeterministicAssertion,
    JudgeAssertion,
    EntityAssertion,
    RelationshipAssertion,
    PropertyAssertion,
    LayerAssertion,
    DiffAssertion,
    PatientStateFixture,
    ScenarioSuite,
)

logger = logging.getLogger(__name__)


class ScenarioLoaderError(Exception):
    """Error al cargar escenarios."""
    pass


class ScenarioValidationError(ScenarioLoaderError):
    """Error de validación de escenario."""
    pass


class FixtureNotFoundError(ScenarioLoaderError):
    """Error cuando no se encuentra un fixture."""
    pass


class ScenarioLoader:
    """
    Carga y parsea escenarios de evaluación desde archivos YAML.

    Features:
    - Carga escenarios individuales o directorios completos
    - Resuelve referencias a fixtures de estado de paciente
    - Valida estructura de escenarios
    - Soporta filtrado por categoría, severidad, tags
    """

    def __init__(
        self,
        scenarios_dir: str,
        fixtures_dir: Optional[str] = None,
    ):
        """
        Inicializa el ScenarioLoader.

        Args:
            scenarios_dir: Directorio raíz de escenarios YAML
            fixtures_dir: Directorio de fixtures de estado de paciente
        """
        self.scenarios_dir = Path(scenarios_dir)
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else self.scenarios_dir.parent / "fixtures" / "patient_states"

        # Cache de fixtures cargados
        self._fixtures_cache: Dict[str, PatientStateFixture] = {}

        logger.info(
            f"ScenarioLoader initialized: scenarios={self.scenarios_dir}, "
            f"fixtures={self.fixtures_dir}"
        )

    # ========================================
    # Scenario Loading
    # ========================================

    def load_scenario(self, path: str) -> Scenario:
        """
        Carga un escenario desde un archivo YAML.

        Args:
            path: Ruta al archivo YAML (absoluta o relativa a scenarios_dir)

        Returns:
            Scenario parseado y validado

        Raises:
            ScenarioLoaderError: Si falla la carga
            ScenarioValidationError: Si el escenario no es válido
        """
        # Resolver ruta
        scenario_path = Path(path)
        if not scenario_path.is_absolute():
            scenario_path = self.scenarios_dir / path

        if not scenario_path.exists():
            raise ScenarioLoaderError(f"Scenario file not found: {scenario_path}")

        logger.debug(f"Loading scenario: {scenario_path}")

        try:
            with open(scenario_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data:
                raise ScenarioLoaderError(f"Empty scenario file: {scenario_path}")

            # Resolver fixture si está referenciado
            if data.get("initial_state", {}).get("fixture"):
                data = self._resolve_fixture(data)

            # Parsear y validar
            scenario = self._parse_scenario(data, scenario_path)

            # Validar que hay al menos una aserción por turno
            self._validate_assertions(scenario, scenario_path)

            logger.info(f"Loaded scenario: {scenario.id} ({len(scenario.turns)} turns)")
            return scenario

        except yaml.YAMLError as e:
            raise ScenarioLoaderError(f"YAML parse error in {scenario_path}: {e}") from e
        except ValidationError as e:
            raise ScenarioValidationError(f"Validation error in {scenario_path}: {e}") from e

    def load_all_scenarios(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        tag: Optional[str] = None,
        include_subdirs: bool = True,
    ) -> List[Scenario]:
        """
        Carga todos los escenarios del directorio.

        Args:
            category: Filtrar por categoría
            severity: Filtrar por severidad
            tag: Filtrar por tag
            include_subdirs: Incluir subdirectorios

        Returns:
            Lista de escenarios ordenados por severidad
        """
        scenarios = []

        if not self.scenarios_dir.exists():
            logger.warning(f"Scenarios directory not found: {self.scenarios_dir}")
            return []

        # Encontrar archivos YAML
        pattern = "**/*.yaml" if include_subdirs else "*.yaml"
        yaml_files = list(self.scenarios_dir.glob(pattern))
        yaml_files.extend(self.scenarios_dir.glob(pattern.replace(".yaml", ".yml")))

        logger.info(f"Found {len(yaml_files)} scenario files")

        for yaml_path in yaml_files:
            try:
                scenario = self.load_scenario(str(yaml_path))

                # Aplicar filtros
                if category and scenario.category != category:
                    continue
                if severity and scenario.severity != severity:
                    continue
                if tag and tag not in scenario.tags:
                    continue

                scenarios.append(scenario)

            except Exception as e:
                logger.warning(f"Failed to load scenario {yaml_path}: {e}")

        # Ordenar por severidad (críticos primero)
        scenarios.sort(key=lambda s: s.get_severity_order())

        logger.info(f"Loaded {len(scenarios)} scenarios (filtered)")
        return scenarios

    def load_suite(self, name: str = "all") -> ScenarioSuite:
        """
        Carga una suite de escenarios.

        Args:
            name: Nombre de la suite o "all" para todos

        Returns:
            ScenarioSuite con los escenarios cargados
        """
        scenarios = self.load_all_scenarios()
        return ScenarioSuite(
            name=name,
            description=f"Loaded from {self.scenarios_dir}",
            scenarios=scenarios,
        )

    # ========================================
    # Fixture Resolution
    # ========================================

    def _resolve_fixture(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resuelve referencia a fixture en el estado inicial.

        Args:
            scenario_data: Datos del escenario con referencia a fixture

        Returns:
            Datos del escenario con fixture resuelto
        """
        fixture_ref = scenario_data.get("initial_state", {}).get("fixture")
        if not fixture_ref:
            return scenario_data

        fixture = self._load_fixture(fixture_ref)

        # Merge fixture con estado inicial del escenario
        initial_state = scenario_data.get("initial_state", {})

        # Las entidades del escenario se añaden a las del fixture
        fixture_entities = [e.model_dump() for e in fixture.entities]
        scenario_entities = initial_state.get("entities", [])
        initial_state["entities"] = fixture_entities + scenario_entities

        # Lo mismo para relaciones
        fixture_rels = [r.model_dump(by_alias=True) for r in fixture.relationships]
        scenario_rels = initial_state.get("relationships", [])
        initial_state["relationships"] = fixture_rels + scenario_rels

        # Remover referencia a fixture
        del initial_state["fixture"]

        scenario_data["initial_state"] = initial_state
        return scenario_data

    def _load_fixture(self, fixture_ref: str) -> PatientStateFixture:
        """
        Carga un fixture de estado de paciente.

        Args:
            fixture_ref: Nombre del fixture (sin extensión)

        Returns:
            PatientStateFixture cargado

        Raises:
            FixtureNotFoundError: Si no se encuentra el fixture
        """
        # Check cache
        if fixture_ref in self._fixtures_cache:
            return self._fixtures_cache[fixture_ref]

        # Buscar archivo
        fixture_path = self.fixtures_dir / f"{fixture_ref}.yaml"
        if not fixture_path.exists():
            fixture_path = self.fixtures_dir / f"{fixture_ref}.yml"

        if not fixture_path.exists():
            raise FixtureNotFoundError(f"Fixture not found: {fixture_ref}")

        logger.debug(f"Loading fixture: {fixture_path}")

        try:
            with open(fixture_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Parsear entidades
            entities = []
            for e in data.get("entities", []):
                entities.append(InitialStateEntity(
                    name=e.get("name"),
                    type=e.get("type"),
                    properties=e.get("properties", {}),
                    dikw_layer=e.get("dikw_layer", "PERCEPTION"),
                    confidence=e.get("confidence", 0.75),
                ))

            # Parsear relaciones
            relationships = []
            for r in data.get("relationships", []):
                relationships.append(InitialStateRelationship(
                    from_entity=r.get("from"),
                    to_entity=r.get("to"),
                    type=r.get("type"),
                    properties=r.get("properties", {}),
                ))

            fixture = PatientStateFixture(
                id=fixture_ref,
                name=data.get("name", fixture_ref),
                description=data.get("description", ""),
                entities=entities,
                relationships=relationships,
            )

            self._fixtures_cache[fixture_ref] = fixture
            return fixture

        except yaml.YAMLError as e:
            raise ScenarioLoaderError(f"YAML error in fixture {fixture_path}: {e}") from e

    # ========================================
    # Parsing
    # ========================================

    def _parse_scenario(self, data: Dict[str, Any], path: Path) -> Scenario:
        """
        Parsea datos YAML a un Scenario.

        Args:
            data: Datos del YAML
            path: Ruta del archivo (para generar ID por defecto)

        Returns:
            Scenario parseado
        """
        # Generar ID por defecto desde el nombre del archivo
        default_id = path.stem

        # Parsear initial_state
        initial_state = None
        if data.get("initial_state"):
            is_data = data["initial_state"]
            entities = []
            for e in is_data.get("entities", []):
                entities.append(InitialStateEntity(
                    name=e.get("name"),
                    type=e.get("type"),
                    properties=e.get("properties", {}),
                    dikw_layer=e.get("dikw_layer", "PERCEPTION"),
                    confidence=e.get("confidence", 0.75),
                ))

            relationships = []
            for r in is_data.get("relationships", []):
                relationships.append(InitialStateRelationship(
                    from_entity=r.get("from"),
                    to_entity=r.get("to"),
                    type=r.get("type"),
                    properties=r.get("properties", {}),
                ))

            initial_state = InitialState(
                patient_id=is_data.get("patient_id"),
                fixture=is_data.get("fixture"),
                entities=entities,
                relationships=relationships,
            )

        # Parsear turns
        turns = []
        for t in data.get("turns", []):
            turn = self._parse_turn(t)
            turns.append(turn)

        return Scenario(
            id=data.get("id", default_id),
            name=data.get("name", default_id),
            description=data.get("description", ""),
            category=data.get("category", "unknown"),
            severity=data.get("severity", "medium"),
            tags=data.get("tags", []),
            created_from_bug=data.get("created_from_bug"),
            initial_state=initial_state,
            turns=turns,
        )

    def _parse_turn(self, data: Dict[str, Any]) -> ScenarioTurn:
        """Parsea un turno de escenario."""
        # Parse response_assertions
        response_assertions = None
        if data.get("response_assertions"):
            ra_data = data["response_assertions"]
            deterministic = []
            for d in ra_data.get("deterministic", []):
                deterministic.append(DeterministicAssertion(**d))

            llm_judge = []
            for j in ra_data.get("llm_judge", []):
                llm_judge.append(JudgeAssertion(**j))

            response_assertions = ResponseAssertions(
                deterministic=deterministic,
                llm_judge=llm_judge,
            )

        # Parse state_assertions
        state_assertions = None
        if data.get("state_assertions"):
            sa_data = data["state_assertions"]

            entities_must_exist = [
                EntityAssertion(**e)
                for e in sa_data.get("entities_must_exist", [])
            ]
            entities_must_not_exist = [
                EntityAssertion(**e)
                for e in sa_data.get("entities_must_not_exist", [])
            ]
            relationships_must_exist = [
                RelationshipAssertion(**r)
                for r in sa_data.get("relationships_must_exist", [])
            ]
            relationships_must_not_exist = [
                RelationshipAssertion(**r)
                for r in sa_data.get("relationships_must_not_exist", [])
            ]
            entity_property_check = [
                PropertyAssertion(**p)
                for p in sa_data.get("entity_property_check", [])
            ]
            dikw_layer_check = [
                LayerAssertion(**l)
                for l in sa_data.get("dikw_layer_check", [])
            ]

            memory_diff_check = None
            if sa_data.get("memory_diff_check"):
                memory_diff_check = DiffAssertion(**sa_data["memory_diff_check"])

            state_assertions = StateAssertions(
                entities_must_exist=entities_must_exist,
                entities_must_not_exist=entities_must_not_exist,
                relationships_must_exist=relationships_must_exist,
                relationships_must_not_exist=relationships_must_not_exist,
                entity_property_check=entity_property_check,
                dikw_layer_check=dikw_layer_check,
                memory_diff_check=memory_diff_check,
            )

        return ScenarioTurn(
            turn=data.get("turn", 1),
            patient_message=data.get("patient_message", ""),
            expected_intent=data.get("expected_intent"),
            response_assertions=response_assertions,
            state_assertions=state_assertions,
        )

    # ========================================
    # Validation
    # ========================================

    def _validate_assertions(self, scenario: Scenario, path: Path) -> None:
        """
        Valida que cada turno tenga al menos una aserción.

        Args:
            scenario: Escenario a validar
            path: Ruta del archivo para mensajes de error

        Raises:
            ScenarioValidationError: Si algún turno no tiene aserciones
        """
        for turn in scenario.turns:
            if not turn.has_assertions():
                raise ScenarioValidationError(
                    f"Turn {turn.turn} in {path} must have at least one assertion "
                    "(response_assertions or state_assertions)"
                )

    # ========================================
    # Utilities
    # ========================================

    def get_categories(self) -> List[str]:
        """Retorna las categorías disponibles basadas en subdirectorios."""
        if not self.scenarios_dir.exists():
            return []

        categories = []
        for item in self.scenarios_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                categories.append(item.name)

        return sorted(categories)

    def get_fixtures(self) -> List[str]:
        """Retorna los fixtures disponibles."""
        if not self.fixtures_dir.exists():
            return []

        fixtures = []
        for item in self.fixtures_dir.glob("*.yaml"):
            fixtures.append(item.stem)
        for item in self.fixtures_dir.glob("*.yml"):
            fixtures.append(item.stem)

        return sorted(set(fixtures))

    def clear_fixture_cache(self) -> None:
        """Limpia el cache de fixtures."""
        self._fixtures_cache.clear()
