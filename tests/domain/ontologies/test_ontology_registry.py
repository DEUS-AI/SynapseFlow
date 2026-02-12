"""Tests for the unified ontology registry.

Tests the medical ontology extension and unified registry functionality.
"""

import pytest
from domain.ontologies.registry import (
    get_ontology_config,
    is_known_type,
    resolve_entity_type,
    get_domain_for_type,
    get_layer_for_type,
    get_auto_relationships,
    get_all_types_for_layer,
    get_all_types_for_domain,
    suggest_type_mapping,
    get_registry_statistics,
    OntologyDomain,
    UNIFIED_ONTOLOGY_REGISTRY,
)
from domain.ontologies.odin_medical import (
    ODINMedical,
    MEDICAL_ONTOLOGY_REGISTRY,
    resolve_medical_type,
    get_medical_ontology_config,
    is_medical_type,
    get_medical_relationship_types,
)


class TestMedicalOntology:
    """Test the medical ontology extension."""

    def test_medical_types_are_defined(self):
        """Verify all expected medical types are in the registry."""
        expected_types = [
            "disease", "drug", "treatment", "symptom", "test",
            "gene", "pathway", "study", "organization",
        ]

        for entity_type in expected_types:
            assert entity_type in MEDICAL_ONTOLOGY_REGISTRY, f"Missing: {entity_type}"

    def test_resolve_medical_type_aliases(self):
        """Test that type aliases are resolved correctly."""
        # Disease aliases
        assert resolve_medical_type("Medical Condition") == "disease"
        assert resolve_medical_type("disorder") == "disease"
        assert resolve_medical_type("syndrome") == "disease"

        # Drug aliases
        assert resolve_medical_type("medication") == "drug"
        assert resolve_medical_type("pharmaceutical") == "drug"

        # Study aliases
        assert resolve_medical_type("clinical trial") == "study"
        assert resolve_medical_type("research study") == "study"

    def test_get_medical_ontology_config(self):
        """Test fetching ontology config for medical types."""
        config = get_medical_ontology_config("disease")

        assert config is not None
        assert config["odin_class"] == ODINMedical.DISEASE
        assert config["layer"] == "SEMANTIC"
        assert "TREATED_BY" in config["auto_relationships"]

    def test_is_medical_type(self):
        """Test medical type detection."""
        assert is_medical_type("disease") is True
        assert is_medical_type("medication") is True  # alias
        assert is_medical_type("table") is False  # data architecture type
        assert is_medical_type("unknown_xyz") is False

    def test_medical_layers(self):
        """Test that medical types are assigned to correct DIKW layers."""
        # PERCEPTION layer
        config = get_medical_ontology_config("symptom")
        assert config["layer"] == "PERCEPTION"

        config = get_medical_ontology_config("test")
        assert config["layer"] == "PERCEPTION"

        # SEMANTIC layer
        config = get_medical_ontology_config("disease")
        assert config["layer"] == "SEMANTIC"

        config = get_medical_ontology_config("drug")
        assert config["layer"] == "SEMANTIC"

        # REASONING layer
        config = get_medical_ontology_config("pathway")
        assert config["layer"] == "REASONING"

        config = get_medical_ontology_config("gene")
        assert config["layer"] == "REASONING"

        # APPLICATION layer
        config = get_medical_ontology_config("guideline")
        assert config["layer"] == "APPLICATION"

    def test_medical_relationship_types(self):
        """Test that relationship types are defined."""
        rel_types = get_medical_relationship_types()

        assert "TREATS" in rel_types
        assert "CAUSES" in rel_types
        assert "INDICATES" in rel_types
        assert "INTERACTS_WITH" in rel_types


