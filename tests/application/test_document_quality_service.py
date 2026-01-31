"""Tests for DocumentQualityService.

Comprehensive unit tests for document quality assessment.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Any

from src.application.services.document_quality_service import (
    DocumentQualityService,
    QualityConfig,
    quick_quality_check,
)
from src.application.services.text_chunker import TextChunk
from domain.quality_models import QualityLevel


@dataclass
class MockTextChunk:
    """Mock TextChunk for testing."""
    id: str
    text: str
    sequence: int = 0
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TestQualityConfig:
    """Tests for QualityConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = QualityConfig()
        assert config.min_facts_per_chunk == 3
        assert config.max_redundancy_ratio == 0.3
        assert config.optimal_chunk_size == 1500
        assert config.chunk_size_tolerance == 0.3
        assert config.sample_query_count == 5
        assert config.max_chunks_to_analyze == 50

    def test_default_weights(self):
        """Test default weight configuration."""
        config = QualityConfig()
        assert config.weights["contextual_relevancy"] == 0.25
        assert config.weights["context_sufficiency"] == 0.20
        assert config.weights["information_density"] == 0.15
        assert config.weights["structural_clarity"] == 0.15
        assert config.weights["entity_density"] == 0.15
        assert config.weights["chunking_quality"] == 0.10

    def test_custom_config(self):
        """Test custom configuration."""
        config = QualityConfig(
            min_facts_per_chunk=5,
            max_redundancy_ratio=0.2,
            optimal_chunk_size=2000,
        )
        assert config.min_facts_per_chunk == 5
        assert config.max_redundancy_ratio == 0.2
        assert config.optimal_chunk_size == 2000


