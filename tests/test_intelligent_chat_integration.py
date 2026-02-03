"""Integration test for IntelligentChatService with NeurosymbolicQueryService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.intelligent_chat_service import IntelligentChatService
from application.services.neurosymbolic_query_service import QueryStrategy
from domain.confidence_models import create_confidence, ConfidenceSource


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("application.services.intelligent_chat_service.AsyncOpenAI") as mock:
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"entities": ["diabetes"]}'
                        )
                    )
                ]
            )
        )
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j backend."""
    with patch("application.services.intelligent_chat_service.Neo4jBackend") as mock:
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[
            {"id": "entity:1", "name": "diabetes", "confidence": 0.9}
        ])
        backend.list_relationships = AsyncMock(return_value=[])
        backend.close = AsyncMock()
        mock.return_value = backend
        yield backend


@pytest.fixture
def mock_document_service():
    """Mock document service."""
    with patch("application.services.intelligent_chat_service.DocumentService") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    with patch("application.services.intelligent_chat_service.RAGService") as mock:
        service = MagicMock()
        service.query = AsyncMock(return_value=MagicMock(sources=[]))
        mock.return_value = service
        yield service


@pytest.fixture
def mock_validation_engine():
    """Mock validation engine."""
    with patch("application.services.intelligent_chat_service.ValidationEngine") as mock:
        engine = MagicMock()
        engine.validate_event = AsyncMock(return_value={"valid": True, "violations": []})
        mock.return_value = engine
        yield engine


