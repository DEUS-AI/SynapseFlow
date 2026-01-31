"""Tests for Quality Models.

Unit tests for DocumentQualityReport and OntologyQualityReport models.
"""

import pytest
from datetime import datetime
from src.domain.quality_models import (
    QualityLevel,
    ContextualRelevancyScore,
    ContextSufficiencyScore,
    InformationDensityScore,
    StructuralClarityScore,
    EntityDensityScore,
    ChunkingQualityScore,
    DocumentQualityReport,
)
from src.domain.ontology_quality_models import (
    OntologyQualityLevel,
    OntologyCoverageScore,
    SchemaComplianceScore,
    TaxonomyCoherenceScore,
    MappingConsistencyScore,
    NormalizationQualityScore,
    CrossReferenceValidityScore,
    InteroperabilityScore,
    OntologyQualityReport,
)


class TestQualityLevel:
    """Tests for QualityLevel enum."""

    def test_quality_level_values(self):
        """Test quality level enum values."""
        assert QualityLevel.EXCELLENT.value == "excellent"
        assert QualityLevel.GOOD.value == "good"
        assert QualityLevel.ACCEPTABLE.value == "acceptable"
        assert QualityLevel.POOR.value == "poor"
        assert QualityLevel.CRITICAL.value == "critical"

    def test_ontology_quality_level_values(self):
        """Test ontology quality level enum values."""
        assert OntologyQualityLevel.EXCELLENT.value == "excellent"
        assert OntologyQualityLevel.GOOD.value == "good"
        assert OntologyQualityLevel.ACCEPTABLE.value == "acceptable"
        assert OntologyQualityLevel.POOR.value == "poor"
        assert OntologyQualityLevel.CRITICAL.value == "critical"


class TestContextualRelevancyScore:
    """Tests for ContextualRelevancyScore."""

    def test_default_values(self):
        """Test default initialization values."""
        score = ContextualRelevancyScore()
        assert score.context_precision == 0.0
        assert score.context_recall == 0.0
        assert score.context_relevancy == 0.0
        assert score.f1_score == 0.0
        assert score.sample_queries == []
        assert score.query_coverage == {}

    def test_compute_f1_score(self):
        """Test F1 score computation."""
        score = ContextualRelevancyScore(
            context_precision=0.8,
            context_recall=0.6
        )
        f1 = score.compute_f1()
        expected = 2 * (0.8 * 0.6) / (0.8 + 0.6)  # 0.6857...
        assert abs(f1 - expected) < 0.001

    def test_compute_f1_zero_division(self):
        """Test F1 score with zero precision and recall."""
        score = ContextualRelevancyScore(
            context_precision=0.0,
            context_recall=0.0
        )
        f1 = score.compute_f1()
        assert f1 == 0.0


