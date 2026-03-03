"""Unit tests for LangExtractIngestionService.

Tests cover:
- 3.1 Service initialization (default Gemini config, custom OpenAI config, parameter validation)
- 3.2 Entity extraction with mocked LangExtract responses
- 3.3 Source grounding metadata mapping
- 3.4 DIKW PERCEPTION layer assignment and confidence
- 3.5 Missing langextract package graceful degradation
"""

import os
import sys
import types
import importlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers: build a fake 'langextract' module so we can import the service
# without relying on the real package's internal structure.
# ---------------------------------------------------------------------------

def _make_fake_langextract():
    """Create a fake langextract package with the data structures the service uses."""
    lx = types.ModuleType("langextract")
    lx_data = types.ModuleType("langextract.data")

    class FakeExtraction:
        def __init__(self, extraction_class="", extraction_text="", attributes=None,
                     source_text=None, source_start=None, source_end=None, grounding=None):
            self.extraction_class = extraction_class
            self.extraction_text = extraction_text
            self.attributes = attributes or {}
            # Source grounding fields
            if source_text is not None:
                self.source_text = source_text
            if source_start is not None:
                self.source_start = source_start
            if source_end is not None:
                self.source_end = source_end
            if grounding is not None:
                self.grounding = grounding

    class FakeExampleData:
        def __init__(self, text="", extractions=None):
            self.text = text
            self.extractions = extractions or []

    class FakeExtractionResponse:
        """Mimics the object returned by lx.extract()."""
        def __init__(self, extractions=None):
            self.extractions = extractions or []

    lx_data.Extraction = FakeExtraction
    lx_data.ExampleData = FakeExampleData
    lx_data.ExtractionResponse = FakeExtractionResponse
    lx.data = lx_data
    lx.extract = MagicMock()

    return lx, lx_data, FakeExtraction, FakeExampleData, FakeExtractionResponse


def _install_fake_langextract():
    """Install fake langextract into sys.modules and return it."""
    lx, lx_data, *_ = _make_fake_langextract()
    sys.modules["langextract"] = lx
    sys.modules["langextract.data"] = lx_data
    return lx


def _remove_langextract_from_modules():
    """Remove langextract and the service module from sys.modules.

    Also deletes the cached attribute on the parent package so that
    ``from application.services import langextract_ingestion`` actually
    re-executes the module code instead of returning the stale reference.
    """
    sys.modules.pop("langextract", None)
    sys.modules.pop("langextract.data", None)
    sys.modules.pop("application.services.langextract_ingestion", None)
    # The parent package caches submodule references as attributes.
    # Deleting this forces Python to reimport rather than reuse the stale ref.
    try:
        import application.services
        if hasattr(application.services, "langextract_ingestion"):
            delattr(application.services, "langextract_ingestion")
    except ImportError:
        pass


def _clear_service_module():
    """Clear the cached service module so it can be freshly reimported.

    Removes both the sys.modules entry and the parent package attribute
    to force a full reimport.
    """
    sys.modules.pop("application.services.langextract_ingestion", None)
    try:
        import application.services
        if hasattr(application.services, "langextract_ingestion"):
            delattr(application.services, "langextract_ingestion")
    except ImportError:
        pass


def _import_service_module():
    """Import (or re-import) the langextract ingestion module.

    Clears the cached module first so LANGEXTRACT_AVAILABLE is re-evaluated.
    """
    _clear_service_module()
    from application.services import langextract_ingestion
    return langextract_ingestion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_modules():
    """Ensure module cache is clean before and after each test."""
    _clear_service_module()
    _remove_langextract_from_modules()
    yield
    _clear_service_module()
    _remove_langextract_from_modules()


@pytest.fixture
def fake_lx():
    """Install and return a fake langextract module."""
    return _install_fake_langextract()


# =====================================================================
# 3.1 Initialization Tests
# =====================================================================

