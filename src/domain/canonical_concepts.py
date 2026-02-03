"""Canonical Concept Models.

This module defines the domain models for managing canonical business concepts
and their variations. It supports:
- Canonical concept registry
- Alias and variation tracking
- Concept hierarchies
- Version control
- Confidence scoring
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ConceptStatus(str, Enum):
    """Status of a canonical concept."""
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    MERGED = "MERGED"
    PROPOSED = "PROPOSED"


class ConceptConfidenceSource(str, Enum):
    """Source of confidence score."""
    USER_DEFINED = "user_defined"
    AUTOMATED_EXTRACTION = "automated_extraction"
    LLM_INFERENCE = "llm_inference"
    VALIDATION_FEEDBACK = "validation_feedback"
    EXPERT_REVIEW = "expert_review"


class ConceptAlias(BaseModel):
    """Represents an alias or variation of a canonical concept."""
    alias: str = Field(..., description="Alias text")
    normalized_form: str = Field(..., description="Normalized form of the alias")
    source: str = Field(..., description="Source of the alias (document, user, system)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in alias mapping")
    usage_count: int = Field(default=1, description="Number of times this alias was encountered")
    first_seen: datetime = Field(default_factory=datetime.now, description="When alias was first recorded")
    last_seen: datetime = Field(default_factory=datetime.now, description="When alias was last seen")


class ConceptRelationship(BaseModel):
    """Relationship between concepts."""
    related_concept_id: str = Field(..., description="ID of related concept")
    relationship_type: str = Field(..., description="Type of relationship (parent, child, related)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in relationship")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional relationship metadata")


class CanonicalConcept(BaseModel):
    """
    Canonical representation of a business concept.

    This model maintains the authoritative definition of a concept,
    tracking all variations, aliases, and relationships.
    """

    canonical_id: str = Field(..., description="Unique identifier for the canonical concept")
    canonical_name: str = Field(..., description="Canonical name in normalized form")
    display_name: str = Field(..., description="Human-readable display name")

    # Concept metadata
    description: Optional[str] = Field(None, description="Detailed description of the concept")
    domain: str = Field(..., description="Business domain this concept belongs to")
    category: Optional[str] = Field(None, description="Category or type of concept")

    # Aliases and variations
    aliases: List[ConceptAlias] = Field(default_factory=list, description="List of known aliases")

    # Hierarchical relationships
    parent_concept_id: Optional[str] = Field(None, description="ID of parent concept in hierarchy")
    child_concept_ids: List[str] = Field(default_factory=list, description="IDs of child concepts")

    # Related concepts
    related_concepts: List[ConceptRelationship] = Field(
        default_factory=list,
        description="Related concepts and relationship types"
    )

    # Confidence and status
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in this concept definition"
    )
    confidence_source: ConceptConfidenceSource = Field(
        default=ConceptConfidenceSource.USER_DEFINED,
        description="Source of confidence score"
    )
    status: ConceptStatus = Field(default=ConceptStatus.ACTIVE, description="Current status")

    # Provenance
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    created_by: str = Field(default="system", description="Creator (user or system)")
    last_modified: datetime = Field(default_factory=datetime.now, description="Last modification timestamp")
    modified_by: str = Field(default="system", description="Last modifier")

    # Version control
    version: int = Field(default=1, description="Version number")
    previous_version_id: Optional[str] = Field(None, description="ID of previous version if versioned")

    # Usage statistics
    usage_count: int = Field(default=0, description="Number of times concept is referenced in graphs")
    last_used: Optional[datetime] = Field(None, description="Last time concept was used")

    # Additional properties
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional custom properties")

    model_config = {
        "json_schema_extra": {
            "example": {
                "canonical_id": "concept:customer",
                "canonical_name": "customer",
                "display_name": "Customer",
                "description": "Individual or organization that purchases products or services",
                "domain": "sales",
                "category": "entity",
                "aliases": [
                    {
                        "alias": "Client",
                        "normalized_form": "customer",
                        "source": "sales_dda.md",
                        "confidence": 0.95,
                        "usage_count": 15
                    },
                    {
                        "alias": "Cust",
                        "normalized_form": "customer",
                        "source": "abbreviation_expansion",
                        "confidence": 1.0,
                        "usage_count": 8
                    }
                ],
                "parent_concept_id": "concept:party",
                "child_concept_ids": ["concept:retail_customer", "concept:wholesale_customer"],
                "confidence": 0.98,
                "confidence_source": "expert_review",
                "status": "ACTIVE",
                "version": 2
            }
        }
    }

    def add_alias(self, alias: str, normalized_form: str, source: str, confidence: float = 1.0):
        """Add a new alias to this concept."""
        # Check if exact alias already exists (match by alias string, not normalized form)
        for existing_alias in self.aliases:
            if existing_alias.alias.lower() == alias.lower():
                # Update usage count and last seen
                existing_alias.usage_count += 1
                existing_alias.last_seen = datetime.now()
                return

        # Add new alias
        self.aliases.append(ConceptAlias(
            alias=alias,
            normalized_form=normalized_form,
            source=source,
            confidence=confidence,
            usage_count=1
        ))

        self.last_modified = datetime.now()

    def get_most_common_alias(self) -> Optional[str]:
        """Get the most commonly used alias."""
        if not self.aliases:
            return None

        return max(self.aliases, key=lambda a: a.usage_count).alias

    def is_active(self) -> bool:
        """Check if concept is active."""
        return self.status == ConceptStatus.ACTIVE

    def deprecate(self, replaced_by: Optional[str] = None):
        """Mark concept as deprecated."""
        self.status = ConceptStatus.DEPRECATED
        if replaced_by:
            self.properties["replaced_by"] = replaced_by
        self.last_modified = datetime.now()

    def merge_into(self, target_concept_id: str):
        """Mark this concept as merged into another."""
        self.status = ConceptStatus.MERGED
        self.properties["merged_into"] = target_concept_id
        self.last_modified = datetime.now()


class ConceptRegistry(BaseModel):
    """
    Registry for managing canonical concepts.

    Provides lookup, search, and management capabilities for canonical concepts.
    """

    domain: str = Field(..., description="Domain this registry covers")
    concepts: Dict[str, CanonicalConcept] = Field(
        default_factory=dict,
        description="Mapping of concept_id to concept"
    )

    # Reverse index: normalized_name -> concept_id
    name_index: Dict[str, str] = Field(
        default_factory=dict,
        description="Index of normalized names to concept IDs"
    )

    # Reverse index: alias -> concept_id
    alias_index: Dict[str, str] = Field(
        default_factory=dict,
        description="Index of aliases to concept IDs"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)

    def add_concept(self, concept: CanonicalConcept) -> None:
        """Add a concept to the registry."""
        # Add to main registry
        self.concepts[concept.canonical_id] = concept

        # Update name index
        self.name_index[concept.canonical_name] = concept.canonical_id

        # Update alias index
        for alias in concept.aliases:
            self.alias_index[alias.normalized_form] = concept.canonical_id

        self.last_modified = datetime.now()

    def get_concept(self, concept_id: str) -> Optional[CanonicalConcept]:
        """Get a concept by ID."""
        return self.concepts.get(concept_id)

    def find_by_name(self, name: str) -> Optional[CanonicalConcept]:
        """Find concept by canonical name."""
        concept_id = self.name_index.get(name)
        if concept_id:
            return self.concepts.get(concept_id)
        return None

    def find_by_alias(self, alias: str) -> Optional[CanonicalConcept]:
        """Find concept by alias."""
        concept_id = self.alias_index.get(alias)
        if concept_id:
            return self.concepts.get(concept_id)
        return None

    def search_concepts(self, query: str) -> List[CanonicalConcept]:
        """Search concepts by name or alias."""
        query_lower = query.lower()
        results = []

        for concept in self.concepts.values():
            # Check canonical name
            if query_lower in concept.canonical_name.lower():
                results.append(concept)
                continue

            # Check display name
            if query_lower in concept.display_name.lower():
                results.append(concept)
                continue

            # Check aliases
            for alias in concept.aliases:
                if query_lower in alias.alias.lower():
                    results.append(concept)
                    break

        return results

    def get_active_concepts(self) -> List[CanonicalConcept]:
        """Get all active concepts."""
        return [c for c in self.concepts.values() if c.is_active()]

    def get_concept_hierarchy(self, concept_id: str) -> Dict[str, Any]:
        """Get the hierarchy tree for a concept."""
        concept = self.get_concept(concept_id)
        if not concept:
            return {}

        # Get parent chain
        parents = []
        current = concept
        while current.parent_concept_id:
            parent = self.get_concept(current.parent_concept_id)
            if parent:
                parents.insert(0, {
                    "id": parent.canonical_id,
                    "name": parent.canonical_name
                })
                current = parent
            else:
                break

        # Get children
        children = [
            {
                "id": child_id,
                "name": self.get_concept(child_id).canonical_name
            }
            for child_id in concept.child_concept_ids
            if self.get_concept(child_id)
        ]

        return {
            "concept": {
                "id": concept.canonical_id,
                "name": concept.canonical_name
            },
            "parents": parents,
            "children": children
        }

    def merge_concepts(self, source_id: str, target_id: str) -> bool:
        """
        Merge one concept into another.

        Args:
            source_id: Concept to merge from
            target_id: Concept to merge into

        Returns:
            True if merge was successful
        """
        source = self.get_concept(source_id)
        target = self.get_concept(target_id)

        if not source or not target:
            return False

        # Transfer aliases
        for alias in source.aliases:
            target.add_alias(
                alias.alias,
                alias.normalized_form,
                f"merged_from_{source_id}",
                alias.confidence
            )

        # Update usage count
        target.usage_count += source.usage_count

        # Mark source as merged
        source.merge_into(target_id)

        # Update indices
        for alias in source.aliases:
            self.alias_index[alias.normalized_form] = target_id

        self.last_modified = datetime.now()
        return True

    def export_to_json(self) -> Dict[str, Any]:
        """Export registry to JSON-serializable format."""
        return {
            "domain": self.domain,
            "concepts": [c.model_dump() for c in self.concepts.values()],
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat()
        }

    @classmethod
    def import_from_json(cls, data: Dict[str, Any]) -> 'ConceptRegistry':
        """Import registry from JSON format."""
        registry = cls(domain=data["domain"])

        for concept_data in data["concepts"]:
            concept = CanonicalConcept(**concept_data)
            registry.add_concept(concept)

        return registry
