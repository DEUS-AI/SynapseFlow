"""Tests for ODINMedical type resolution and ODIN_SCHEMAS coverage.

Covers:
- resolve_medical_type() with all types including food_component, genus, model organism
- Biomarker no longer resolves to test
- All medical types have entries in ODIN_SCHEMAS
- FoodComponent schema and Schema.org mapping
"""

import pytest
from domain.ontologies.odin_medical import (
    ODINMedical,
    resolve_medical_type,
    is_medical_type,
    get_medical_ontology_config,
    get_layer_for_medical_type,
    MEDICAL_ONTOLOGY_REGISTRY,
)
from domain.ontology_quality_models import ODIN_SCHEMAS, SCHEMA_ORG_MAPPINGS


# ========================================
# 6.1 - resolve_medical_type with new types
# ========================================


class TestResolveMedicalType:
    """Test resolve_medical_type() with new and existing types."""

    def test_protein_resolves(self):
        assert resolve_medical_type("Protein") == "protein"

    def test_protein_alias_enzyme(self):
        assert resolve_medical_type("enzyme") == "protein"

    def test_protein_plural(self):
        assert resolve_medical_type("proteins") == "protein"

    def test_biomarker_resolves_to_biomarker(self):
        """Biomarker should resolve to 'biomarker', NOT 'test'."""
        assert resolve_medical_type("Biomarker") == "biomarker"

    def test_biomarker_lowercase(self):
        assert resolve_medical_type("biomarker") == "biomarker"

    def test_cell_type_resolves(self):
        assert resolve_medical_type("CellType") == "cell_type"

    def test_cell_type_alias(self):
        assert resolve_medical_type("cell type") == "cell_type"

    def test_cell_type_alias_cell_types(self):
        assert resolve_medical_type("cell types") == "cell_type"

    def test_organism_resolves(self):
        assert resolve_medical_type("Organism") == "organism"

    def test_organism_alias_species(self):
        assert resolve_medical_type("species") == "organism"

    def test_organism_alias_pathogen(self):
        assert resolve_medical_type("pathogen") == "organism"

    def test_organism_alias_bacteria(self):
        assert resolve_medical_type("bacteria") == "organism"

    def test_virus_resolves(self):
        assert resolve_medical_type("Virus") == "virus"

    def test_virus_alias_viruses(self):
        assert resolve_medical_type("viruses") == "virus"

    def test_existing_disease_still_works(self):
        assert resolve_medical_type("Disease") == "disease"

    def test_existing_drug_still_works(self):
        assert resolve_medical_type("Drug") == "drug"

    def test_existing_symptom_still_works(self):
        assert resolve_medical_type("Symptom") == "symptom"

    def test_existing_treatment_still_works(self):
        assert resolve_medical_type("Treatment") == "treatment"

    def test_existing_gene_still_works(self):
        assert resolve_medical_type("Gene") == "gene"

    # --- New type alias tests ---

    def test_genus_resolves_to_organism(self):
        assert resolve_medical_type("Genus") == "organism"

    def test_model_organism_resolves_to_organism(self):
        assert resolve_medical_type("Model Organism") == "organism"

    def test_food_component_resolves(self):
        assert resolve_medical_type("Food Component") == "food_component"

    def test_nutrient_resolves_to_food_component(self):
        assert resolve_medical_type("nutrient") == "food_component"

    def test_vitamin_resolves_to_food_component(self):
        assert resolve_medical_type("Vitamin") == "food_component"

    # --- Cytokine and Chemical alias tests (kg-audit-remediation) ---

    def test_cytokine_resolves_to_protein(self):
        assert resolve_medical_type("Cytokine") == "protein"

    def test_cytokines_resolves_to_protein(self):
        assert resolve_medical_type("cytokines") == "protein"

    def test_chemical_resolves_to_drug(self):
        assert resolve_medical_type("Chemical") == "drug"

    def test_chemicals_resolves_to_drug(self):
        assert resolve_medical_type("chemicals") == "drug"


class TestIsMedicalType:
    """Test is_medical_type() recognizes new types."""

    def test_protein_is_medical(self):
        assert is_medical_type("protein") is True

    def test_biomarker_is_medical(self):
        assert is_medical_type("biomarker") is True

    def test_cell_type_is_medical(self):
        assert is_medical_type("cell_type") is True

    def test_organism_is_medical(self):
        assert is_medical_type("organism") is True

    def test_virus_is_medical(self):
        assert is_medical_type("virus") is True

    def test_food_component_is_medical(self):
        assert is_medical_type("food_component") is True

    def test_unknown_is_not_medical(self):
        assert is_medical_type("Unknown") is False


