"""
Tests para el Memory Inspector.

Estos tests verifican:
1. Normalización de texto para comparación
2. Cálculo de diffs entre snapshots
3. Detección de entidades/relaciones añadidas/eliminadas/modificadas
4. Operaciones del cliente HTTP
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from tests.eval.runner.models import (
    MemorySnapshot,
    MemoryDiff,
    MemoryEntity,
    MemoryRelationship,
    Mem0Memory,
    EntityChange,
    RedisLayerSnapshot,
    Mem0LayerSnapshot,
    GraphitiLayerSnapshot,
    Neo4jDIKWLayerSnapshot,
    MemoryLayer,
    DIKWLayer,
    normalize_text,
    entities_match,
    relationships_match,
)
from tests.eval.runner.memory_inspector import (
    MemoryInspector,
    MemoryInspectorError,
    QuiescenceTimeoutError,
)


class TestNormalizeText:
    """Tests para la función normalize_text."""

    def test_normalize_lowercase(self):
        """Convierte a minúsculas."""
        assert normalize_text("METFORMIN") == "metformin"
        assert normalize_text("Diabetes Tipo 2") == "diabetes tipo 2"

    def test_normalize_strip(self):
        """Elimina espacios extra."""
        assert normalize_text("  metformin  ") == "metformin"
        assert normalize_text("diabetes   tipo   2") == "diabetes tipo 2"

    def test_normalize_accents(self):
        """Elimina acentos/diacríticos."""
        assert normalize_text("hipertensión") == "hipertension"
        assert normalize_text("María") == "maria"
        assert normalize_text("niño") == "nino"
        assert normalize_text("corazón") == "corazon"

    def test_normalize_empty(self):
        """Maneja strings vacíos."""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_normalize_mixed(self):
        """Maneja casos mixtos."""
        assert normalize_text("  HIPERTENSIÓN Arterial  ") == "hipertension arterial"


class TestEntitiesMatch:
    """Tests para la función entities_match."""

    def test_match_same_name(self):
        """Match con mismo nombre normalizado."""
        e1 = MemoryEntity(name="Metformin", entity_type="Medication")
        e2 = MemoryEntity(name="metformin", entity_type="Medication")
        assert entities_match(e1, e2)

    def test_match_accents(self):
        """Match ignorando acentos."""
        e1 = MemoryEntity(name="Hipertensión", entity_type="Condition")
        e2 = MemoryEntity(name="Hipertension", entity_type="Condition")
        assert entities_match(e1, e2)

    def test_no_match_different_name(self):
        """No match con nombres diferentes."""
        e1 = MemoryEntity(name="Metformin", entity_type="Medication")
        e2 = MemoryEntity(name="Lisinopril", entity_type="Medication")
        assert not entities_match(e1, e2)

    def test_no_match_different_type(self):
        """No match con tipos diferentes."""
        e1 = MemoryEntity(name="Diabetes", entity_type="Condition")
        e2 = MemoryEntity(name="Diabetes", entity_type="Medication")
        assert not entities_match(e1, e2, match_type=True)
        assert entities_match(e1, e2, match_type=False)


class TestRelationshipsMatch:
    """Tests para la función relationships_match."""

    def test_match_same(self):
        """Match con misma relación."""
        r1 = MemoryRelationship(
            from_name="Metformin",
            to_name="Diabetes",
            relationship_type="TREATS",
        )
        r2 = MemoryRelationship(
            from_name="metformin",
            to_name="diabetes",
            relationship_type="treats",
        )
        assert relationships_match(r1, r2)

    def test_no_match_different_type(self):
        """No match con tipo diferente."""
        r1 = MemoryRelationship(
            from_name="Metformin",
            to_name="Diabetes",
            relationship_type="TREATS",
        )
        r2 = MemoryRelationship(
            from_name="Metformin",
            to_name="Diabetes",
            relationship_type="CAUSES",
        )
        assert not relationships_match(r1, r2)


class TestMemoryEntity:
    """Tests para el modelo MemoryEntity."""

    def test_normalized_key(self):
        """Genera clave normalizada correctamente."""
        entity = MemoryEntity(name="Hipertensión", entity_type="Condition")
        assert entity.normalized_key() == "hipertension:condition"

    def test_hash_equality(self):
        """Entidades con mismo key son iguales para sets."""
        e1 = MemoryEntity(name="Metformin", entity_type="Medication")
        e2 = MemoryEntity(name="METFORMIN", entity_type="medication")
        assert hash(e1) == hash(e2)
        assert e1 == e2


class TestMemorySnapshot:
    """Tests para el modelo MemorySnapshot."""

    def test_all_entities(self):
        """Retorna todas las entidades de todas las capas."""
        snapshot = MemorySnapshot(
            patient_id="test-patient",
            timestamp=datetime.now(UTC),
            graphiti=GraphitiLayerSnapshot(
                entities=[MemoryEntity(name="E1", entity_type="Type1")],
            ),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[MemoryEntity(name="E2", entity_type="Type2")],
                semantic=[MemoryEntity(name="E3", entity_type="Type3")],
            ),
        )

        all_entities = snapshot.all_entities()
        assert len(all_entities) == 3
        names = [e.name for e in all_entities]
        assert "E1" in names
        assert "E2" in names
        assert "E3" in names

    def test_get_entity_by_name(self):
        """Busca entidad por nombre."""
        snapshot = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[
                    MemoryEntity(name="Metformin", entity_type="Medication"),
                    MemoryEntity(name="Diabetes", entity_type="Condition"),
                ],
            ),
        )

        entity = snapshot.get_entity_by_name("metformin")
        assert entity is not None
        assert entity.name == "Metformin"

        entity = snapshot.get_entity_by_name("NonExistent")
        assert entity is None

    def test_has_entity(self):
        """Verifica existencia de entidad."""
        snapshot = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[
                    MemoryEntity(name="Metformin", entity_type="Medication"),
                ],
            ),
        )

        assert snapshot.has_entity("Metformin")
        assert snapshot.has_entity("metformin")
        assert not snapshot.has_entity("Lisinopril")


class TestMemoryDiff:
    """Tests para el modelo MemoryDiff."""

    def test_has_changes_empty(self):
        """Diff vacío no tiene cambios."""
        diff = MemoryDiff()
        assert not diff.has_changes

    def test_has_changes_with_added(self):
        """Diff con entidades añadidas tiene cambios."""
        diff = MemoryDiff(
            entities_added=[MemoryEntity(name="E1", entity_type="T1")]
        )
        assert diff.has_changes

    def test_entity_changes_count(self):
        """Cuenta cambios de entidades."""
        diff = MemoryDiff(
            entities_added=[
                MemoryEntity(name="E1", entity_type="T1"),
                MemoryEntity(name="E2", entity_type="T2"),
            ],
            entities_removed=[
                MemoryEntity(name="E3", entity_type="T3"),
            ],
        )
        assert diff.entity_changes_count == 3

    def test_get_added_entity_names(self):
        """Retorna nombres de entidades añadidas."""
        diff = MemoryDiff(
            entities_added=[
                MemoryEntity(name="Metformin", entity_type="Medication"),
                MemoryEntity(name="Diabetes", entity_type="Condition"),
            ],
        )
        names = diff.get_added_entity_names()
        assert "Metformin" in names
        assert "Diabetes" in names

    def test_has_entity_added(self):
        """Verifica si se añadió entidad específica."""
        diff = MemoryDiff(
            entities_added=[
                MemoryEntity(name="Metformin", entity_type="Medication"),
            ],
        )
        assert diff.has_entity_added("Metformin")
        assert diff.has_entity_added("metformin")  # Case insensitive
        assert not diff.has_entity_added("Lisinopril")


class TestMemoryInspectorDiff:
    """Tests para el cálculo de diffs del MemoryInspector."""

    @pytest.fixture
    def inspector(self):
        """Crea una instancia del inspector."""
        return MemoryInspector(
            base_url="http://localhost:8000",
            api_key="test-key",
        )

    def test_compute_diff_entity_added(self, inspector):
        """Detecta entidad añadida."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[MemoryEntity(name="Metformin", entity_type="Medication")],
            ),
        )

        diff = inspector.compute_diff(before, after)

        assert len(diff.entities_added) == 1
        assert diff.entities_added[0].name == "Metformin"
        assert len(diff.entities_removed) == 0

    def test_compute_diff_entity_removed(self, inspector):
        """Detecta entidad eliminada."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[MemoryEntity(name="Metformin", entity_type="Medication")],
            ),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
        )

        diff = inspector.compute_diff(before, after)

        assert len(diff.entities_removed) == 1
        assert diff.entities_removed[0].name == "Metformin"
        assert len(diff.entities_added) == 0

    def test_compute_diff_entity_modified(self, inspector):
        """Detecta entidad modificada."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[
                    MemoryEntity(
                        name="Metformin",
                        entity_type="Medication",
                        confidence=0.7,
                        observation_count=1,
                    )
                ],
            ),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[
                    MemoryEntity(
                        name="Metformin",
                        entity_type="Medication",
                        confidence=0.9,
                        observation_count=3,
                    )
                ],
            ),
        )

        diff = inspector.compute_diff(before, after)

        # No entities added or removed
        assert len(diff.entities_added) == 0
        assert len(diff.entities_removed) == 0

        # But modifications detected
        assert len(diff.entities_modified) == 2
        fields = [c.field for c in diff.entities_modified]
        assert "confidence" in fields
        assert "observation_count" in fields

    def test_compute_diff_relationship_added(self, inspector):
        """Detecta relación añadida."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                relationships=[
                    MemoryRelationship(
                        from_name="Metformin",
                        to_name="Diabetes",
                        relationship_type="TREATS",
                    )
                ],
            ),
        )

        diff = inspector.compute_diff(before, after)

        assert len(diff.relationships_added) == 1
        assert diff.relationships_added[0].relationship_type == "TREATS"

    def test_compute_diff_no_changes(self, inspector):
        """No detecta cambios cuando no hay."""
        snapshot = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[MemoryEntity(name="Metformin", entity_type="Medication")],
            ),
        )

        diff = inspector.compute_diff(snapshot, snapshot)

        assert not diff.has_changes

    def test_compute_diff_multiple_layers(self, inspector):
        """Detecta cambios en múltiples capas."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            graphiti=GraphitiLayerSnapshot(
                entities=[MemoryEntity(name="Old", entity_type="Entity")],
            ),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[MemoryEntity(name="New", entity_type="Entity")],
            ),
        )

        diff = inspector.compute_diff(before, after)

        assert len(diff.entities_added) == 1
        assert diff.entities_added[0].name == "New"
        assert len(diff.entities_removed) == 1
        assert diff.entities_removed[0].name == "Old"

    def test_compute_diff_memories(self, inspector):
        """Detecta cambios en memorias Mem0."""
        before = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            mem0=Mem0LayerSnapshot(
                memories=[Mem0Memory(id="mem1", text="Old memory")],
            ),
        )
        after = MemorySnapshot(
            patient_id="test",
            timestamp=datetime.now(UTC),
            mem0=Mem0LayerSnapshot(
                memories=[Mem0Memory(id="mem2", text="New memory")],
            ),
        )

        diff = inspector.compute_diff(before, after)

        assert len(diff.memories_added) == 1
        assert diff.memories_added[0].id == "mem2"
        assert len(diff.memories_removed) == 1
        assert diff.memories_removed[0].id == "mem1"


