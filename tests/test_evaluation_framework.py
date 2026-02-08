"""
Tests para el Framework de Evaluación de Agentes.

Estos tests verifican que los endpoints de evaluación funcionan
correctamente para permitir testing automatizado del agente.
"""

import pytest
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Set eval mode before importing the app
os.environ["SYNAPSEFLOW_EVAL_MODE"] = "true"
os.environ["SYNAPSEFLOW_EVAL_API_KEY"] = "test-eval-key-12345"


class TestEvaluationAuth:
    """Tests para autenticación de endpoints de evaluación."""

    def test_is_eval_mode_enabled(self):
        """Verifica que is_eval_mode_enabled lee correctamente la variable."""
        from src.application.api.evaluation_auth import is_eval_mode_enabled

        # Already set to true above
        assert is_eval_mode_enabled() is True

    def test_is_eval_mode_disabled_by_default(self):
        """Verifica que eval mode está deshabilitado por defecto."""
        with patch.dict(os.environ, {"SYNAPSEFLOW_EVAL_MODE": "false"}):
            from src.application.api.evaluation_auth import is_eval_mode_enabled
            # Need to reload to pick up env change
            assert os.getenv("SYNAPSEFLOW_EVAL_MODE") == "false"

    def test_get_eval_api_key(self):
        """Verifica que get_eval_api_key lee la API key."""
        from src.application.api.evaluation_auth import get_eval_api_key

        key = get_eval_api_key()
        assert key == "test-eval-key-12345"

    def test_eval_api_key_auth_missing_key(self):
        """Verifica que se rechaza request sin API key."""
        from src.application.api.evaluation_auth import EvalAPIKeyAuth
        from fastapi import HTTPException

        auth = EvalAPIKeyAuth(api_key="expected-key")

        with pytest.raises(HTTPException) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(auth(api_key=None))

        assert exc_info.value.status_code == 401

    def test_eval_api_key_auth_wrong_key(self):
        """Verifica que se rechaza API key incorrecta."""
        from src.application.api.evaluation_auth import EvalAPIKeyAuth
        from fastapi import HTTPException

        auth = EvalAPIKeyAuth(api_key="expected-key")

        with pytest.raises(HTTPException) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(auth(api_key="wrong-key"))

        assert exc_info.value.status_code == 403

    def test_eval_api_key_auth_correct_key(self):
        """Verifica que se acepta API key correcta."""
        from src.application.api.evaluation_auth import EvalAPIKeyAuth

        auth = EvalAPIKeyAuth(api_key="correct-key")

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(auth(api_key="correct-key"))

        assert result == "correct-key"