class TestServiceInitialization:
    """Test LangExtractIngestionService.__init__ with various configs."""

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_default_gemini_config(self, mock_markitdown_cls, fake_lx):
        """Default init uses Gemini model with schema constraints enabled."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        assert svc.model_id == "gemini-2.5-flash"
        assert svc.extraction_passes == 1
        assert svc.max_workers == 5
        assert svc.use_schema_constraints is True
        assert svc.fence_output is False
        assert svc._is_openai_model is False

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_openai_model_config(self, mock_markitdown_cls, fake_lx):
        """OpenAI model_id enables fence_output and disables schema constraints."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(model_id="gpt-4o", api_key="test-key")

        assert svc.model_id == "gpt-4o"
        assert svc._is_openai_model is True
        assert svc.fence_output is True
        assert svc.use_schema_constraints is False

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_openai_o1_model_detected(self, mock_markitdown_cls, fake_lx):
        """Models starting with o1- are detected as OpenAI models."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(model_id="o1-preview", api_key="test-key")

        assert svc._is_openai_model is True
        assert svc.fence_output is True

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_openai_o3_model_detected(self, mock_markitdown_cls, fake_lx):
        """Models starting with o3- are detected as OpenAI models."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(model_id="o3-mini", api_key="test-key")

        assert svc._is_openai_model is True

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_custom_extraction_passes(self, mock_markitdown_cls, fake_lx):
        """extraction_passes parameter is stored correctly."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(extraction_passes=3, api_key="test-key")

        assert svc.extraction_passes == 3

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_custom_max_workers(self, mock_markitdown_cls, fake_lx):
        """max_workers parameter is stored correctly."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(max_workers=10, api_key="test-key")

        assert svc.max_workers == 10

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_api_key_from_explicit_param(self, mock_markitdown_cls, fake_lx):
        """Explicit api_key parameter takes precedence over env vars."""
        mod = _import_service_module()
        with patch.dict(os.environ, {"LANGEXTRACT_API_KEY": "env-key"}, clear=False):
            svc = mod.LangExtractIngestionService(api_key="explicit-key")

        assert svc.api_key == "explicit-key"

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_api_key_from_langextract_env(self, mock_markitdown_cls, fake_lx):
        """Falls back to LANGEXTRACT_API_KEY env var when no explicit key."""
        mod = _import_service_module()
        env = {"LANGEXTRACT_API_KEY": "lx-env-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            svc = mod.LangExtractIngestionService()

        assert svc.api_key == "lx-env-key"

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_api_key_from_gemini_env(self, mock_markitdown_cls, fake_lx):
        """Falls back to GEMINI_API_KEY when LANGEXTRACT_API_KEY is not set."""
        mod = _import_service_module()
        env = {"GEMINI_API_KEY": "gemini-env-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGEXTRACT_API_KEY", None)
            svc = mod.LangExtractIngestionService()

        assert svc.api_key == "gemini-env-key"

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_builds_few_shot_examples(self, mock_markitdown_cls, fake_lx):
        """Init builds few-shot examples list."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        assert isinstance(svc._examples, list)
        assert len(svc._examples) > 0

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_entity_types_taxonomy(self, mock_markitdown_cls, fake_lx):
        """Module-level ENTITY_TYPES matches the SynapseFlow taxonomy."""
        mod = _import_service_module()
        expected = [
            "Disease", "Treatment", "Symptom", "Test", "Drug",
            "Gene", "Pathway", "Organization", "Study",
        ]
        assert mod.ENTITY_TYPES == expected


# =====================================================================
# 3.5 Missing Package Graceful Degradation Tests
# =====================================================================

class TestMissingPackageDegradation:
    """Test behavior when langextract is not installed."""

    def _import_with_blocked_langextract(self):
        """Re-import the service module with langextract blocked.

        Uses builtins.__import__ patching to make 'import langextract'
        raise ImportError, even if the real package is installed.
        """
        import builtins
        _original_import = builtins.__import__

        def _blocked_import(name, *args, **kwargs):
            if name == "langextract":
                raise ImportError("No module named 'langextract'")
            return _original_import(name, *args, **kwargs)

        _remove_langextract_from_modules()
        _clear_service_module()
        with patch("builtins.__import__", side_effect=_blocked_import):
            sys.modules.pop("application.services.langextract_ingestion", None)
            from application.services import langextract_ingestion as mod
        return mod

    def test_flag_false_when_package_missing(self):
        """LANGEXTRACT_AVAILABLE is False when langextract import fails."""
        mod = self._import_with_blocked_langextract()
        assert mod.LANGEXTRACT_AVAILABLE is False

    def test_import_error_on_instantiation(self):
        """Instantiating the service without langextract raises ImportError."""
        mod = self._import_with_blocked_langextract()

        with pytest.raises(ImportError, match="langextract is not installed"):
            mod.LangExtractIngestionService(api_key="test-key")

    def test_error_message_includes_install_instructions(self):
        """ImportError message tells the user how to install langextract."""
        mod = self._import_with_blocked_langextract()

        with pytest.raises(ImportError) as exc_info:
            mod.LangExtractIngestionService(api_key="test-key")

        msg = str(exc_info.value)
        assert "uv pip install langextract" in msg or "uv sync --extra langextract" in msg

    def test_flag_true_when_package_available(self, fake_lx):
        """LANGEXTRACT_AVAILABLE is True when langextract is importable."""
        mod = _import_service_module()
        assert mod.LANGEXTRACT_AVAILABLE is True

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_service_works_when_available(self, mock_markitdown_cls, fake_lx):
        """Service can be instantiated when langextract is available."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")
        assert svc.model_id == "gemini-2.5-flash"


