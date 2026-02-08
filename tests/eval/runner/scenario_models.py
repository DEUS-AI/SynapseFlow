"""
Modelos para escenarios de evaluación.

Este módulo define los modelos Pydantic que representan escenarios
de evaluación definidos en archivos YAML.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ========================================
# Enums
# ========================================

class ScenarioSeverity(str, Enum):
    """Severidad de un escenario de evaluación."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScenarioCategory(str, Enum):
    """Categoría de un escenario de evaluación."""
    REGRESSION = "regression"
    ENTITY_EXTRACTION = "entity_extraction"
    MEMORY_POLLUTION = "memory_pollution"
    TEMPORAL_REASONING = "temporal_reasoning"
    CONVERSATIONAL_SAFETY = "conversational_safety"
    MEDICAL_ACCURACY = "medical_accuracy"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"


# ========================================
# Assertion Models - Response
# ========================================

class DeterministicAssertion(BaseModel):
    """Aserción determinística sobre la respuesta del agente."""
    type: str = Field(..., description="Tipo de aserción")
    values: Optional[List[str]] = Field(None, description="Valores a verificar")
    pattern: Optional[str] = Field(None, description="Patrón regex")
    reference: Optional[str] = Field(None, description="Texto de referencia para similarity")
    threshold: Optional[float] = Field(None, ge=0, le=1, description="Umbral para similarity")
    chars: Optional[int] = Field(None, gt=0, description="Límite de caracteres")
    expected: Optional[str] = Field(None, description="Valor esperado")
    reason: str = Field(..., description="Razón de la aserción")


class JudgeAssertion(BaseModel):
    """Aserción LLM-as-Judge sobre la respuesta del agente."""
    criterion: str = Field(..., description="Criterio de evaluación")
    rubric: Optional[str] = Field(None, description="Rúbrica personalizada")
    min_score: int = Field(3, ge=1, le=5, description="Score mínimo aceptable")


class ResponseAssertions(BaseModel):
    """Aserciones sobre la respuesta del agente."""
    deterministic: List[DeterministicAssertion] = Field(default_factory=list)
    llm_judge: List[JudgeAssertion] = Field(default_factory=list)


# ========================================
# Assertion Models - State
# ========================================

class EntityAssertion(BaseModel):
    """Aserción sobre existencia de entidad."""
    name: Optional[str] = Field(None, description="Nombre exacto")
    name_pattern: Optional[str] = Field(None, description="Patrón regex del nombre")
    type: Optional[str] = Field(None, description="Tipo de entidad")
    reason: str = Field(..., description="Razón de la aserción")


class RelationshipAssertion(BaseModel):
    """Aserción sobre existencia de relación."""
    from_name: Optional[str] = Field(None, description="Nombre de entidad origen")
    from_pattern: Optional[str] = Field(None, description="Patrón de entidad origen")
    to_name: Optional[str] = Field(None, description="Nombre de entidad destino")
    to_pattern: Optional[str] = Field(None, description="Patrón de entidad destino")
    type_name: Optional[str] = Field(None, description="Tipo de relación")
    type_pattern: Optional[str] = Field(None, description="Patrón de tipo de relación")
    reason: str = Field(..., description="Razón de la aserción")


class PropertyAssertion(BaseModel):
    """Aserción sobre propiedad de entidad."""
    name: str = Field(..., description="Nombre de la entidad")
    property: str = Field(..., description="Nombre de la propiedad")
    expected: Any = Field(..., description="Valor esperado")
    reason: str = Field(..., description="Razón de la aserción")


class LayerAssertion(BaseModel):
    """Aserción sobre capa DIKW de entidad."""
    name: str = Field(..., description="Nombre de la entidad")
    expected_layer: str = Field(..., description="Capa esperada")
    must_be_in: bool = Field(True, description="True: debe estar en la capa")
    reason: str = Field(..., description="Razón de la aserción")


class DiffAssertion(BaseModel):
    """Aserción sobre cambios inesperados en memoria."""
    max_unexpected_entities: int = Field(0, ge=0, description="Máximo de entidades inesperadas")
    max_unexpected_relationships: int = Field(0, ge=0, description="Máximo de relaciones inesperadas")
    reason: str = Field("No unexpected memory writes should occur", description="Razón")


class StateAssertions(BaseModel):
    """Aserciones sobre el estado de memoria."""
    entities_must_exist: List[EntityAssertion] = Field(default_factory=list)
    entities_must_not_exist: List[EntityAssertion] = Field(default_factory=list)
    relationships_must_exist: List[RelationshipAssertion] = Field(default_factory=list)
    relationships_must_not_exist: List[RelationshipAssertion] = Field(default_factory=list)
    entity_property_check: List[PropertyAssertion] = Field(default_factory=list)
    dikw_layer_check: List[LayerAssertion] = Field(default_factory=list)
    memory_diff_check: Optional[DiffAssertion] = None


# ========================================
# Scenario Turn
# ========================================