class TestEvaluationModels:
    """Tests para modelos Pydantic de evaluación."""

    def test_memory_entity_model(self):
        """Verifica creación de MemoryEntityModel."""
        from src.application.api.evaluation_models import MemoryEntityModel, DIKWLayer

        entity = MemoryEntityModel(
            name="Metformin",
            entity_type="Medication",
            dikw_layer=DIKWLayer.SEMANTIC,
            confidence=0.92,
            observation_count=5,
        )

        assert entity.name == "Metformin"
        assert entity.entity_type == "Medication"
        assert entity.dikw_layer == DIKWLayer.SEMANTIC
        assert entity.confidence == 0.92

    def test_memory_snapshot_all_entities(self):
        """Verifica método all_entities de MemorySnapshot."""
        from src.application.api.evaluation_models import (
            MemorySnapshot,
            MemoryEntityModel,
            Neo4jDIKWLayerSnapshot,
            DIKWLayer,
        )

        snapshot = MemorySnapshot(
            patient_id="test-patient",
            neo4j_dikw=Neo4jDIKWLayerSnapshot(
                perception=[
                    MemoryEntityModel(name="Entity1", entity_type="Type1"),
                ],
                semantic=[
                    MemoryEntityModel(name="Entity2", entity_type="Type2"),
                ],
            ),
        )

        all_entities = snapshot.all_entities()
        assert len(all_entities) == 2
        names = [e.name for e in all_entities]
        assert "Entity1" in names
        assert "Entity2" in names

    def test_seed_state_request(self):
        """Verifica modelo SeedStateRequest."""
        from src.application.api.evaluation_models import (
            SeedStateRequest,
            SeedEntityRequest,
            SeedRelationshipRequest,
            DIKWLayer,
        )

        request = SeedStateRequest(
            patient_id="test-patient",
            entities=[
                SeedEntityRequest(
                    name="Diabetes",
                    entity_type="Condition",
                    dikw_layer=DIKWLayer.PERCEPTION,
                    confidence=0.8,
                ),
            ],
            relationships=[
                SeedRelationshipRequest(
                    from_name="Metformin",
                    to_name="Diabetes",
                    relationship_type="TREATS",
                ),
            ],
            clear_existing=True,
        )

        assert request.patient_id == "test-patient"
        assert len(request.entities) == 1
        assert len(request.relationships) == 1
        assert request.clear_existing is True

    def test_flush_pipelines_response(self):
        """Verifica modelo FlushPipelinesResponse."""
        from src.application.api.evaluation_models import FlushPipelinesResponse

        response = FlushPipelinesResponse(
            flushed=True,
            events_processed=10,
            entities_crystallized=5,
            promotions_executed=2,
            pending_after_flush=0,
            processing_time_ms=150.5,
        )

        assert response.flushed is True
        assert response.entities_crystallized == 5

    def test_test_chat_request(self):
        """Verifica modelo TestChatRequest."""
        from src.application.api.evaluation_models import TestChatRequest

        request = TestChatRequest(
            patient_id="test-patient",
            message="Hola, me duele la cabeza",
            conversation_history=[
                {"role": "user", "content": "Buenos días"},
                {"role": "assistant", "content": "Buenos días, ¿cómo puedo ayudarte?"},
            ],
        )

        assert request.patient_id == "test-patient"
        assert "cabeza" in request.message
        assert len(request.conversation_history) == 2


class TestCrystallizationFlush:
    """Tests para los métodos flush_now y get_buffer_status."""

    @pytest.mark.asyncio
    async def test_get_buffer_status(self):
        """Verifica que get_buffer_status retorna estado correcto."""
        from src.application.services.crystallization_service import (
            CrystallizationService,
            CrystallizationConfig,
        )

        # Create mock dependencies
        mock_backend = AsyncMock()
        mock_resolver = AsyncMock()
        mock_event_bus = AsyncMock()

        service = CrystallizationService(
            neo4j_backend=mock_backend,
            entity_resolver=mock_resolver,
            event_bus=mock_event_bus,
            config=CrystallizationConfig(),
        )

        status = service.get_buffer_status()

        assert status.buffer_size == 0
        assert status.batch_in_progress is False
        assert status.running is False

    @pytest.mark.asyncio
    async def test_flush_now_empty_buffer(self):
        """Verifica flush_now con buffer vacío."""
        from src.application.services.crystallization_service import (
            CrystallizationService,
            CrystallizationConfig,
            CrystallizationResult,
        )

        # Create mock dependencies
        mock_backend = AsyncMock()
        mock_resolver = AsyncMock()
        mock_event_bus = AsyncMock()

        service = CrystallizationService(
            neo4j_backend=mock_backend,
            entity_resolver=mock_resolver,
            event_bus=mock_event_bus,
            config=CrystallizationConfig(),
        )

        # Mock crystallize_from_graphiti to return empty result
        service.crystallize_from_graphiti = AsyncMock(return_value=CrystallizationResult(
            entities_processed=0,
            entities_created=0,
            entities_merged=0,
            entities_skipped=0,
            relationships_created=0,
            promotion_candidates=0,
            processing_time_ms=0,
        ))

        result = await service.flush_now()

        assert result.flushed is True
        assert result.pending_after_flush == 0

    @pytest.mark.asyncio
    async def test_is_quiescent(self):
        """Verifica is_quiescent con buffer vacío."""
        from src.application.services.crystallization_service import (
            CrystallizationService,
            CrystallizationConfig,
        )

        mock_backend = AsyncMock()
        mock_resolver = AsyncMock()
        mock_event_bus = AsyncMock()

        service = CrystallizationService(
            neo4j_backend=mock_backend,
            entity_resolver=mock_resolver,
            event_bus=mock_event_bus,
            config=CrystallizationConfig(),
        )

        assert service.is_quiescent() is True

        # Add pending entity
        service._pending_entities.append({"name": "test"})

        assert service.is_quiescent() is False