class TestGetMedicalOntologyConfig:
    """Test get_medical_ontology_config() for new types."""

    def test_protein_has_config(self):
        config = get_medical_ontology_config("protein")
        assert config is not None
        assert "odin_class" in config
        assert "layer" in config
        assert "auto_relationships" in config

    def test_biomarker_has_config(self):
        config = get_medical_ontology_config("biomarker")
        assert config is not None
        assert config["layer"] == "PERCEPTION"

    def test_organism_has_config(self):
        config = get_medical_ontology_config("organism")
        assert config is not None

    def test_virus_has_config(self):
        config = get_medical_ontology_config("virus")
        assert config is not None

    def test_cell_type_has_config(self):
        config = get_medical_ontology_config("cell_type")
        assert config is not None

    def test_food_component_has_config(self):
        config = get_medical_ontology_config("food_component")
        assert config is not None
        assert config["layer"] == "SEMANTIC"
        assert "ASSOCIATED_WITH" in config["auto_relationships"]
        assert "INTERACTS_WITH" in config["auto_relationships"]

    def test_food_component_layer(self):
        assert get_layer_for_medical_type("food_component") == "SEMANTIC"


# ========================================
# All medical types have ODIN_SCHEMAS entries
# ========================================


class TestOdinSchemaCoverage:
    """Verify all medical types have entries in ODIN_SCHEMAS."""

    # All type constants from ODINMedical
    MEDICAL_TYPES = [
        ODINMedical.SYMPTOM,
        ODINMedical.TEST,
        ODINMedical.BIOMARKER,
        ODINMedical.OBSERVATION,
        ODINMedical.MEASUREMENT,
        ODINMedical.DISEASE,
        ODINMedical.CONDITION,
        ODINMedical.DRUG,
        ODINMedical.TREATMENT,
        ODINMedical.ANATOMY,
        ODINMedical.PROTEIN,
        ODINMedical.ORGANISM,
        ODINMedical.VIRUS,
        ODINMedical.CELL_TYPE,
        ODINMedical.FOOD_COMPONENT,
        ODINMedical.PATHWAY,
        ODINMedical.GENE,
        ODINMedical.MECHANISM,
        ODINMedical.INTERACTION,
        ODINMedical.GUIDELINE,
        ODINMedical.PROTOCOL,
        ODINMedical.STUDY,
        ODINMedical.ORGANIZATION,
    ]

    @pytest.mark.parametrize("type_name", MEDICAL_TYPES)
    def test_type_has_schema(self, type_name):
        """Each medical type must have an OntologyClassSchema in ODIN_SCHEMAS."""
        assert type_name in ODIN_SCHEMAS, f"{type_name} missing from ODIN_SCHEMAS"

    @pytest.mark.parametrize("type_name", MEDICAL_TYPES)
    def test_schema_has_required_properties(self, type_name):
        """Each schema must define required_properties with at least name and id."""
        schema = ODIN_SCHEMAS[type_name]
        assert "name" in schema.required_properties
        assert "id" in schema.required_properties

    @pytest.mark.parametrize("type_name", MEDICAL_TYPES)
    def test_schema_has_registry_entry(self, type_name):
        """Each type in ODIN_SCHEMAS should also be in MEDICAL_ONTOLOGY_REGISTRY."""
        canonical = type_name.lower()
        # Handle CamelCase -> snake_case
        if type_name == "CellType":
            canonical = "cell_type"
        elif type_name == "FoodComponent":
            canonical = "food_component"
        assert canonical in MEDICAL_ONTOLOGY_REGISTRY, (
            f"{type_name} (canonical: {canonical}) missing from MEDICAL_ONTOLOGY_REGISTRY"
        )

    def test_schema_org_mappings_exist(self):
        """Schema.org mappings should exist for key medical types."""
        expected = ["Disease", "Drug", "Symptom", "Treatment", "Study", "Organization", "Gene"]
        for type_name in expected:
            assert type_name in SCHEMA_ORG_MAPPINGS, (
                f"{type_name} missing from SCHEMA_ORG_MAPPINGS"
            )

    def test_food_component_has_schema(self):
        """FoodComponent must have an OntologyClassSchema in ODIN_SCHEMAS."""
        assert "FoodComponent" in ODIN_SCHEMAS
        schema = ODIN_SCHEMAS["FoodComponent"]
        assert schema.namespace == "odin:medical"
        assert "name" in schema.required_properties
        assert "id" in schema.required_properties
        assert "ASSOCIATED_WITH" in schema.allowed_relationships
        assert "INTERACTS_WITH" in schema.allowed_relationships

    def test_food_component_schema_org_mapping(self):
        """FoodComponent must map to 'Thing' in Schema.org."""
        assert SCHEMA_ORG_MAPPINGS["FoodComponent"] == "Thing"
