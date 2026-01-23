"""Schema.org Ontology Definitions.

This module defines the subset of Schema.org vocabulary used for annotation.
Namespace: schema
"""

class SCHEMA:
    """Schema.org Vocabulary Constants."""
    NAMESPACE = "schema"
    PREFIX = "schema:"

    # --- Classes ---
    DATASET = "Dataset"                 # Maps to odin:DataEntity
    PROPERTY = "Property"               # Maps to odin:Attribute
    ARTICLE = "Article"                 # Maps to odin:InformationAsset (Report)
    DEFINED_TERM = "DefinedTerm"        # Maps to odin:BusinessConcept
    ACTION = "Action"                   # Maps to odin:Decision / Lineage
    ORGANIZATION = "Organization"       # Maps to Domain/Org
    PERSON = "Person"                   # Maps to User/Owner
    
    # --- Properties ---
    NAME = "name"
    DESCRIPTION = "description"
    ABOUT = "about"                     # Subject matter
    AUTHOR = "author"                   # Creator/Owner
    DATE_CREATED = "dateCreated"
    DATE_MODIFIED = "dateModified"
    IS_PART_OF = "isPartOf"