class TestFlushAndBufferDataclasses:
    """Tests para las nuevas dataclasses FlushResult y BufferStatus."""

    def test_flush_result_dataclass(self):
        """Verifica creación de FlushResult."""
        from src.application.services.crystallization_service import FlushResult

        result = FlushResult(
            flushed=True,
            events_processed=10,
            entities_crystallized=5,
            promotions_executed=2,
            pending_after_flush=0,
            processing_time_ms=150.5,
            errors=["Some warning"],
        )

        assert result.flushed is True
        assert result.events_processed == 10
        assert result.entities_crystallized == 5
        assert len(result.errors) == 1

    def test_buffer_status_dataclass(self):
        """Verifica creación de BufferStatus."""
        from src.application.services.crystallization_service import BufferStatus

        status = BufferStatus(
            buffer_size=10,
            last_flush=datetime.utcnow(),
            batch_in_progress=False,
            running=True,
        )

        assert status.buffer_size == 10
        assert status.running is True


# ========================================
# Integration Tests with Mocked Services
# ========================================

class TestEvaluationEndpointsIntegration:
    """Tests de integración para endpoints de evaluación."""

    @pytest.fixture
    def mock_patient_memory(self):
        """Mock del PatientMemoryService."""
        mock = AsyncMock()
        mock.get_or_create_patient = AsyncMock(return_value="test-patient")
        mock.create_session = AsyncMock()
        mock.neo4j = AsyncMock()
        mock.neo4j.query_raw = AsyncMock(return_value=[])
        mock.redis = AsyncMock()
        mock.redis.get_session = AsyncMock(return_value=None)
        mock.mem0 = MagicMock()
        mock.mem0.get_all = MagicMock(return_value={"results": []})
        return mock

    @pytest.fixture
    def mock_chat_service(self):
        """Mock del ChatService."""
        mock = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_response.confidence = 0.9
        mock_response.sources = []
        mock_response.reasoning_trail = []
        mock_response.layer_accesses = ["SEMANTIC"]
        mock_response.entities = []
        mock_response.medical_alerts = []
        mock.query = AsyncMock(return_value=mock_response)
        return mock

    @pytest.fixture
    def mock_kg_backend(self):
        """Mock del KG Backend."""
        mock = AsyncMock()
        mock.query_raw = AsyncMock(return_value=[])
        mock.add_entity = AsyncMock()
        mock.add_relationship = AsyncMock()
        return mock

    @pytest.fixture
    def mock_crystallization(self):
        """Mock del CrystallizationService."""
        from src.application.services.crystallization_service import (
            FlushResult,
            BufferStatus,
        )

        mock = AsyncMock()
        mock.flush_now = AsyncMock(return_value=FlushResult(
            flushed=True,
            events_processed=5,
            entities_crystallized=3,
            promotions_executed=1,
            pending_after_flush=0,
            processing_time_ms=100.0,
        ))
        mock.get_buffer_status = MagicMock(return_value=BufferStatus(
            buffer_size=0,
            last_flush=datetime.utcnow(),
            batch_in_progress=False,
            running=True,
        ))
        mock.get_crystallization_stats = AsyncMock(return_value={
            "mode": "hybrid",
            "running": True,
            "pending_entities": 0,
        })
        return mock

    @pytest.mark.asyncio
    async def test_health_endpoint(
        self,
        mock_patient_memory,
        mock_chat_service,
        mock_kg_backend,
        mock_crystallization,
    ):
        """Test del endpoint de health check."""
        with patch("src.application.api.evaluation_router.get_patient_memory", return_value=mock_patient_memory), \
             patch("src.application.api.evaluation_router.get_chat_service", return_value=mock_chat_service), \
             patch("src.application.api.evaluation_router.get_kg_backend", return_value=mock_kg_backend), \
             patch("src.application.api.evaluation_router.get_crystallization_service", return_value=mock_crystallization), \
             patch("src.application.api.evaluation_router.get_episodic_memory", return_value=None):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/eval/health",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["eval_mode_enabled"] is True
                assert "services" in data

    @pytest.mark.asyncio
    async def test_memory_snapshot_endpoint(
        self,
        mock_patient_memory,
        mock_kg_backend,
    ):
        """Test del endpoint de memory snapshot."""
        with patch("src.application.api.evaluation_router.get_patient_memory", return_value=mock_patient_memory), \
             patch("src.application.api.evaluation_router.get_kg_backend", return_value=mock_kg_backend), \
             patch("src.application.api.evaluation_router.get_episodic_memory", return_value=None):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/eval/memory-snapshot/test-patient-123",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["patient_id"] == "test-patient-123"
                assert "redis" in data
                assert "mem0" in data
                assert "neo4j_dikw" in data

    @pytest.mark.asyncio
    async def test_flush_pipelines_endpoint(self, mock_crystallization):
        """Test del endpoint de flush pipelines."""
        with patch("src.application.api.evaluation_router.get_crystallization_service", return_value=mock_crystallization):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/eval/flush-pipelines",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["flushed"] is True
                assert data["entities_crystallized"] == 3

    @pytest.mark.asyncio
    async def test_pipeline_status_endpoint(self, mock_crystallization):
        """Test del endpoint de pipeline status."""
        with patch("src.application.api.evaluation_router.get_crystallization_service", return_value=mock_crystallization):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/eval/pipeline-status",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["quiescent"] is True
                assert data["buffer_size"] == 0

    @pytest.mark.asyncio
    async def test_test_chat_endpoint(
        self,
        mock_patient_memory,
        mock_chat_service,
    ):
        """Test del endpoint REST de chat."""
        with patch("src.application.api.evaluation_router.get_patient_memory", return_value=mock_patient_memory), \
             patch("src.application.api.evaluation_router.get_chat_service", return_value=mock_chat_service):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/eval/chat",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"},
                    json={
                        "patient_id": "test-patient",
                        "message": "Me duele la cabeza",
                        "conversation_history": []
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["patient_id"] == "test-patient"
                assert data["content"] == "Test response"
                assert data["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_seed_state_endpoint(
        self,
        mock_patient_memory,
        mock_kg_backend,
    ):
        """Test del endpoint de seed state."""
        with patch("src.application.api.evaluation_router.get_patient_memory", return_value=mock_patient_memory), \
             patch("src.application.api.evaluation_router.get_kg_backend", return_value=mock_kg_backend):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/eval/seed-state",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"},
                    json={
                        "patient_id": "test-patient",
                        "entities": [
                            {
                                "name": "Metformin",
                                "entity_type": "Medication",
                                "dikw_layer": "PERCEPTION",
                                "confidence": 0.8
                            }
                        ],
                        "relationships": [],
                        "clear_existing": False
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["patient_id"] == "test-patient"
                assert data["entities_created"] == 1

    @pytest.mark.asyncio
    async def test_reset_patient_endpoint(
        self,
        mock_patient_memory,
        mock_kg_backend,
    ):
        """Test del endpoint de reset patient."""
        with patch("src.application.api.evaluation_router.get_patient_memory", return_value=mock_patient_memory), \
             patch("src.application.api.evaluation_router.get_kg_backend", return_value=mock_kg_backend), \
             patch("src.application.api.evaluation_router.get_episodic_memory", return_value=None):

            from src.application.api.evaluation_router import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/eval/reset/test-patient",
                    headers={"X-Eval-API-Key": "test-eval-key-12345"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["patient_id"] == "test-patient"
                assert "layers_cleared" in data

    @pytest.mark.asyncio
    async def test_auth_required_for_all_endpoints(self):
        """Verifica que todos los endpoints requieren autenticación."""
        from src.application.api.evaluation_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Test without API key
            endpoints = [
                ("GET", "/api/eval/health"),
                ("GET", "/api/eval/memory-snapshot/test"),
                ("POST", "/api/eval/seed-state"),
                ("POST", "/api/eval/reset/test"),
                ("POST", "/api/eval/flush-pipelines"),
                ("GET", "/api/eval/pipeline-status"),
                ("POST", "/api/eval/chat"),
            ]

            for method, path in endpoints:
                if method == "GET":
                    response = await client.get(path)
                else:
                    response = await client.post(path, json={})

                assert response.status_code == 401, f"Expected 401 for {method} {path}"