class TestDocumentQualityReport:
    """Tests for DocumentQualityReport."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample report for testing."""
        return DocumentQualityReport(
            document_id="doc-123",
            document_name="test.pdf"
        )

    @pytest.fixture
    def high_quality_report(self):
        """Create a high quality report."""
        report = DocumentQualityReport(
            document_id="doc-high",
            document_name="excellent.pdf"
        )
        # Set high scores
        report.contextual_relevancy.f1_score = 0.95
        report.context_sufficiency.completeness = 0.92
        report.information_density.signal_to_noise = 0.90
        report.structural_clarity.section_coherence = 0.88
        report.entity_density.entity_consistency = 0.91
        report.chunking_quality.retrieval_quality = 0.89
        return report

    @pytest.fixture
    def low_quality_report(self):
        """Create a low quality report."""
        report = DocumentQualityReport(
            document_id="doc-low",
            document_name="poor.pdf"
        )
        # Set low scores
        report.contextual_relevancy.f1_score = 0.25
        report.contextual_relevancy.context_precision = 0.3
        report.contextual_relevancy.context_recall = 0.2
        report.context_sufficiency.completeness = 0.2
        report.context_sufficiency.topic_coverage = 0.3
        report.context_sufficiency.missing_topics = ["topic1", "topic2", "topic3"]
        report.information_density.signal_to_noise = 0.25
        report.information_density.redundancy_ratio = 0.5
        report.information_density.unique_facts_per_chunk = 1.5
        report.structural_clarity.section_coherence = 0.3
        report.structural_clarity.heading_hierarchy_score = 0.4
        report.structural_clarity.orphan_sections = 3
        report.entity_density.entity_consistency = 0.2
        report.entity_density.entity_extraction_rate = 0.3
        report.entity_density.ambiguous_entities = ["entity1", "entity2"]
        report.chunking_quality.retrieval_quality = 0.25
        report.chunking_quality.boundary_coherence = 0.4
        return report

    def test_default_values(self, sample_report):
        """Test default initialization values."""
        assert sample_report.document_id == "doc-123"
        assert sample_report.document_name == "test.pdf"
        assert sample_report.overall_score == 0.0
        assert sample_report.quality_level == QualityLevel.ACCEPTABLE
        assert sample_report.recommendations == []

    def test_compute_overall_score_default_weights(self, high_quality_report):
        """Test overall score computation with default weights."""
        score = high_quality_report.compute_overall_score()
        # Default weights: 0.25 + 0.20 + 0.15 + 0.15 + 0.15 + 0.10 = 1.0
        expected = (
            0.95 * 0.25 +  # contextual_relevancy
            0.92 * 0.20 +  # context_sufficiency
            0.90 * 0.15 +  # information_density
            0.88 * 0.15 +  # structural_clarity
            0.91 * 0.15 +  # entity_density
            0.89 * 0.10    # chunking_quality
        )
        assert abs(score - expected) < 0.001

    def test_compute_overall_score_custom_weights(self, high_quality_report):
        """Test overall score computation with custom weights."""
        custom_weights = {
            "contextual_relevancy": 0.5,
            "context_sufficiency": 0.2,
            "information_density": 0.1,
            "structural_clarity": 0.1,
            "entity_density": 0.05,
            "chunking_quality": 0.05,
        }
        score = high_quality_report.compute_overall_score(weights=custom_weights)
        expected = (
            0.95 * 0.5 +   # contextual_relevancy - weighted higher
            0.92 * 0.2 +   # context_sufficiency
            0.90 * 0.1 +   # information_density
            0.88 * 0.1 +   # structural_clarity
            0.91 * 0.05 +  # entity_density
            0.89 * 0.05    # chunking_quality
        )
        assert abs(score - expected) < 0.001

    def test_quality_level_excellent(self):
        """Test EXCELLENT quality level (>= 0.9)."""
        report = DocumentQualityReport(
            document_id="doc",
            document_name="test.pdf"
        )
        report.contextual_relevancy.f1_score = 0.95
        report.context_sufficiency.completeness = 0.95
        report.information_density.signal_to_noise = 0.95
        report.structural_clarity.section_coherence = 0.95
        report.entity_density.entity_consistency = 0.95
        report.chunking_quality.retrieval_quality = 0.95

        report.compute_overall_score()
        assert report.quality_level == QualityLevel.EXCELLENT
        assert report.overall_score >= 0.9

    def test_quality_level_good(self):
        """Test GOOD quality level (0.7-0.9)."""
        report = DocumentQualityReport(
            document_id="doc",
            document_name="test.pdf"
        )
        report.contextual_relevancy.f1_score = 0.8
        report.context_sufficiency.completeness = 0.8
        report.information_density.signal_to_noise = 0.8
        report.structural_clarity.section_coherence = 0.8
        report.entity_density.entity_consistency = 0.8
        report.chunking_quality.retrieval_quality = 0.8

        report.compute_overall_score()
        assert report.quality_level == QualityLevel.GOOD
        assert 0.7 <= report.overall_score < 0.9

    def test_quality_level_acceptable(self):
        """Test ACCEPTABLE quality level (0.5-0.7)."""
        report = DocumentQualityReport(
            document_id="doc",
            document_name="test.pdf"
        )
        report.contextual_relevancy.f1_score = 0.6
        report.context_sufficiency.completeness = 0.6
        report.information_density.signal_to_noise = 0.6
        report.structural_clarity.section_coherence = 0.6
        report.entity_density.entity_consistency = 0.6
        report.chunking_quality.retrieval_quality = 0.6

        report.compute_overall_score()
        assert report.quality_level == QualityLevel.ACCEPTABLE
        assert 0.5 <= report.overall_score < 0.7

    def test_quality_level_poor(self):
        """Test POOR quality level (0.3-0.5)."""
        report = DocumentQualityReport(
            document_id="doc",
            document_name="test.pdf"
        )
        report.contextual_relevancy.f1_score = 0.4
        report.context_sufficiency.completeness = 0.4
        report.information_density.signal_to_noise = 0.4
        report.structural_clarity.section_coherence = 0.4
        report.entity_density.entity_consistency = 0.4
        report.chunking_quality.retrieval_quality = 0.4

        report.compute_overall_score()
        assert report.quality_level == QualityLevel.POOR
        assert 0.3 <= report.overall_score < 0.5

    def test_quality_level_critical(self):
        """Test CRITICAL quality level (< 0.3)."""
        report = DocumentQualityReport(
            document_id="doc",
            document_name="test.pdf"
        )
        report.contextual_relevancy.f1_score = 0.2
        report.context_sufficiency.completeness = 0.2
        report.information_density.signal_to_noise = 0.2
        report.structural_clarity.section_coherence = 0.2
        report.entity_density.entity_consistency = 0.2
        report.chunking_quality.retrieval_quality = 0.2

        report.compute_overall_score()
        assert report.quality_level == QualityLevel.CRITICAL
        assert report.overall_score < 0.3

    def test_generate_recommendations_low_relevancy(self, low_quality_report):
        """Test recommendations for low contextual relevancy."""
        recommendations = low_quality_report.generate_recommendations()

        # Should have recommendations about precision/recall
        precision_recs = [r for r in recommendations if "boundaries" in r.lower() or "chunk" in r.lower()]
        assert len(precision_recs) > 0

    def test_generate_recommendations_low_density(self, low_quality_report):
        """Test recommendations for low information density."""
        recommendations = low_quality_report.generate_recommendations()

        # Should have recommendations about redundancy
        density_recs = [r for r in recommendations if "redundancy" in r.lower() or "density" in r.lower()]
        assert len(density_recs) > 0

    def test_generate_recommendations_structure_issues(self, low_quality_report):
        """Test recommendations for structure issues."""
        recommendations = low_quality_report.generate_recommendations()

        # Should have recommendations about heading hierarchy
        structure_recs = [r for r in recommendations if "hierarchy" in r.lower() or "orphan" in r.lower()]
        assert len(structure_recs) > 0

    def test_generate_recommendations_missing_topics(self, low_quality_report):
        """Test recommendations for missing topics."""
        recommendations = low_quality_report.generate_recommendations()

        # Should mention missing topics
        topic_recs = [r for r in recommendations if "missing" in r.lower() and "topic" in r.lower()]
        assert len(topic_recs) > 0

    def test_to_dict_serialization(self, sample_report):
        """Test full JSON serialization."""
        sample_report.contextual_relevancy.f1_score = 0.75
        sample_report.chunk_count = 10
        sample_report.total_tokens = 5000
        sample_report.processing_time_ms = 150
        sample_report.compute_overall_score()

        result = sample_report.to_dict()

        # Check top-level fields
        assert result["document_id"] == "doc-123"
        assert result["document_name"] == "test.pdf"
        assert "assessed_at" in result
        assert "overall_score" in result
        assert "quality_level" in result

        # Check scores structure
        assert "scores" in result
        assert "contextual_relevancy" in result["scores"]
        assert "context_sufficiency" in result["scores"]
        assert "information_density" in result["scores"]
        assert "structural_clarity" in result["scores"]
        assert "entity_density" in result["scores"]
        assert "chunking_quality" in result["scores"]

        # Check metadata
        assert result["metadata"]["chunk_count"] == 10
        assert result["metadata"]["total_tokens"] == 5000
        assert result["metadata"]["processing_time_ms"] == 150

    def test_priority_score_ranking(self, sample_report):
        """Test recommendation priority scoring."""
        # Test priority keywords
        assert sample_report._priority_score("missing topics") == 0.9
        assert sample_report._priority_score("high redundancy detected") == 0.8
        assert sample_report._priority_score("fix hierarchy") == 0.7
        assert sample_report._priority_score("improve boundary") == 0.8
        assert sample_report._priority_score("ambiguous entities") == 0.6
        assert sample_report._priority_score("low extraction rate") == 0.5
        assert sample_report._priority_score("other issue") == 0.5