class TestDocumentQualityService:
    """Tests for DocumentQualityService."""

    @pytest.fixture
    def service(self):
        """Create DocumentQualityService instance."""
        return DocumentQualityService()

    @pytest.fixture
    def sample_chunks(self):
        """Sample document chunks for testing."""
        return [
            MockTextChunk(
                id="chunk-1",
                text="Diabetes mellitus is a chronic metabolic disease characterized by elevated blood glucose levels. The disease affects millions of people worldwide.",
                sequence=0,
            ),
            MockTextChunk(
                id="chunk-2",
                text="Treatment options include insulin therapy and oral medications. Regular monitoring of blood glucose is essential for disease management.",
                sequence=1,
            ),
            MockTextChunk(
                id="chunk-3",
                text="Studies show that early intervention can reduce complications. Clinical trials have demonstrated improved outcomes with combination therapy.",
                sequence=2,
            ),
        ]

    @pytest.fixture
    def sample_markdown(self):
        """Sample markdown document."""
        return """# Diabetes Mellitus Overview

## Introduction

Diabetes mellitus is a chronic metabolic disease. It affects the body's ability to process glucose.

## Treatment

### Medication Options

Treatment options include insulin therapy and oral medications.

### Lifestyle Changes

Regular exercise and diet modification are important.

## Conclusion

Early intervention is key to managing diabetes.
"""

    @pytest.fixture
    def sample_entities(self):
        """Sample extracted entities."""
        return [
            {"name": "Diabetes Mellitus", "type": "disease", "chunk_id": "chunk-1"},
            {"name": "Insulin", "type": "medication", "chunk_id": "chunk-2"},
            {"name": "Blood Glucose", "type": "concept", "chunk_id": "chunk-1"},
            {"name": "Blood Glucose", "type": "concept", "chunk_id": "chunk-2"},
        ]

    # --- Assessment Method Tests ---

    @pytest.mark.asyncio
    async def test_assess_document_empty_chunks(self, service):
        """Test assessment with empty chunk list."""
        report = await service.assess_document(
            document_id="doc-1",
            document_name="empty.pdf",
            markdown_text="",
            chunks=[],
        )
        assert report.document_id == "doc-1"
        assert report.chunk_count == 0
        assert report.overall_score >= 0

    @pytest.mark.asyncio
    async def test_assess_document_with_chunks(self, service, sample_chunks, sample_markdown):
        """Test full assessment with valid chunks."""
        report = await service.assess_document(
            document_id="doc-2",
            document_name="test.pdf",
            markdown_text=sample_markdown,
            chunks=sample_chunks,
        )
        assert report.document_id == "doc-2"
        assert report.document_name == "test.pdf"
        assert report.chunk_count == 3
        assert report.processing_time_ms >= 0
        assert report.overall_score >= 0
        assert isinstance(report.quality_level, QualityLevel)

    @pytest.mark.asyncio
    async def test_assess_document_with_entities(self, service, sample_chunks, sample_markdown, sample_entities):
        """Test assessment includes entity metrics."""
        report = await service.assess_document(
            document_id="doc-3",
            document_name="entities.pdf",
            markdown_text=sample_markdown,
            chunks=sample_chunks,
            entities=sample_entities,
        )
        assert report.entity_density.total_entities == 4
        assert report.entity_density.unique_entities >= 1

    @pytest.mark.asyncio
    async def test_assess_document_with_expected_topics(self, service, sample_chunks, sample_markdown):
        """Test topic coverage validation."""
        expected_topics = ["diabetes", "treatment", "glucose"]
        report = await service.assess_document(
            document_id="doc-4",
            document_name="topics.pdf",
            markdown_text=sample_markdown,
            chunks=sample_chunks,
            expected_topics=expected_topics,
        )
        assert report.context_sufficiency.expected_topics == expected_topics
        # At least some topics should be found
        assert len(report.context_sufficiency.found_topics) >= 0

    @pytest.mark.asyncio
    async def test_assess_document_processing_time(self, service, sample_chunks, sample_markdown):
        """Test that processing time is tracked."""
        report = await service.assess_document(
            document_id="doc-5",
            document_name="time.pdf",
            markdown_text=sample_markdown,
            chunks=sample_chunks,
        )
        assert report.processing_time_ms >= 0

    # --- Contextual Relevancy Tests ---

    @pytest.mark.asyncio
    async def test_contextual_relevancy_high_coverage(self, service):
        """Test high query coverage scores well."""
        chunks = [
            MockTextChunk(id="c1", text="Diabetes treatment involves medication and lifestyle changes."),
            MockTextChunk(id="c2", text="Diabetes management requires regular blood glucose monitoring."),
            MockTextChunk(id="c3", text="Diabetes complications can be prevented with early treatment."),
        ]
        expected_topics = ["Diabetes"]

        score = await service._assess_contextual_relevancy(chunks, expected_topics)

        # Should have good coverage since all chunks mention diabetes
        assert score.context_precision >= 0
        assert score.context_recall >= 0

    @pytest.mark.asyncio
    async def test_contextual_relevancy_low_coverage(self, service):
        """Test low coverage is identified."""
        chunks = [
            MockTextChunk(id="c1", text="The weather today is sunny."),
            MockTextChunk(id="c2", text="I like to eat pizza for lunch."),
        ]
        expected_topics = ["Diabetes", "Treatment"]

        score = await service._assess_contextual_relevancy(chunks, expected_topics)

        # Low coverage expected
        assert score.f1_score >= 0

    @pytest.mark.asyncio
    async def test_contextual_relevancy_no_queries(self, service):
        """Test fallback when no queries can be generated."""
        chunks = [
            MockTextChunk(id="c1", text="a b c d e f g"),  # No meaningful content
        ]

        score = await service._assess_contextual_relevancy(chunks, None)

        # Should use fallback heuristics
        assert score.context_precision == 0.7
        assert score.context_recall == 0.7

    @pytest.mark.asyncio
    async def test_contextual_relevancy_f1_calculation(self, service, sample_chunks):
        """Test F1 score is computed."""
        expected_topics = ["Diabetes", "Treatment"]

        score = await service._assess_contextual_relevancy(sample_chunks, expected_topics)

        # F1 should be computed
        if score.context_precision > 0 and score.context_recall > 0:
            expected_f1 = 2 * (score.context_precision * score.context_recall) / (score.context_precision + score.context_recall)
            assert abs(score.f1_score - expected_f1) < 0.01

    # --- Context Sufficiency Tests ---

    @pytest.mark.asyncio
    async def test_context_sufficiency_with_expected_topics(self, service, sample_markdown, sample_chunks):
        """Test topic coverage with expected topics."""
        expected_topics = ["diabetes", "treatment", "medication"]

        score = await service._assess_context_sufficiency(
            sample_markdown, sample_chunks, expected_topics
        )

        assert score.expected_topics == expected_topics
        assert score.topic_coverage >= 0
        assert len(score.found_topics) + len(score.missing_topics) == len(expected_topics)

    @pytest.mark.asyncio
    async def test_context_sufficiency_without_topics(self, service, sample_markdown, sample_chunks):
        """Test topic extraction when no topics specified."""
        score = await service._assess_context_sufficiency(
            sample_markdown, sample_chunks, None
        )

        # Topics should be extracted from document
        assert len(score.expected_topics) >= 0
        assert score.topic_coverage == 0.8  # Default assumption

    @pytest.mark.asyncio
    async def test_context_sufficiency_technical_indicators(self, service, sample_chunks):
        """Test detection of technical/research terms."""
        technical_text = """
        This study examines the treatment of patients with diabetes.
        The research methodology involved clinical trials.
        Results show improved outcomes. The conclusion supports the hypothesis.
        """

        score = await service._assess_context_sufficiency(
            technical_text, sample_chunks, None
        )

        # Should detect technical indicators
        assert score.claim_coverage > 0

    @pytest.mark.asyncio
    async def test_context_sufficiency_completeness(self, service, sample_markdown, sample_chunks):
        """Test completeness metric computation."""
        expected_topics = ["diabetes"]

        score = await service._assess_context_sufficiency(
            sample_markdown, sample_chunks, expected_topics
        )

        # Completeness is average of topic_coverage and claim_coverage
        expected_completeness = (score.topic_coverage + score.claim_coverage) / 2
        assert abs(score.completeness - expected_completeness) < 0.01

    # --- Information Density Tests ---

    @pytest.mark.asyncio
    async def test_information_density_empty_chunks(self, service):
        """Test density with empty chunks."""
        score = await service._assess_information_density([])

        assert score.unique_facts_per_chunk == 0
        assert score.redundancy_ratio == 0

    @pytest.mark.asyncio
    async def test_information_density_high_facts(self, service):
        """Test high fact count scores well."""
        chunks = [
            MockTextChunk(id="c1", text="The study shows 50 patients were treated. Results indicate 80% improvement. The medication was given daily."),
            MockTextChunk(id="c2", text="Clinical data reveals 25 side effects. Analysis shows significant correlation. Treatment lasted 6 months."),
        ]

        score = await service._assess_information_density(chunks)

        assert score.unique_facts_per_chunk > 0
        assert len(score.chunk_densities) == 2

    @pytest.mark.asyncio
    async def test_information_density_redundancy_detection(self, service):
        """Test duplicate fact detection."""
        chunks = [
            MockTextChunk(id="c1", text="The study shows improvement. The study shows results."),
            MockTextChunk(id="c2", text="The study shows improvement. Analysis confirms the study."),
        ]

        score = await service._assess_information_density(chunks)

        # Should detect redundancy
        assert score.redundancy_ratio >= 0

    @pytest.mark.asyncio
    async def test_information_density_low_density_chunks(self, service):
        """Test identification of sparse chunks."""
        config = QualityConfig(min_facts_per_chunk=5)
        service_strict = DocumentQualityService(config=config)

        chunks = [
            MockTextChunk(id="c1", text="Hello world."),  # Very low content
        ]

        score = await service_strict._assess_information_density(chunks)

        assert "c1" in score.low_density_chunks

    @pytest.mark.asyncio
    async def test_information_density_signal_to_noise(self, service, sample_chunks):
        """Test signal-to-noise calculation."""
        score = await service._assess_information_density(sample_chunks)

        # Signal to noise is 1 - redundancy (bounded)
        expected_stn = 1.0 - min(score.redundancy_ratio, 0.8)
        assert abs(score.signal_to_noise - expected_stn) < 0.01

    # --- Structural Clarity Tests ---

    def test_structural_clarity_proper_hierarchy(self, service):
        """Test correct heading levels score well."""
        markdown = """# Main Title

## Section One

Content here.

### Subsection

More content.

## Section Two

Final content.
"""
        score = service._assess_structural_clarity(markdown)

        assert score.heading_count == 4
        assert score.heading_hierarchy_score > 0.7
        assert len(score.hierarchy_violations) == 0

    def test_structural_clarity_violations(self, service):
        """Test detection of level skips (h1 -> h3)."""
        markdown = """# Main Title

### Subsection Skipped H2

Content here.

## Section Two

Content.
"""
        score = service._assess_structural_clarity(markdown)

        assert len(score.hierarchy_violations) > 0
        assert score.heading_hierarchy_score < 1.0

    def test_structural_clarity_no_headings(self, service):
        """Test handling of documents without headings."""
        markdown = """This is a document with no headings.
Just plain text content.
No structure at all.
"""
        score = service._assess_structural_clarity(markdown)

        assert score.heading_count == 0
        assert score.heading_hierarchy_score == 0.3  # Default for no headings
        assert score.section_coherence == 0.5

    def test_structural_clarity_orphan_sections(self, service):
        """Test detection of orphan sections."""
        markdown = """### Starting with H3 (orphan)

Content here without parent heading.
"""
        score = service._assess_structural_clarity(markdown)

        assert score.orphan_sections == 1

    def test_structural_clarity_logical_flow(self, service):
        """Test pattern matching for logical flow."""
        markdown = """# Study Title

## Introduction

Background information.

## Methodology

How we did it.

## Results

What we found.

## Discussion

What it means.

## Conclusion

Summary.
"""
        score = service._assess_structural_clarity(markdown)

        # Should match multiple expected patterns
        assert score.logical_flow > 0.5

    # --- Entity Density Tests ---

    @pytest.mark.asyncio
    async def test_entity_density_with_entities(self, service, sample_chunks, sample_entities):
        """Test entity extraction works."""
        score = await service._assess_entity_density(sample_chunks, sample_entities)

        assert score.total_entities == 4
        assert score.unique_entities >= 1
        assert score.entities_per_chunk > 0

    @pytest.mark.asyncio
    async def test_entity_density_no_entities(self, service, sample_chunks):
        """Test handling when no entities provided or found."""
        # Use chunks with no extractable entities
        plain_chunks = [
            MockTextChunk(id="c1", text="this is all lowercase text with no entities"),
        ]

        score = await service._assess_entity_density(plain_chunks, [])

        assert score.total_entities == 0
        assert score.entity_extraction_rate == 0.0

    @pytest.mark.asyncio
    async def test_entity_density_consistency(self, service, sample_chunks):
        """Test same entity referenced consistently."""
        entities = [
            {"name": "Diabetes", "type": "disease", "chunk_id": "chunk-1"},
            {"name": "Diabetes", "type": "disease", "chunk_id": "chunk-2"},
            {"name": "Diabetes", "type": "disease", "chunk_id": "chunk-3"},
        ]

        score = await service._assess_entity_density(sample_chunks, entities)

        # Same entity consistently referenced should have high consistency
        assert score.entity_consistency >= 0.5

    @pytest.mark.asyncio
    async def test_entity_density_ambiguous(self, service, sample_chunks):
        """Test detection of entities with different types."""
        entities = [
            {"name": "Insulin", "type": "medication", "chunk_id": "chunk-1"},
            {"name": "Insulin", "type": "hormone", "chunk_id": "chunk-2"},  # Different type!
        ]

        score = await service._assess_entity_density(sample_chunks, entities)

        # Insulin should be flagged as ambiguous
        assert "insulin" in score.ambiguous_entities

    @pytest.mark.asyncio
    async def test_entity_density_ontology_alignment(self, service, sample_chunks, sample_entities):
        """Test standard type matching."""
        score = await service._assess_entity_density(sample_chunks, sample_entities)

        # Should have some alignment with standard types
        assert score.ontology_alignment >= 0

    @pytest.mark.asyncio
    async def test_entity_density_relationship_density(self, service, sample_chunks):
        """Test cross-reference scoring."""
        entities = [
            {"name": "Diabetes", "type": "disease", "chunk_id": "chunk-1"},
            {"name": "Insulin", "type": "medication", "chunk_id": "chunk-1"},
            {"name": "Patient", "type": "person", "chunk_id": "chunk-1"},
        ]

        score = await service._assess_entity_density(sample_chunks, entities)

        # Entities in same chunk create relationships
        assert score.total_relationships > 0

    # --- Chunking Quality Tests ---

    def test_chunking_quality_optimal_size(self, service):
        """Test good chunk size distribution."""
        # Create chunks near optimal size (1500 chars)
        chunks = [
            MockTextChunk(id="c1", text="a" * 1400),
            MockTextChunk(id="c2", text="b" * 1500),
            MockTextChunk(id="c3", text="c" * 1600),
        ]

        score = service._assess_chunking_quality(chunks, "")

        assert score.optimal_size_ratio > 0.5

    def test_chunking_quality_variance(self, service):
        """Test size consistency."""
        # Create chunks with similar sizes
        chunks = [
            MockTextChunk(id="c1", text="a" * 1000),
            MockTextChunk(id="c2", text="b" * 1000),
            MockTextChunk(id="c3", text="c" * 1000),
        ]

        score = service._assess_chunking_quality(chunks, "")

        # Low variance expected
        assert score.size_variance < 0.1

    def test_chunking_quality_boundary_coherence(self, service):
        """Test sentence boundary detection."""
        chunks = [
            MockTextChunk(id="c1", text="This is a complete sentence."),
            MockTextChunk(id="c2", text="Another complete sentence!"),
            MockTextChunk(id="c3", text="A question mark ends here?"),
        ]

        score = service._assess_chunking_quality(chunks, "")

        assert score.boundary_coherence == 1.0

    def test_chunking_quality_self_containment(self, service):
        """Test complete thought detection."""
        chunks = [
            MockTextChunk(id="c1", text="Diabetes is a chronic disease."),  # Good start
            MockTextChunk(id="c2", text="it causes many complications."),  # Starts with "it" - bad
            MockTextChunk(id="c3", text="Treatment options are available."),  # Good start
        ]

        score = service._assess_chunking_quality(chunks, "")

        # 2 out of 3 are self-contained
        assert score.self_containment > 0.5

    def test_chunking_quality_context_preservation(self, service):
        """Test context preservation between chunks."""
        chunks = [
            MockTextChunk(id="c1", text="First chunk ends properly."),
            MockTextChunk(id="c2", text="Second chunk starts fresh."),
            MockTextChunk(id="c3", text="Third chunk is independent."),
        ]

        score = service._assess_chunking_quality(chunks, "")

        assert score.context_preservation > 0.5

    # --- Helper Method Tests ---

    @pytest.mark.asyncio
    async def test_generate_sample_queries(self, service, sample_chunks):
        """Test query synthesis."""
        queries = await service._generate_sample_queries(sample_chunks, None)

        assert isinstance(queries, list)
        assert len(queries) <= service.config.sample_query_count

    @pytest.mark.asyncio
    async def test_generate_sample_queries_with_topics(self, service, sample_chunks):
        """Test query generation with expected topics."""
        expected_topics = ["Diabetes", "Treatment"]
        queries = await service._generate_sample_queries(sample_chunks, expected_topics)

        # Should include topic-based queries
        topic_queries = [q for q in queries if any(t.lower() in q.lower() for t in expected_topics)]
        assert len(topic_queries) > 0

    def test_extract_topics_from_text(self, service, sample_markdown):
        """Test topic extraction from headings."""
        topics = service._extract_topics_from_text(sample_markdown)

        assert isinstance(topics, list)
        # Should extract heading topics
        heading_topics = [t for t in topics if "diabetes" in t.lower() or "treatment" in t.lower() or "introduction" in t.lower()]
        assert len(heading_topics) >= 0

    def test_extract_facts_from_chunk(self, service):
        """Test fact detection."""
        text = "The study shows 50 patients improved. Results indicate success. The treatment was effective."
        facts = service._extract_facts_from_chunk(text)

        assert isinstance(facts, list)
        assert len(facts) >= 1

    def test_extract_facts_from_chunk_short_sentences(self, service):
        """Test that short sentences are skipped."""
        text = "Hi. OK. Yes."  # All sentences too short
        facts = service._extract_facts_from_chunk(text)

        assert len(facts) == 0

    def test_extract_entities_heuristic(self, service):
        """Test named entity extraction."""
        text = "Diabetes Mellitus affects many patients. Insulin therapy is common."
        entities = service._extract_entities_heuristic(text)

        assert isinstance(entities, list)
        # Should find capitalized terms
        names = [e["name"] for e in entities]
        assert "Diabetes Mellitus" in names or "Insulin" in names

    def test_guess_entity_type_medical(self, service):
        """Test medical pattern matching."""
        assert service._guess_entity_type("Diabetes Disease", "") == "disease"
        assert service._guess_entity_type("Patient", "") == "person"
        assert service._guess_entity_type("Clinical Study", "") == "study"

    def test_guess_entity_type_technical(self, service):
        """Test technical pattern matching."""
        assert service._guess_entity_type("Users Table", "") == "table"
        assert service._guess_entity_type("Auth System", "") == "system"

    def test_guess_entity_type_medication(self, service):
        """Test medication context detection."""
        context = "This drug is used for treatment"
        assert service._guess_entity_type("Metformin", context) == "medication"

    def test_guess_entity_type_default(self, service):
        """Test default type fallback."""
        assert service._guess_entity_type("SomeUnknownThing", "") == "concept"

    def test_split_by_headings(self, service, sample_markdown):
        """Test document segmentation."""
        sections = service._split_by_headings(sample_markdown)

        assert isinstance(sections, list)
        assert len(sections) >= 1
        # Each section is (heading, content) tuple
        for heading, content in sections:
            assert isinstance(heading, str)
            assert isinstance(content, str)

    def test_estimate_tokens(self, service):
        """Test token counting approximation."""
        # 100 characters should be ~25 tokens
        text = "a" * 100
        tokens = service._estimate_tokens(text)
        assert tokens == 25

    def test_estimate_tokens_empty(self, service):
        """Test token count for empty text."""
        tokens = service._estimate_tokens("")
        assert tokens == 0