class TestMemoryInspectorClient:
    """Tests para operaciones HTTP del MemoryInspector."""

    @pytest.fixture
    def mock_http_client(self):
        """Crea un mock del cliente HTTP."""
        return AsyncMock()

    @pytest.fixture
    async def inspector_with_mock(self, mock_http_client):
        """Crea un inspector con cliente HTTP mockeado."""
        import asyncio
        inspector = MemoryInspector(
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        inspector._client = mock_http_client
        # Set the client loop to match the current async test's loop
        inspector._client_loop = asyncio.get_running_loop()
        return inspector

    @pytest.mark.asyncio
    async def test_take_snapshot_success(self, inspector_with_mock, mock_http_client):
        """Test de captura de snapshot exitosa."""
        mock_response = {
            "patient_id": "test-patient",
            "timestamp": datetime.now(UTC).isoformat(),
            "redis": {"session_data": {}, "active_sessions": 0},
            "mem0": {"memories": [], "memory_count": 0},
            "graphiti": {"episodes": [], "entities": [], "edges": []},
            "neo4j_dikw": {
                "perception": [
                    {"name": "Metformin", "entity_type": "Medication", "confidence": 0.8}
                ],
                "semantic": [],
                "reasoning": [],
                "application": [],
                "relationships": [],
            },
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.get = AsyncMock(return_value=mock_response_obj)

        snapshot = await inspector_with_mock.take_snapshot("test-patient")

        assert snapshot.patient_id == "test-patient"
        assert len(snapshot.neo4j_dikw.perception) == 1
        assert snapshot.neo4j_dikw.perception[0].name == "Metformin"

    @pytest.mark.asyncio
    async def test_flush_pipelines_success(self, inspector_with_mock, mock_http_client):
        """Test de flush de pipelines exitoso."""
        mock_response = {
            "flushed": True,
            "entities_crystallized": 5,
            "promotions_executed": 2,
            "pending_after_flush": 0,
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response_obj)

        result = await inspector_with_mock.flush_pipelines()

        assert result["flushed"] is True
        assert result["entities_crystallized"] == 5

    @pytest.mark.asyncio
    async def test_wait_for_quiescence_immediate(self, inspector_with_mock, mock_http_client):
        """Test de espera por quiescence que retorna inmediatamente."""
        mock_response = {"quiescent": True, "buffer_size": 0}

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.get = AsyncMock(return_value=mock_response_obj)

        result = await inspector_with_mock.wait_for_quiescence(timeout_seconds=5)

        assert result is True

    @pytest.mark.asyncio
    async def test_seed_state_success(self, inspector_with_mock, mock_http_client):
        """Test de seeding de estado exitoso."""
        mock_response = {
            "success": True,
            "patient_id": "test-patient",
            "entities_created": 2,
            "relationships_created": 1,
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response_obj)

        result = await inspector_with_mock.seed_state(
            patient_id="test-patient",
            entities=[{"name": "E1", "entity_type": "T1"}],
            relationships=[],
        )

        assert result["success"] is True
        assert result["entities_created"] == 2

    @pytest.mark.asyncio
    async def test_reset_patient_success(self, inspector_with_mock, mock_http_client):
        """Test de reset de paciente exitoso."""
        mock_response = {
            "success": True,
            "patient_id": "test-patient",
            "layers_cleared": ["neo4j_dikw", "mem0"],
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response_obj)

        result = await inspector_with_mock.reset_patient("test-patient")

        assert result["success"] is True
        assert "neo4j_dikw" in result["layers_cleared"]

    @pytest.mark.asyncio
    async def test_send_chat_success(self, inspector_with_mock, mock_http_client):
        """Test de envío de chat exitoso."""
        mock_response = {
            "patient_id": "test-patient",
            "session_id": "session-123",
            "response_id": "resp-456",
            "content": "Hola, ¿cómo puedo ayudarte?",
            "confidence": 0.9,
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response_obj)

        result = await inspector_with_mock.send_chat(
            patient_id="test-patient",
            message="Hola",
        )

        assert result["content"] == "Hola, ¿cómo puedo ayudarte?"
        assert result["confidence"] == 0.9


class TestNormalizeAccentsSpanish:
    """Tests específicos para normalización de texto en español."""

    def test_common_spanish_accents(self):
        """Normaliza acentos comunes en español médico."""
        assert normalize_text("medicación") == "medicacion"
        assert normalize_text("crónico") == "cronico"
        assert normalize_text("diagnóstico") == "diagnostico"
        assert normalize_text("síntoma") == "sintoma"
        assert normalize_text("tratamiento médico") == "tratamiento medico"

    def test_spanish_special_chars(self):
        """Normaliza caracteres especiales del español."""
        assert normalize_text("niño") == "nino"
        assert normalize_text("año") == "ano"

    def test_uppercase_with_accents(self):
        """Normaliza mayúsculas con acentos."""
        assert normalize_text("HIPERTENSIÓN ARTERIAL") == "hipertension arterial"
        assert normalize_text("DIABETES MELLITUS TIPO 2") == "diabetes mellitus tipo 2"


class TestEvalResult:
    """Tests para el modelo EvalResult."""

    def test_total_assertions(self):
        """Cuenta total de aserciones."""
        from tests.eval.runner.models import TurnResult, AssertionResult

        result = EvalResult(
            scenario_id="test",
            scenario_name="Test Scenario",
            category="test",
            severity="medium",
            passed=True,
            turns=[
                TurnResult(
                    turn_number=1,
                    patient_message="Test",
                    agent_response="Response",
                    response_assertions=[
                        AssertionResult(assertion_type="test", passed=True),
                        AssertionResult(assertion_type="test", passed=False),
                    ],
                    state_assertions=[
                        AssertionResult(assertion_type="test", passed=True),
                    ],
                ),
            ],
        )

        assert result.total_assertions == 3
        assert result.failed_assertions_count == 1
        assert result.pass_rate == 2 / 3


# Import EvalResult at module level
from tests.eval.runner.models import EvalResult