class TestOntologyQualityReport:
    """Tests for OntologyQualityReport."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample ontology report."""
        return OntologyQualityReport(
            assessment_id="assess-123",
            ontology_name="default"
        )

    @pytest.fixture
    def high_quality_report(self):
        """Create a high quality ontology report."""
        report = OntologyQualityReport(
            assessment_id="assess-high",
            ontology_name="production"
        )
        report.coverage.coverage_ratio = 0.95
        report.compliance.compliance_ratio = 0.92
        report.taxonomy.coherence_ratio = 0.90
        report.consistency.consistency_ratio = 0.93
        report.normalization.normalization_rate = 0.88
        report.cross_reference.validity_ratio = 0.91
        report.interoperability.exchange_readiness = 0.85
        return report

    @pytest.fixture
    def low_quality_report(self):
        """Create a low quality ontology report."""
        report = OntologyQualityReport(
            assessment_id="assess-low",
            ontology_name="development"
        )
        report.coverage.coverage_ratio = 0.3
        report.coverage.unmapped_entities = 50
        report.coverage.unmapped_types = ["Type1", "Type2", "Type3"]
        report.compliance.compliance_ratio = 0.4
        report.compliance.non_compliant = 20
        report.taxonomy.coherence_ratio = 0.5
        report.taxonomy.invalid_relationships = 15
        report.taxonomy.orphan_nodes = 10
        report.taxonomy.circular_references = ["cycle1", "cycle2"]
        report.consistency.consistency_ratio = 0.4
        report.consistency.inconsistent_types = 8
        report.normalization.normalization_rate = 0.3
        report.normalization.total_names = 100
        report.normalization.normalized_names = 30
        report.normalization.deduplication_candidates = 12
        report.cross_reference.validity_ratio = 0.5
        report.cross_reference.invalid_references = 25
        report.interoperability.exchange_readiness = 0.2
        report.interoperability.schema_org_coverage = 0.3
        return report

    def test_default_values(self, sample_report):
        """Test default initialization values."""
        assert sample_report.assessment_id == "assess-123"
        assert sample_report.ontology_name == "default"
        assert sample_report.overall_score == 0.0
        assert sample_report.quality_level == OntologyQualityLevel.ACCEPTABLE
        assert sample_report.recommendations == []
        assert sample_report.critical_issues == []

    def test_compute_overall_score_default_weights(self, high_quality_report):
        """Test overall score computation with default weights."""
        score = high_quality_report.compute_overall_score()

        # Default weights sum to 1.0
        expected = (
            0.95 * 0.25 +  # coverage
            0.92 * 0.20 +  # compliance
            0.90 * 0.15 +  # taxonomy
            0.93 * 0.15 +  # consistency
            0.88 * 0.10 +  # normalization
            0.91 * 0.10 +  # cross_reference
            0.85 * 0.05    # interoperability
        )
        assert abs(score - expected) < 0.001

    def test_ontology_quality_levels(self, high_quality_report):
        """Test ontology quality level assignment."""
        score = high_quality_report.compute_overall_score()
        assert score >= 0.9
        assert high_quality_report.quality_level == OntologyQualityLevel.EXCELLENT

    def test_ontology_quality_level_good(self):
        """Test GOOD quality level."""
        report = OntologyQualityReport(
            assessment_id="test",
            ontology_name="test"
        )
        report.coverage.coverage_ratio = 0.8
        report.compliance.compliance_ratio = 0.8
        report.taxonomy.coherence_ratio = 0.8
        report.consistency.consistency_ratio = 0.8
        report.normalization.normalization_rate = 0.8
        report.cross_reference.validity_ratio = 0.8
        report.interoperability.exchange_readiness = 0.8

        report.compute_overall_score()
        assert report.quality_level == OntologyQualityLevel.GOOD
        assert 0.7 <= report.overall_score < 0.9

    def test_ontology_generate_recommendations_low_coverage(self, low_quality_report):
        """Test recommendations for low coverage."""
        recommendations = low_quality_report.generate_recommendations()

        # Should have coverage recommendations
        coverage_recs = [r for r in recommendations if "coverage" in r.lower() or "unmapped" in r.lower() or "mapping" in r.lower()]
        assert len(coverage_recs) > 0

    def test_ontology_generate_recommendations_circular_refs(self, low_quality_report):
        """Test critical issues for circular references."""
        low_quality_report.generate_recommendations()

        # Circular references should be critical
        circular_issues = [i for i in low_quality_report.critical_issues if "circular" in i.lower()]
        assert len(circular_issues) > 0

    def test_ontology_generate_recommendations_orphans(self, low_quality_report):
        """Test recommendations for orphan nodes."""
        recommendations = low_quality_report.generate_recommendations()

        # Should have orphan node recommendations
        orphan_recs = [r for r in recommendations if "orphan" in r.lower()]
        assert len(orphan_recs) > 0

    def test_ontology_to_dict_serialization(self, sample_report):
        """Test full JSON serialization."""
        sample_report.coverage.coverage_ratio = 0.85
        sample_report.entity_count = 100
        sample_report.relationship_count = 200
        sample_report.class_count = 15
        sample_report.processing_time_ms = 250
        sample_report.compute_overall_score()

        result = sample_report.to_dict()

        # Check top-level fields
        assert result["assessment_id"] == "assess-123"
        assert result["ontology_name"] == "default"
        assert "assessed_at" in result
        assert "overall_score" in result
        assert "quality_level" in result

        # Check scores structure
        assert "scores" in result
        assert "coverage" in result["scores"]
        assert "compliance" in result["scores"]
        assert "taxonomy" in result["scores"]
        assert "consistency" in result["scores"]
        assert "normalization" in result["scores"]
        assert "cross_reference" in result["scores"]
        assert "interoperability" in result["scores"]

        # Check metadata
        assert result["metadata"]["entity_count"] == 100
        assert result["metadata"]["relationship_count"] == 200
        assert result["metadata"]["class_count"] == 15
        assert result["metadata"]["processing_time_ms"] == 250