class ScenarioTurn(BaseModel):
    """Un turno de conversación en el escenario."""
    turn: int = Field(..., ge=1, description="Número de turno")
    patient_message: str = Field(..., min_length=1, description="Mensaje del paciente")
    expected_intent: Optional[str] = Field(None, description="Intent esperado")
    response_assertions: Optional[ResponseAssertions] = None
    state_assertions: Optional[StateAssertions] = None

    @field_validator('patient_message')
    @classmethod
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("patient_message cannot be empty")
        return v.strip()

    def has_assertions(self) -> bool:
        """Verifica si el turno tiene al menos una aserción."""
        has_response = (
            self.response_assertions is not None and
            (self.response_assertions.deterministic or self.response_assertions.llm_judge)
        )
        has_state = (
            self.state_assertions is not None and
            (
                self.state_assertions.entities_must_exist or
                self.state_assertions.entities_must_not_exist or
                self.state_assertions.relationships_must_exist or
                self.state_assertions.relationships_must_not_exist or
                self.state_assertions.entity_property_check or
                self.state_assertions.dikw_layer_check or
                self.state_assertions.memory_diff_check
            )
        )
        return has_response or has_state


# ========================================
# Initial State
# ========================================

class InitialStateEntity(BaseModel):
    """Entidad para el estado inicial."""
    name: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    dikw_layer: str = Field("PERCEPTION", description="Capa DIKW inicial")
    confidence: float = Field(0.75, ge=0, le=1)


class InitialStateRelationship(BaseModel):
    """Relación para el estado inicial."""
    model_config = ConfigDict(populate_by_name=True)

    from_entity: str = Field(..., alias="from")
    to_entity: str = Field(..., alias="to")
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class InitialState(BaseModel):
    """Estado inicial del paciente para el escenario."""
    patient_id: Optional[str] = Field(None, description="ID del paciente (se genera si no se provee)")
    fixture: Optional[str] = Field(None, description="Referencia a fixture YAML")
    entities: List[InitialStateEntity] = Field(default_factory=list)
    relationships: List[InitialStateRelationship] = Field(default_factory=list)


# ========================================
# Complete Scenario
# ========================================

class Scenario(BaseModel):
    """Escenario completo de evaluación."""
    id: str = Field(..., min_length=1, description="ID único del escenario")
    name: str = Field(..., min_length=1, description="Nombre descriptivo")
    description: str = Field("", description="Descripción detallada")
    category: str = Field(..., description="Categoría del escenario")
    severity: str = Field("medium", description="Severidad")
    tags: List[str] = Field(default_factory=list, description="Tags para filtrado")
    created_from_bug: Optional[str] = Field(None, description="ID de bug que originó el escenario")
    initial_state: Optional[InitialState] = None
    turns: List[ScenarioTurn] = Field(..., min_length=1)

    @field_validator('turns')
    @classmethod
    def validate_turns(cls, v):
        if not v:
            raise ValueError("Scenario must have at least one turn")
        # Verificar que los turnos están numerados correctamente
        for i, turn in enumerate(v, 1):
            if turn.turn != i:
                raise ValueError(f"Turn numbers must be sequential. Expected {i}, got {turn.turn}")
        return v

    def get_severity_order(self) -> int:
        """Retorna orden numérico de severidad para sorting."""
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return order.get(self.severity.lower(), 99)

    @property
    def is_regression(self) -> bool:
        """Verifica si es un escenario de regresión."""
        return self.category == "regression" or self.created_from_bug is not None

    @property
    def is_critical(self) -> bool:
        """Verifica si es un escenario crítico."""
        return self.severity.lower() == "critical"


# ========================================
# Patient State Fixture
# ========================================

class PatientStateFixture(BaseModel):
    """Fixture reutilizable de estado de paciente."""
    id: str = Field(..., description="ID del fixture")
    name: str = Field(..., description="Nombre descriptivo")
    description: str = Field("", description="Descripción")
    entities: List[InitialStateEntity] = Field(default_factory=list)
    relationships: List[InitialStateRelationship] = Field(default_factory=list)


# ========================================
# Scenario Suite
# ========================================

class ScenarioSuite(BaseModel):
    """Suite de escenarios para ejecución."""
    name: str = Field(..., description="Nombre de la suite")
    description: str = Field("", description="Descripción")
    scenarios: List[Scenario] = Field(default_factory=list)

    @property
    def total_scenarios(self) -> int:
        return len(self.scenarios)

    @property
    def critical_count(self) -> int:
        return sum(1 for s in self.scenarios if s.is_critical)

    @property
    def regression_count(self) -> int:
        return sum(1 for s in self.scenarios if s.is_regression)

    def filter_by_category(self, category: str) -> List[Scenario]:
        """Filtra escenarios por categoría."""
        return [s for s in self.scenarios if s.category == category]

    def filter_by_severity(self, severity: str) -> List[Scenario]:
        """Filtra escenarios por severidad."""
        return [s for s in self.scenarios if s.severity == severity]

    def filter_by_tag(self, tag: str) -> List[Scenario]:
        """Filtra escenarios por tag."""
        return [s for s in self.scenarios if tag in s.tags]

    def sort_by_severity(self) -> List[Scenario]:
        """Ordena escenarios por severidad (críticos primero)."""
        return sorted(self.scenarios, key=lambda s: s.get_severity_order())