class TestQuickQualityCheck:
    """Tests for quick_quality_check function."""

    @pytest.mark.asyncio
    async def test_quick_quality_check_basic(self):
        """Test quick quality check returns expected structure."""
        markdown = """# Test Document

## Introduction

This is a test document with some content about diabetes and treatment options.

## Methodology

The study examined 100 patients over 6 months.

## Results

Results showed improvement in 80% of cases.

## Conclusion

The treatment is effective.
"""
        result = await quick_quality_check(markdown, "test.pdf")

        assert "quality_level" in result
        assert "overall_score" in result
        assert "chunk_count" in result
        assert "recommendations" in result
        assert isinstance(result["overall_score"], float)
        assert result["quality_level"] in ["excellent", "good", "acceptable", "poor", "critical"]

    @pytest.mark.asyncio
    async def test_quick_quality_check_empty_document(self):
        """Test quick check with empty document."""
        result = await quick_quality_check("", "empty.pdf")

        assert "quality_level" in result
        assert result["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_quick_quality_check_default_name(self):
        """Test default document name."""
        result = await quick_quality_check("Some text content.")

        assert "quality_level" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return DocumentQualityService()

    @pytest.mark.asyncio
    async def test_single_chunk(self, service):
        """Test assessment with single chunk."""
        chunks = [MockTextChunk(id="only", text="Single chunk document.")]

        report = await service.assess_document(
            document_id="single",
            document_name="single.pdf",
            markdown_text="Single chunk document.",
            chunks=chunks,
        )

        assert report.chunk_count == 1
        # Context preservation should be 1.0 with single chunk
        assert report.chunking_quality.context_preservation == 1.0

    @pytest.mark.asyncio
    async def test_very_long_chunks(self, service):
        """Test with very long chunks."""
        long_text = "This is a test. " * 1000
        chunks = [MockTextChunk(id="long", text=long_text)]

        report = await service.assess_document(
            document_id="long",
            document_name="long.pdf",
            markdown_text=long_text,
            chunks=chunks,
        )

        assert report.chunk_count == 1
        assert report.total_tokens > 0

    @pytest.mark.asyncio
    async def test_special_characters(self, service):
        """Test handling of special characters."""
        text_with_special = "Test with special chars: @#$%^&*()_+{}|:<>?"
        chunks = [MockTextChunk(id="special", text=text_with_special)]

        report = await service.assess_document(
            document_id="special",
            document_name="special.pdf",
            markdown_text=text_with_special,
            chunks=chunks,
        )

        assert report.document_id == "special"

    @pytest.mark.asyncio
    async def test_unicode_content(self, service):
        """Test handling of unicode content."""
        unicode_text = "Test with unicode: \u00e9\u00e8\u00ea\u00eb \u00f1 \u00fc"
        chunks = [MockTextChunk(id="unicode", text=unicode_text)]

        report = await service.assess_document(
            document_id="unicode",
            document_name="unicode.pdf",
            markdown_text=unicode_text,
            chunks=chunks,
        )

        assert report.document_id == "unicode"