class TestUnifiedRegistry:
    """Test the unified ontology registry."""

    def test_registry_contains_both_domains(self):
        """Verify registry contains both data and medical types."""
        # Data architecture types
        assert "table" in UNIFIED_ONTOLOGY_REGISTRY
        assert "column" in UNIFIED_ONTOLOGY_REGISTRY
        assert "domain" in UNIFIED_ONTOLOGY_REGISTRY

        # Medical types
        assert "disease" in UNIFIED_ONTOLOGY_REGISTRY
        assert "drug" in UNIFIED_ONTOLOGY_REGISTRY
        assert "symptom" in UNIFIED_ONTOLOGY_REGISTRY

    def test_get_ontology_config_data_types(self):
        """Test fetching config for data architecture types."""
        config = get_ontology_config("table")

        assert config is not None
        assert config["layer"] == "PERCEPTION"
        assert "HAS_ATTRIBUTE" in config["auto_relationships"]

    def test_get_ontology_config_medical_types(self):
        """Test fetching config for medical types."""
        config = get_ontology_config("disease")

        assert config is not None
        assert config["layer"] == "SEMANTIC"
        assert config["odin_class"] == ODINMedical.DISEASE

    def test_resolve_entity_type_unified(self):
        """Test type resolution across all domains."""
        # Data types
        assert resolve_entity_type("tables") == "table"
        assert resolve_entity_type("dataentity") == "table"

        # Medical types
        assert resolve_entity_type("medications") == "drug"
        assert resolve_entity_type("clinical trial") == "study"

    def test_is_known_type(self):
        """Test known type detection across domains."""
        # Known types
        assert is_known_type("table") is True
        assert is_known_type("disease") is True
        assert is_known_type("medication") is True  # alias

        # Unknown types
        assert is_known_type("unknown_xyz") is False

    def test_get_domain_for_type(self):
        """Test domain detection for types."""
        assert get_domain_for_type("table") == OntologyDomain.DATA_ARCHITECTURE
        assert get_domain_for_type("disease") == OntologyDomain.MEDICAL
        assert get_domain_for_type("unknown") == OntologyDomain.UNKNOWN

    def test_get_layer_for_type(self):
        """Test layer detection for types."""
        # Data architecture
        assert get_layer_for_type("table") == "PERCEPTION"
        assert get_layer_for_type("report") == "SEMANTIC"

        # Medical
        assert get_layer_for_type("symptom") == "PERCEPTION"
        assert get_layer_for_type("disease") == "SEMANTIC"
        assert get_layer_for_type("gene") == "REASONING"

    def test_get_auto_relationships(self):
        """Test relationship type retrieval."""
        rels = get_auto_relationships("disease")
        assert "TREATED_BY" in rels

        rels = get_auto_relationships("table")
        assert "HAS_ATTRIBUTE" in rels

    def test_get_all_types_for_layer(self):
        """Test retrieving types by layer."""
        perception_types = get_all_types_for_layer("PERCEPTION")
        assert "table" in perception_types
        assert "symptom" in perception_types

        semantic_types = get_all_types_for_layer("SEMANTIC")
        assert "disease" in semantic_types
        assert "report" in semantic_types

    def test_get_all_types_for_domain(self):
        """Test retrieving types by domain."""
        medical_types = get_all_types_for_domain(OntologyDomain.MEDICAL)
        assert "disease" in medical_types
        assert "drug" in medical_types
        assert "table" not in medical_types

        data_types = get_all_types_for_domain(OntologyDomain.DATA_ARCHITECTURE)
        assert "table" in data_types
        assert "disease" not in data_types

    def test_suggest_type_mapping(self):
        """Test type mapping suggestions."""
        suggestions = suggest_type_mapping("diseases")

        assert len(suggestions) > 0
        # Should suggest "disease" as top match
        assert suggestions[0]["suggested_type"] == "disease"
        assert suggestions[0]["similarity"] > 0.8

    def test_registry_statistics(self):
        """Test registry statistics function."""
        stats = get_registry_statistics()

        assert stats["total_types"] > 0
        assert stats["medical_types"] > 0
        assert stats["data_architecture_types"] > 0
        assert "PERCEPTION" in stats["types_by_layer"]
        assert "SEMANTIC" in stats["types_by_layer"]


class TestOntologyMapper:
    """Test the updated OntologyMapper."""

    def test_map_medical_entity(self):
        """Test mapping a medical entity."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()
        labels, props = mapper.map_entity("Disease", {"name": "Diabetes"})

        # Should have ODIN medical class
        assert ODINMedical.DISEASE in labels
        # Should be marked as mapped
        assert props.get("_ontology_mapped") is True
        assert props.get("_ontology_domain") == "medical"

    def test_map_data_entity(self):
        """Test mapping a data architecture entity."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()
        labels, props = mapper.map_entity("Table", {"name": "customers"})

        # Should be marked as mapped
        assert props.get("_ontology_mapped") is True
        assert props.get("_ontology_domain") == "data_architecture"

    def test_map_unknown_entity(self):
        """Test mapping an unknown entity type."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()
        labels, props = mapper.map_entity("UnknownType", {"name": "test"})

        # Should be marked as unmapped
        assert props.get("_ontology_mapped") is False
        assert props.get("_unmapped_type") == "UnknownType"

    def test_is_type_mapped(self):
        """Test type mapping check."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()

        assert mapper.is_type_mapped("disease") is True
        assert mapper.is_type_mapped("table") is True
        assert mapper.is_type_mapped("unknown_xyz") is False

    def test_get_valid_relationships(self):
        """Test getting valid relationships for a type."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()

        rels = mapper.get_valid_relationships("disease")
        assert "TREATED_BY" in rels

        rels = mapper.get_valid_relationships("drug")
        assert "TREATS" in rels

    def test_get_entity_layer(self):
        """Test getting layer for entity type."""
        from application.agents.knowledge_manager.ontology_mapper import OntologyMapper

        mapper = OntologyMapper()

        assert mapper.get_entity_layer("symptom") == "PERCEPTION"
        assert mapper.get_entity_layer("disease") == "SEMANTIC"
        assert mapper.get_entity_layer("gene") == "REASONING"