# =====================================================================
# 3.2 Entity Extraction Tests
# =====================================================================

class TestEntityExtraction:
    """Test extract_from_file() with mocked LangExtract responses."""

    def _make_extraction(self, extraction_class, text, attrs=None, **kwargs):
        """Helper to build a fake Extraction object."""
        lx_data = sys.modules["langextract.data"]
        return lx_data.Extraction(
            extraction_class=extraction_class,
            extraction_text=text,
            attributes=attrs or {"description": f"Test {text}", "confidence": 0.9},
            **kwargs,
        )

    def _make_response(self, extractions):
        """Helper to build a fake ExtractionResponse."""
        lx_data = sys.modules["langextract.data"]
        return lx_data.ExtractionResponse(extractions=extractions)

    def _create_service_and_file(self, fake_lx, tmp_path, markdown_text="Medical text."):
        """Helper to create a service with mocked converter and a temp file."""
        mod = _import_service_module()
        with patch("application.services.markitdown_wrapper.MarkItDown"):
            svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy pdf content")

        svc._converter.convert_to_markdown = MagicMock(return_value=markdown_text)
        return mod, svc, test_file

    def test_extract_returns_extraction_result(self, fake_lx, tmp_path):
        """extract_from_file returns an ExtractionResult."""
        mod, svc, test_file = self._create_service_and_file(
            fake_lx, tmp_path, "Some medical text about diabetes."
        )

        fake_lx.extract.return_value = self._make_response([
            self._make_extraction("Disease", "diabetes"),
            self._make_extraction("Drug", "metformin"),
        ])

        result = svc.extract_from_file(str(test_file))

        from application.services.neo4j_pdf_ingestion import ExtractionResult
        assert isinstance(result, ExtractionResult)

    def test_extract_entity_count_matches(self, fake_lx, tmp_path):
        """Number of entities in result matches number of extractions."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)

        fake_lx.extract.return_value = self._make_response([
            self._make_extraction("Disease", "diabetes"),
            self._make_extraction("Drug", "metformin"),
            self._make_extraction("Symptom", "fatigue"),
        ])

        result = svc.extract_from_file(str(test_file))
        assert len(result.entities) == 3

    def test_extract_entities_match_taxonomy(self, fake_lx, tmp_path):
        """Extracted entity types come from the SynapseFlow taxonomy."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)

        fake_lx.extract.return_value = self._make_response([
            self._make_extraction("Disease", "diabetes"),
            self._make_extraction("Treatment", "insulin therapy"),
            self._make_extraction("Symptom", "polyuria"),
            self._make_extraction("Test", "HbA1c"),
            self._make_extraction("Drug", "metformin"),
            self._make_extraction("Gene", "INS"),
            self._make_extraction("Pathway", "insulin signaling"),
            self._make_extraction("Organization", "WHO"),
            self._make_extraction("Study", "UKPDS"),
        ])

        result = svc.extract_from_file(str(test_file))

        for entity in result.entities:
            assert entity.get("type") in mod.ENTITY_TYPES, (
                f"Entity type '{entity.get('type')}' not in taxonomy"
            )

    def test_extract_populates_entity_fields(self, fake_lx, tmp_path):
        """Each entity has name, type, and description fields."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)

        fake_lx.extract.return_value = self._make_response([
            self._make_extraction(
                "Disease", "diabetes",
                {"description": "Metabolic disease", "confidence": 0.95},
            ),
        ])

        result = svc.extract_from_file(str(test_file))

        assert len(result.entities) >= 1
        entity = result.entities[0]
        assert entity["name"] == "diabetes"
        assert entity["type"] == "Disease"
        assert entity["description"] == "Metabolic disease"

    def test_extract_records_timing(self, fake_lx, tmp_path):
        """ExtractionResult includes extraction_time_seconds >= 0."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)

        fake_lx.extract.return_value = self._make_response([])

        result = svc.extract_from_file(str(test_file))
        assert result.extraction_time_seconds >= 0

    def test_extract_calls_lx_extract(self, fake_lx, tmp_path):
        """lx.extract() is called during extraction."""
        mod, svc, test_file = self._create_service_and_file(
            fake_lx, tmp_path, "Medical text content."
        )

        fake_lx.extract.return_value = self._make_response([])

        svc.extract_from_file(str(test_file))
        fake_lx.extract.assert_called_once()

    def test_extract_passes_model_id(self, fake_lx, tmp_path):
        """lx.extract() is called with the configured model_id."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)

        fake_lx.extract.return_value = self._make_response([])

        svc.extract_from_file(str(test_file))

        call_kwargs = fake_lx.extract.call_args
        assert call_kwargs.kwargs.get("model_id") == "gemini-2.5-flash" or \
               (call_kwargs.args and "gemini-2.5-flash" in str(call_kwargs))

    def test_extract_empty_markdown_returns_empty(self, fake_lx, tmp_path):
        """Empty markdown from converter returns empty entities."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)
        svc._converter.convert_to_markdown = MagicMock(return_value=None)

        result = svc.extract_from_file(str(test_file))
        assert result.entities == []
        assert result.relationships == []

    def test_extract_file_not_found_raises(self, fake_lx, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        mod, svc, _ = self._create_service_and_file(fake_lx, tmp_path)

        with pytest.raises(FileNotFoundError):
            svc.extract_from_file(str(tmp_path / "nonexistent.pdf"))

    def test_extract_populates_document_metadata(self, fake_lx, tmp_path):
        """ExtractionResult.document contains file metadata."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)
        fake_lx.extract.return_value = self._make_response([])

        result = svc.extract_from_file(str(test_file))

        assert result.document.filename == "test.pdf"
        assert result.document.path == test_file
        assert result.document.size_bytes > 0

    def test_extract_relationships_is_list(self, fake_lx, tmp_path):
        """ExtractionResult.relationships is a list."""
        mod, svc, test_file = self._create_service_and_file(fake_lx, tmp_path)
        fake_lx.extract.return_value = self._make_response([
            self._make_extraction("Disease", "diabetes"),
        ])

        result = svc.extract_from_file(str(test_file))
        assert isinstance(result.relationships, list)


# =====================================================================
# 3.3 Source Grounding Metadata Mapping Tests
# =====================================================================

class TestSourceGrounding:
    """Test that entity metadata contains source grounding."""

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_entities_have_source_grounding_key(self, mock_markitdown_cls, fake_lx, tmp_path):
        """Each extracted entity has a 'source_grounding' metadata key."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy")

        svc._converter.convert_to_markdown = MagicMock(return_value="Diabetes is a disease.")

        lx_data = sys.modules["langextract.data"]
        extraction = lx_data.Extraction(
            extraction_class="Disease",
            extraction_text="Diabetes",
            attributes={"description": "Metabolic disease", "confidence": 0.9},
            source_text="Diabetes",
            source_start=0,
            source_end=8,
        )
        mock_response = lx_data.ExtractionResponse(extractions=[extraction])
        fake_lx.extract.return_value = mock_response

        result = svc.extract_from_file(str(test_file))

        for entity in result.entities:
            assert "source_grounding" in entity, (
                f"Entity '{entity.get('name')}' missing source_grounding"
            )

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_source_grounding_has_offsets_when_provided(self, mock_markitdown_cls, fake_lx, tmp_path):
        """source_grounding contains start_offset and end_offset from LangExtract."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy")

        svc._converter.convert_to_markdown = MagicMock(return_value="Diabetes is a disease.")

        lx_data = sys.modules["langextract.data"]
        extraction = lx_data.Extraction(
            extraction_class="Disease",
            extraction_text="Diabetes",
            attributes={"description": "Metabolic disease", "confidence": 0.9},
            source_text="Diabetes",
            source_start=0,
            source_end=8,
        )
        mock_response = lx_data.ExtractionResponse(extractions=[extraction])
        fake_lx.extract.return_value = mock_response

        result = svc.extract_from_file(str(test_file))

        entity = result.entities[0]
        grounding = entity["source_grounding"]
        assert grounding.get("start_offset") == 0
        assert grounding.get("end_offset") == 8
        assert grounding.get("source_text") == "Diabetes"

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_source_grounding_empty_when_no_grounding_data(self, mock_markitdown_cls, fake_lx, tmp_path):
        """source_grounding is empty dict when extraction has no grounding fields."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy")

        svc._converter.convert_to_markdown = MagicMock(return_value="Diabetes.")

        lx_data = sys.modules["langextract.data"]
        # Extraction without source_text/source_start/source_end
        extraction = lx_data.Extraction(
            extraction_class="Disease",
            extraction_text="Diabetes",
            attributes={"description": "A disease", "confidence": 0.9},
        )
        mock_response = lx_data.ExtractionResponse(extractions=[extraction])
        fake_lx.extract.return_value = mock_response

        result = svc.extract_from_file(str(test_file))

        entity = result.entities[0]
        assert "source_grounding" in entity
        assert entity["source_grounding"] == {}

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_map_source_grounding_direct_call(self, mock_markitdown_cls, fake_lx):
        """_map_source_grounding processes raw extraction dicts correctly."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        raw = [
            {
                "name": "Diabetes",
                "type": "Disease",
                "description": "Metabolic disease",
                "confidence": 0.9,
                "_source_text": "Diabetes",
                "_source_start": 0,
                "_source_end": 8,
            }
        ]

        result = svc._map_source_grounding(raw)

        assert len(result) == 1
        assert result[0]["source_grounding"]["source_text"] == "Diabetes"
        assert result[0]["source_grounding"]["start_offset"] == 0
        assert result[0]["source_grounding"]["end_offset"] == 8

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_map_source_grounding_preserves_entity_fields(self, mock_markitdown_cls, fake_lx):
        """_map_source_grounding preserves name, type, description."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        raw = [
            {
                "name": "metformin",
                "type": "Drug",
                "description": "Antidiabetic drug",
                "confidence": 0.85,
            }
        ]

        result = svc._map_source_grounding(raw)

        assert result[0]["name"] == "metformin"
        assert result[0]["type"] == "Drug"
        assert result[0]["description"] == "Antidiabetic drug"