class TestIndividualScoreModels:
    """Tests for individual score dataclasses."""

    def test_context_sufficiency_score_defaults(self):
        """Test ContextSufficiencyScore defaults."""
        score = ContextSufficiencyScore()
        assert score.topic_coverage == 0.0
        assert score.claim_coverage == 0.0
        assert score.completeness == 0.0
        assert score.expected_topics == []
        assert score.found_topics == []
        assert score.missing_topics == []
        assert score.information_gaps == []

    def test_information_density_score_defaults(self):
        """Test InformationDensityScore defaults."""
        score = InformationDensityScore()
        assert score.unique_facts_per_chunk == 0.0
        assert score.redundancy_ratio == 0.0
        assert score.signal_to_noise == 0.0
        assert score.chunk_densities == []
        assert score.low_density_chunks == []

    def test_structural_clarity_score_defaults(self):
        """Test StructuralClarityScore defaults."""
        score = StructuralClarityScore()
        assert score.heading_hierarchy_score == 0.0
        assert score.section_coherence == 0.0
        assert score.logical_flow == 0.0
        assert score.heading_count == 0
        assert score.max_depth == 0
        assert score.orphan_sections == 0
        assert score.hierarchy_violations == []

    def test_entity_density_score_defaults(self):
        """Test EntityDensityScore defaults."""
        score = EntityDensityScore()
        assert score.entities_per_chunk == 0.0
        assert score.entity_extraction_rate == 0.0
        assert score.relationship_density == 0.0
        assert score.entity_consistency == 0.0
        assert score.total_entities == 0
        assert score.unique_entities == 0
        assert score.ambiguous_entities == []

    def test_chunking_quality_score_defaults(self):
        """Test ChunkingQualityScore defaults."""
        score = ChunkingQualityScore()
        assert score.self_containment == 0.0
        assert score.boundary_coherence == 0.0
        assert score.context_preservation == 0.0
        assert score.size_variance == 0.0
        assert score.optimal_size_ratio == 0.0
        assert score.retrieval_quality == 0.0

    def test_ontology_coverage_score_defaults(self):
        """Test OntologyCoverageScore defaults."""
        score = OntologyCoverageScore()
        assert score.total_entities == 0
        assert score.mapped_entities == 0
        assert score.unmapped_entities == 0
        assert score.coverage_ratio == 0.0
        assert score.class_distribution == {}

    def test_schema_compliance_score_defaults(self):
        """Test SchemaComplianceScore defaults."""
        score = SchemaComplianceScore()
        assert score.total_validated == 0
        assert score.fully_compliant == 0
        assert score.partially_compliant == 0
        assert score.non_compliant == 0
        assert score.compliance_ratio == 0.0

    def test_taxonomy_coherence_score_defaults(self):
        """Test TaxonomyCoherenceScore defaults."""
        score = TaxonomyCoherenceScore()
        assert score.total_relationships == 0
        assert score.valid_relationships == 0
        assert score.invalid_relationships == 0
        assert score.coherence_ratio == 0.0
        assert score.orphan_nodes == 0
        assert score.circular_references == []

    def test_mapping_consistency_score_defaults(self):
        """Test MappingConsistencyScore defaults."""
        score = MappingConsistencyScore()
        assert score.total_types == 0
        assert score.consistent_types == 0
        assert score.inconsistent_types == 0
        assert score.consistency_ratio == 0.0
        assert score.ambiguous_mappings == {}

    def test_normalization_quality_score_defaults(self):
        """Test NormalizationQualityScore defaults."""
        score = NormalizationQualityScore()
        assert score.total_names == 0
        assert score.normalized_names == 0
        assert score.normalization_rate == 0.0
        assert score.abbreviations_expanded == 0
        assert score.unknown_abbreviations == []

    def test_cross_reference_validity_score_defaults(self):
        """Test CrossReferenceValidityScore defaults."""
        score = CrossReferenceValidityScore()
        assert score.total_references == 0
        assert score.valid_references == 0
        assert score.invalid_references == 0
        assert score.validity_ratio == 0.0
        assert score.invalid_combinations == []

    def test_interoperability_score_defaults(self):
        """Test InteroperabilityScore defaults."""
        score = InteroperabilityScore()
        assert score.schema_org_types == 0
        assert score.schema_org_properties == 0
        assert score.schema_org_coverage == 0.0
        assert score.linked_data_ready == False
        assert score.sparql_compatible == False
        assert score.rdf_exportable == False
        assert score.exchange_readiness == 0.0