class TestIntelligentChatNeurosymbolicIntegration:
    """Test IntelligentChatService integration with NeurosymbolicQueryService."""

    @pytest.mark.asyncio
    async def test_query_uses_neurosymbolic_service(
        self,
        mock_openai,
        mock_neo4j,
        mock_document_service,
        mock_rag_service,
        mock_validation_engine
    ):
        """Test that queries use the neurosymbolic service for reasoning."""
        # Arrange
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            service = IntelligentChatService(
                openai_api_key="test-key",
                enable_conversational_layer=False
            )

            # Verify neurosymbolic service is initialized
            assert service.neurosymbolic_service is not None
            assert service.neurosymbolic_service.backend is not None

            # Mock the neurosymbolic service execute_query method
            service.neurosymbolic_service.execute_query = AsyncMock(
                return_value=(
                    {
                        "query_id": "query_000001",
                        "strategy": "collaborative",
                        "layers_traversed": ["REASONING", "SEMANTIC"],
                        "confidence": 0.85,
                        "entities": [{"name": "diabetes", "type": "Disease"}],
                        "relationships": [],
                        "applied_rules": ["safety_check"],
                        "inferences": [{"type": "confidence_score", "score": 0.85}],
                        "assertions": [],
                        "entity_ids": ["entity:1"]
                    },
                    MagicMock(
                        query_id="query_000001",
                        strategy=QueryStrategy.COLLABORATIVE,
                        layers_traversed=["REASONING", "SEMANTIC"],
                        layer_results=[],
                        final_confidence=create_confidence(0.85, ConfidenceSource.HYBRID, "test"),
                        conflicts_detected=[],
                        total_time_ms=100.0
                    )
                )
            )

            # Mock answer generation
            mock_openai.chat.completions.create.return_value = MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content="Diabetes is a chronic condition affecting blood sugar levels."
                        )
                    )
                ]
            )

            # Act
            response = await service.query("What is diabetes?")

            # Assert
            assert response is not None
            assert response.answer is not None
            assert response.confidence > 0
            assert "diabetes" in response.answer.lower()

            # Verify neurosymbolic service was called
            service.neurosymbolic_service.execute_query.assert_called_once()
            call_args = service.neurosymbolic_service.execute_query.call_args
            assert call_args.kwargs["query_text"] == "What is diabetes?"
            assert call_args.kwargs["trace_execution"] is True

    @pytest.mark.asyncio
    async def test_reasoning_provenance_includes_layer_info(
        self,
        mock_openai,
        mock_neo4j,
        mock_document_service,
        mock_rag_service,
        mock_validation_engine
    ):
        """Test that reasoning provenance includes layer traversal information."""
        # Arrange
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            service = IntelligentChatService(
                openai_api_key="test-key",
                enable_conversational_layer=False
            )

            # Create proper mock trace with KnowledgeLayer enum values
            from domain.confidence_models import KnowledgeLayer
            from application.services.neurosymbolic_query_service import LayerResult

            mock_trace = MagicMock()
            mock_trace.query_id = "query_000002"
            mock_trace.strategy = QueryStrategy.SYMBOLIC_FIRST
            mock_trace.layers_traversed = [KnowledgeLayer.SEMANTIC, KnowledgeLayer.REASONING]
            mock_trace.layer_results = [
                LayerResult(
                    layer=KnowledgeLayer.SEMANTIC,
                    entities=[{"name": "headache"}],
                    relationships=[],
                    confidence=create_confidence(0.85, ConfidenceSource.SYMBOLIC_RULE, "test"),
                    query_time_ms=10.0,
                    cache_hit=False
                ),
                LayerResult(
                    layer=KnowledgeLayer.REASONING,
                    entities=[{"name": "ibuprofen"}],
                    relationships=[],
                    confidence=create_confidence(0.90, ConfidenceSource.HYBRID, "test"),
                    query_time_ms=15.0,
                    cache_hit=False
                )
            ]
            mock_trace.final_confidence = create_confidence(0.90, ConfidenceSource.HYBRID, "test")
            mock_trace.conflicts_detected = []
            mock_trace.total_time_ms = 25.0

            # Mock neurosymbolic query execution with proper trace
            service.neurosymbolic_service.execute_query = AsyncMock(
                return_value=(
                    {
                        "query_id": "query_000002",
                        "strategy": "symbolic_first",
                        "layers_traversed": ["SEMANTIC", "REASONING"],
                        "confidence": 0.90,
                        "entities": [],
                        "relationships": [],
                        "applied_rules": [],
                        "inferences": [],
                        "assertions": [],
                        "entity_ids": []
                    },
                    mock_trace
                )
            )

            # Mock answer generation
            mock_openai.chat.completions.create.return_value = MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="Test answer")
                    )
                ]
            )

            # Act
            response = await service.query("What treats headache?")

            # Assert
            assert "reasoning_trail" in response.__dict__
            assert len(response.reasoning_trail) > 0

            # Verify provenance includes layer information
            provenance_text = "\n".join(response.reasoning_trail)
            # Check that it contains either strategy info or layer traversal
            assert (
                "symbolic_first" in provenance_text.lower() or
                "Layers Traversed" in provenance_text or
                "SEMANTIC" in provenance_text or
                "REASONING" in provenance_text
            )

    @pytest.mark.asyncio
    async def test_neurosymbolic_service_with_patient_context(
        self,
        mock_openai,
        mock_neo4j,
        mock_document_service,
        mock_rag_service,
        mock_validation_engine
    ):
        """Test neurosymbolic service receives patient context."""
        # Arrange
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            # Mock patient memory service
            patient_memory = MagicMock()
            patient_memory.get_patient_context = AsyncMock(
                return_value=MagicMock(
                    patient_id="patient_123",
                    diagnoses=[{"condition": "hypertension"}],
                    medications=[{"name": "lisinopril"}],
                    allergies=["penicillin"],
                    conversation_summary="Patient managing hypertension"
                )
            )

            service = IntelligentChatService(
                openai_api_key="test-key",
                patient_memory_service=patient_memory,
                enable_conversational_layer=False
            )

            # Mock neurosymbolic query execution
            service.neurosymbolic_service.execute_query = AsyncMock(
                return_value=(
                    {
                        "query_id": "query_000003",
                        "strategy": "collaborative",
                        "layers_traversed": ["REASONING"],
                        "confidence": 0.88,
                        "entities": [],
                        "relationships": [],
                        "applied_rules": [],
                        "inferences": [],
                        "assertions": [],
                        "entity_ids": []
                    },
                    None
                )
            )

            # Mock answer generation
            mock_openai.chat.completions.create.return_value = MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="Test answer with patient context")
                    )
                ]
            )

            # Act
            response = await service.query(
                "Can I take ibuprofen?",
                patient_id="patient_123"
            )

            # Assert
            service.neurosymbolic_service.execute_query.assert_called_once()
            call_args = service.neurosymbolic_service.execute_query.call_args

            # Verify patient context was passed
            assert call_args.kwargs["patient_context"] is not None
            patient_context = call_args.kwargs["patient_context"]
            assert patient_context.patient_id == "patient_123"
            assert any(d["condition"] == "hypertension" for d in patient_context.diagnoses)


class TestNeurosymbolicServiceInitialization:
    """Test that NeurosymbolicQueryService is properly initialized."""

    @pytest.mark.asyncio
    async def test_service_has_neurosymbolic_service(
        self,
        mock_openai,
        mock_neo4j,
        mock_document_service,
        mock_rag_service,
        mock_validation_engine
    ):
        """Test IntelligentChatService initializes neurosymbolic service."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            service = IntelligentChatService(
                openai_api_key="test-key",
                enable_conversational_layer=False
            )

            # Verify attributes exist
            assert hasattr(service, "neurosymbolic_service")
            assert service.neurosymbolic_service is not None
            assert hasattr(service.neurosymbolic_service, "execute_query")
            assert hasattr(service.neurosymbolic_service, "backend")
            assert hasattr(service.neurosymbolic_service, "reasoning_engine")
            assert hasattr(service.neurosymbolic_service, "confidence_propagator")
