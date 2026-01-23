"""ODIN (Open Data Intelligence Network) Ontology Definitions.

This module defines the vocabulary for the custom DIKW-aligned ontology.
Namespace: odin
"""

class ODIN:
    """ODIN Vocabulary Constants."""
    NAMESPACE = "odin"
    PREFIX = "odin:"

    # --- Classes (Nodes) ---
    
    # Perception Layer (Data)
    DATA_ENTITY = "DataEntity"          # Represents raw data (Table, File)
    ATTRIBUTE = "Attribute"             # Represents a field/column
    
    # Semantic Layer (Information)
    INFORMATION_ASSET = "InformationAsset" # Contextualized data (Report, Dashboard)
    DOMAIN = "Domain"                   # Business Domain (Sales, Finance)
    
    # Reasoning Layer (Knowledge)
    BUSINESS_CONCEPT = "BusinessConcept"   # Abstract concept (Customer, Churn)
    DATA_QUALITY_RULE = "DataQualityRule"  # Rule for validation
    DATA_QUALITY_SCORE = "DataQualityScore" # Result of validation
    
    # Application Layer (Wisdom)
    DECISION = "Decision"               # Actionable outcome
    USAGE_STATS = "UsageStats"          # Usage metrics
    
    # --- Properties (Edges/Attributes) ---
    
    # Core
    HAS_NAME = "name"
    HAS_DESCRIPTION = "description"
    HAS_ORIGIN = "origin"
    
    # Relationships
    HAS_ATTRIBUTE = "hasAttribute"      # DataEntity -> Attribute
    BELONGS_TO_DOMAIN = "belongsToDomain" # * -> Domain
    DERIVED_FROM = "derivedFrom"        # InformationAsset -> DataEntity
    REPRESENTS = "represents"           # DataEntity -> BusinessConcept
    HAS_QUALITY_SCORE = "hasQualityScore" # DataEntity -> DataQualityScore
    TRANSFORMS_INTO = "transformsInto"  # Lineage: Table -> Table
    
    # Metadata
    CONFIDENCE_SCORE = "confidenceScore"
    STATUS = "status"                   # e.g., 'active', 'hypothetical'