# =====================================================================
# 3.4 DIKW Layer Assignment and Confidence Tests
# =====================================================================

class TestDIKWLayerAssignment:
    """Test that all entities get PERCEPTION layer and confidence 0.7."""

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_entities_have_perception_layer(self, mock_markitdown_cls, fake_lx, tmp_path):
        """All extracted entities are assigned layer='PERCEPTION'."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy")

        svc._converter.convert_to_markdown = MagicMock(return_value="Medical text.")

        lx_data = sys.modules["langextract.data"]
        mock_response = lx_data.ExtractionResponse(
            extractions=[
                lx_data.Extraction(
                    extraction_class="Disease",
                    extraction_text="diabetes",
                    attributes={"description": "A disease", "confidence": 0.9},
                ),
                lx_data.Extraction(
                    extraction_class="Drug",
                    extraction_text="metformin",
                    attributes={"description": "A drug", "confidence": 0.85},
                ),
            ]
        )
        fake_lx.extract.return_value = mock_response

        result = svc.extract_from_file(str(test_file))

        for entity in result.entities:
            assert entity.get("layer") == "PERCEPTION", (
                f"Entity '{entity.get('name')}' should have layer='PERCEPTION', "
                f"got '{entity.get('layer')}'"
            )

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_entities_have_confidence_07(self, mock_markitdown_cls, fake_lx, tmp_path):
        """All extracted entities are assigned confidence=0.7 (PERCEPTION baseline)."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy")

        svc._converter.convert_to_markdown = MagicMock(return_value="Medical text.")

        lx_data = sys.modules["langextract.data"]
        mock_response = lx_data.ExtractionResponse(
            extractions=[
                lx_data.Extraction(
                    extraction_class="Disease",
                    extraction_text="diabetes",
                    attributes={"description": "A disease", "confidence": 0.95},
                ),
            ]
        )
        fake_lx.extract.return_value = mock_response

        result = svc.extract_from_file(str(test_file))

        for entity in result.entities:
            assert entity.get("confidence") == 0.7, (
                f"Entity '{entity.get('name')}' should have confidence=0.7, "
                f"got {entity.get('confidence')}"
            )

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_assign_dikw_layer_direct_call(self, mock_markitdown_cls, fake_lx):
        """_assign_dikw_layer adds layer and confidence to entity dicts."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        entities = [
            {"name": "diabetes", "type": "Disease"},
            {"name": "metformin", "type": "Drug"},
        ]

        result = svc._assign_dikw_layer(entities)

        assert len(result) == 2
        for entity in result:
            assert entity["layer"] == "PERCEPTION"
            assert entity["confidence"] == 0.7

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_dikw_layer_preserves_existing_fields(self, mock_markitdown_cls, fake_lx):
        """_assign_dikw_layer preserves existing entity fields."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        entities = [
            {"name": "diabetes", "type": "Disease", "description": "Metabolic disease",
             "source_grounding": {"start_offset": 0, "end_offset": 8}},
        ]

        result = svc._assign_dikw_layer(entities)

        assert result[0]["name"] == "diabetes"
        assert result[0]["type"] == "Disease"
        assert result[0]["description"] == "Metabolic disease"
        assert result[0]["source_grounding"]["start_offset"] == 0

    @patch("application.services.markitdown_wrapper.MarkItDown")
    def test_dikw_overrides_extraction_confidence(self, mock_markitdown_cls, fake_lx):
        """_assign_dikw_layer overrides any existing confidence with 0.7."""
        mod = _import_service_module()
        svc = mod.LangExtractIngestionService(api_key="test-key")

        entities = [
            {"name": "diabetes", "type": "Disease", "confidence": 0.95},
        ]

        result = svc._assign_dikw_layer(entities)
        assert result[0]["confidence"] == 0.7
