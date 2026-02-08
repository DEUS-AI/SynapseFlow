"""ODIN Medical Domain Extension.

Extends ODIN for clinical/medical entities following DIKW layers.
Maps to standard terminologies: SNOMED-CT, ICD-10, RxNorm, MeSH.

This module defines medical-specific entity types that integrate with
the core ODIN ontology while maintaining domain separation.
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class ODINMedical:
    """Medical domain vocabulary for ODIN.

    Organized by DIKW layers to align with the core ODIN architecture.
    """
    NAMESPACE = "odin:medical"
    PREFIX = "odin:medical:"

    # ========================================
    # PERCEPTION Layer - Raw clinical observations
    # ========================================
    SYMPTOM = "Symptom"              # Clinical manifestations, signs
    TEST = "Test"                    # Diagnostic tests, biomarkers
    OBSERVATION = "Observation"      # Clinical observations
    MEASUREMENT = "Measurement"      # Vital signs, lab values

    # ========================================
    # SEMANTIC Layer - Validated clinical concepts
    # ========================================
    DISEASE = "Disease"              # Medical conditions, syndromes
    CONDITION = "Condition"          # Health states, disorders
    DRUG = "Drug"                    # Medications, compounds
    TREATMENT = "Treatment"          # Therapies, procedures, interventions
    ANATOMY = "Anatomy"              # Body parts, organs, tissues

    # ========================================
    # REASONING Layer - Clinical knowledge
    # ========================================
    PATHWAY = "Pathway"              # Biological pathways, mechanisms
    GENE = "Gene"                    # Genes, genetic markers
    MECHANISM = "Mechanism"          # Pathophysiological mechanisms
    INTERACTION = "Interaction"      # Drug-drug, gene-drug interactions

    # ========================================
    # APPLICATION Layer - Clinical decisions
    # ========================================
    GUIDELINE = "Guideline"          # Clinical practice guidelines
    PROTOCOL = "Protocol"            # Treatment protocols
    STUDY = "Study"                  # Clinical trials, research studies
    ORGANIZATION = "Organization"    # Research institutions, pharma companies

    # ========================================
    # Relationship Types
    # ========================================
    TREATS = "TREATS"                # Drug/Treatment -> Disease
    CAUSES = "CAUSES"                # Entity -> Disease/Symptom
    INDICATES = "INDICATES"          # Symptom/Test -> Disease
    DIAGNOSED_BY = "DIAGNOSED_BY"    # Disease -> Test
    ASSOCIATED_WITH = "ASSOCIATED_WITH"  # Generic association
    INTERACTS_WITH = "INTERACTS_WITH"    # Drug-drug, gene-drug
    TARGETS = "TARGETS"              # Drug -> Gene/Pathway
    LOCATED_IN = "LOCATED_IN"        # Condition -> Anatomy
    STUDIED_BY = "STUDIED_BY"        # Entity -> Study
    PUBLISHED_BY = "PUBLISHED_BY"    # Study -> Organization
    CONTRAINDICATED_FOR = "CONTRAINDICATED_FOR"  # Drug -> Condition


class MedicalOntologySystem(str, Enum):
    """External ontology systems for medical concept mapping."""
    SNOMED_CT = "SNOMED-CT"
    ICD_10 = "ICD-10"
    ICD_11 = "ICD-11"
    RXNORM = "RxNorm"
    MESH = "MeSH"
    LOINC = "LOINC"
    UMLS = "UMLS"
    CUSTOM = "custom"


# ========================================
# Medical Ontology Registry
# ========================================

MEDICAL_ONTOLOGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    # PERCEPTION Layer
    "symptom": {
        "odin_class": ODINMedical.SYMPTOM,
        "layer": "PERCEPTION",
        "parent_type": "clinical_observation",
        "auto_relationships": ["INDICATES", "ASSOCIATED_WITH", "LOCATED_IN"],
        "external_systems": [MedicalOntologySystem.SNOMED_CT, MedicalOntologySystem.MESH],
        "hierarchy_path": ["clinical_observation", "symptom"],
        "confidence_threshold": 0.7,
    },
    "test": {
        "odin_class": ODINMedical.TEST,
        "layer": "PERCEPTION",
        "parent_type": "clinical_observation",
        "auto_relationships": ["INDICATES", "DIAGNOSED_BY"],
        "external_systems": [MedicalOntologySystem.LOINC, MedicalOntologySystem.SNOMED_CT],
        "hierarchy_path": ["clinical_observation", "test"],
        "confidence_threshold": 0.7,
    },
    "observation": {
        "odin_class": ODINMedical.OBSERVATION,
        "layer": "PERCEPTION",
        "parent_type": "clinical_observation",
        "auto_relationships": ["ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.SNOMED_CT],
        "hierarchy_path": ["clinical_observation", "observation"],
        "confidence_threshold": 0.6,
    },
    "measurement": {
        "odin_class": ODINMedical.MEASUREMENT,
        "layer": "PERCEPTION",
        "parent_type": "clinical_observation",
        "auto_relationships": ["INDICATES", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.LOINC],
        "hierarchy_path": ["clinical_observation", "measurement"],
        "confidence_threshold": 0.7,
    },

    # SEMANTIC Layer
    "disease": {
        "odin_class": ODINMedical.DISEASE,
        "layer": "SEMANTIC",
        "parent_type": "clinical_concept",
        "auto_relationships": ["TREATED_BY", "CAUSES", "DIAGNOSED_BY", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.ICD_10, MedicalOntologySystem.SNOMED_CT],
        "hierarchy_path": ["clinical_concept", "disease"],
        "confidence_threshold": 0.85,
    },
    "condition": {
        "odin_class": ODINMedical.CONDITION,
        "layer": "SEMANTIC",
        "parent_type": "clinical_concept",
        "auto_relationships": ["TREATED_BY", "ASSOCIATED_WITH", "LOCATED_IN"],
        "external_systems": [MedicalOntologySystem.ICD_10, MedicalOntologySystem.SNOMED_CT],
        "hierarchy_path": ["clinical_concept", "condition"],
        "confidence_threshold": 0.85,
    },
    "drug": {
        "odin_class": ODINMedical.DRUG,
        "layer": "SEMANTIC",
        "parent_type": "therapeutic_agent",
        "auto_relationships": ["TREATS", "INTERACTS_WITH", "TARGETS", "CONTRAINDICATED_FOR"],
        "external_systems": [MedicalOntologySystem.RXNORM, MedicalOntologySystem.MESH],
        "hierarchy_path": ["therapeutic_agent", "drug"],
        "confidence_threshold": 0.85,
    },
    "treatment": {
        "odin_class": ODINMedical.TREATMENT,
        "layer": "SEMANTIC",
        "parent_type": "therapeutic_agent",
        "auto_relationships": ["TREATS", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.SNOMED_CT, MedicalOntologySystem.MESH],
        "hierarchy_path": ["therapeutic_agent", "treatment"],
        "confidence_threshold": 0.85,
    },
    "anatomy": {
        "odin_class": ODINMedical.ANATOMY,
        "layer": "SEMANTIC",
        "parent_type": "clinical_concept",
        "auto_relationships": ["LOCATED_IN", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.SNOMED_CT],
        "hierarchy_path": ["clinical_concept", "anatomy"],
        "confidence_threshold": 0.9,
    },

    # REASONING Layer
    "pathway": {
        "odin_class": ODINMedical.PATHWAY,
        "layer": "REASONING",
        "parent_type": "biological_mechanism",
        "auto_relationships": ["ASSOCIATED_WITH", "TARGETS"],
        "external_systems": [MedicalOntologySystem.MESH],
        "hierarchy_path": ["biological_mechanism", "pathway"],
        "confidence_threshold": 0.9,
    },
    "gene": {
        "odin_class": ODINMedical.GENE,
        "layer": "REASONING",
        "parent_type": "biological_mechanism",
        "auto_relationships": ["ASSOCIATED_WITH", "TARGETS", "CAUSES"],
        "external_systems": [MedicalOntologySystem.MESH, MedicalOntologySystem.UMLS],
        "hierarchy_path": ["biological_mechanism", "gene"],
        "confidence_threshold": 0.9,
    },
    "mechanism": {
        "odin_class": ODINMedical.MECHANISM,
        "layer": "REASONING",
        "parent_type": "biological_mechanism",
        "auto_relationships": ["CAUSES", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.MESH],
        "hierarchy_path": ["biological_mechanism", "mechanism"],
        "confidence_threshold": 0.9,
    },
    "interaction": {
        "odin_class": ODINMedical.INTERACTION,
        "layer": "REASONING",
        "parent_type": "biological_mechanism",
        "auto_relationships": ["INTERACTS_WITH"],
        "external_systems": [MedicalOntologySystem.RXNORM],
        "hierarchy_path": ["biological_mechanism", "interaction"],
        "confidence_threshold": 0.85,
    },

    # APPLICATION Layer
    "guideline": {
        "odin_class": ODINMedical.GUIDELINE,
        "layer": "APPLICATION",
        "parent_type": "clinical_knowledge",
        "auto_relationships": ["ASSOCIATED_WITH", "PUBLISHED_BY"],
        "external_systems": [MedicalOntologySystem.CUSTOM],
        "hierarchy_path": ["clinical_knowledge", "guideline"],
        "confidence_threshold": 0.95,
    },
    "protocol": {
        "odin_class": ODINMedical.PROTOCOL,
        "layer": "APPLICATION",
        "parent_type": "clinical_knowledge",
        "auto_relationships": ["TREATS", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.CUSTOM],
        "hierarchy_path": ["clinical_knowledge", "protocol"],
        "confidence_threshold": 0.95,
    },
    "study": {
        "odin_class": ODINMedical.STUDY,
        "layer": "APPLICATION",
        "parent_type": "clinical_knowledge",
        "auto_relationships": ["STUDIED_BY", "PUBLISHED_BY", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.MESH],
        "hierarchy_path": ["clinical_knowledge", "study"],
        "confidence_threshold": 0.9,
    },
    "organization": {
        "odin_class": ODINMedical.ORGANIZATION,
        "layer": "APPLICATION",
        "parent_type": "clinical_knowledge",
        "auto_relationships": ["PUBLISHED_BY", "ASSOCIATED_WITH"],
        "external_systems": [MedicalOntologySystem.CUSTOM],
        "hierarchy_path": ["clinical_knowledge", "organization"],
        "confidence_threshold": 0.85,
    },
}


# ========================================
# Type Aliases for Normalization
# ========================================

MEDICAL_TYPE_ALIASES: Dict[str, str] = {
    # Disease aliases
    "diseases": "disease",
    "medical condition": "disease",
    "medical_condition": "disease",
    "disorder": "disease",
    "syndrome": "disease",
    "illness": "disease",

    # Condition aliases
    "conditions": "condition",
    "health state": "condition",
    "health_state": "condition",

    # Drug aliases
    "drugs": "drug",
    "medication": "drug",
    "medications": "drug",
    "compound": "drug",
    "pharmaceutical": "drug",
    "medicine": "drug",

    # Treatment aliases
    "treatments": "treatment",
    "therapy": "treatment",
    "procedure": "treatment",
    "intervention": "treatment",

    # Symptom aliases
    "symptoms": "symptom",
    "sign": "symptom",
    "signs": "symptom",
    "manifestation": "symptom",
    "clinical sign": "symptom",

    # Test aliases
    "tests": "test",
    "diagnostic test": "test",
    "diagnostic_test": "test",
    "biomarker": "test",
    "lab test": "test",
    "laboratory test": "test",

    # Gene aliases
    "genes": "gene",
    "genetic marker": "gene",
    "genetic_marker": "gene",

    # Pathway aliases
    "pathways": "pathway",
    "biological pathway": "pathway",
    "biological_pathway": "pathway",

    # Study aliases
    "studies": "study",
    "clinical trial": "study",
    "clinical_trial": "study",
    "research study": "study",
    "research_study": "study",
    "trial": "study",

    # Organization aliases
    "organizations": "organization",
    "institution": "organization",
    "research institution": "organization",
    "research_institution": "organization",
    "pharma company": "organization",
    "pharmaceutical company": "organization",
    "university": "organization",
    "hospital": "organization",
}


def resolve_medical_type(raw_type: str) -> str:
    """Normalize and resolve a medical entity type to its canonical form.

    Args:
        raw_type: Raw entity type string (e.g., "Medical Condition", "drugs")

    Returns:
        Canonical type string (e.g., "disease", "drug")
    """
    normalized = raw_type.lower().strip().replace("-", "_").replace(" ", "_")
    return MEDICAL_TYPE_ALIASES.get(normalized, normalized)


def get_medical_ontology_config(entity_type: str) -> Optional[Dict[str, Any]]:
    """Get ontology configuration for a medical entity type.

    Args:
        entity_type: Entity type (raw or canonical)

    Returns:
        Ontology configuration dict or None if not a medical type
    """
    resolved = resolve_medical_type(entity_type)
    return MEDICAL_ONTOLOGY_REGISTRY.get(resolved)


def is_medical_type(entity_type: str) -> bool:
    """Check if an entity type is a known medical type.

    Args:
        entity_type: Entity type to check

    Returns:
        True if it's a recognized medical entity type
    """
    resolved = resolve_medical_type(entity_type)
    return resolved in MEDICAL_ONTOLOGY_REGISTRY


def get_medical_relationship_types() -> List[str]:
    """Get all valid medical relationship types.

    Returns:
        List of relationship type strings
    """
    return [
        ODINMedical.TREATS,
        ODINMedical.CAUSES,
        ODINMedical.INDICATES,
        ODINMedical.DIAGNOSED_BY,
        ODINMedical.ASSOCIATED_WITH,
        ODINMedical.INTERACTS_WITH,
        ODINMedical.TARGETS,
        ODINMedical.LOCATED_IN,
        ODINMedical.STUDIED_BY,
        ODINMedical.PUBLISHED_BY,
        ODINMedical.CONTRAINDICATED_FOR,
    ]


def get_layer_for_medical_type(entity_type: str) -> Optional[str]:
    """Get the DIKW layer for a medical entity type.

    Args:
        entity_type: Medical entity type

    Returns:
        Layer name (PERCEPTION, SEMANTIC, REASONING, APPLICATION) or None
    """
    config = get_medical_ontology_config(entity_type)
    return config.get("layer") if config else None
