"""Unit tests for Canonical Concept models."""

import pytest
from datetime import datetime
from domain.canonical_concepts import (
    CanonicalConcept,
    ConceptAlias,
    ConceptRelationship,
    ConceptRegistry,
    ConceptStatus,
    ConceptConfidenceSource
)


class TestConceptAlias:
    """Test ConceptAlias model."""

    def test_alias_creation(self):
        """Test creating an alias."""
        alias = ConceptAlias(
            alias="Client",
            normalized_form="customer",
            source="sales_dda.md",
            confidence=0.95
        )

        assert alias.alias == "Client"
        assert alias.normalized_form == "customer"
        assert alias.confidence == 0.95
        assert alias.usage_count == 1

    def test_alias_timestamps(self):
        """Test alias has timestamps."""
        alias = ConceptAlias(
            alias="Cust",
            normalized_form="customer",
            source="test"
        )

        assert isinstance(alias.first_seen, datetime)
        assert isinstance(alias.last_seen, datetime)


class TestCanonicalConcept:
    """Test CanonicalConcept model."""

    def test_concept_creation(self):
        """Test creating a canonical concept."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            description="Individual or organization that purchases",
            domain="sales"
        )

        assert concept.canonical_id == "concept:customer"
        assert concept.canonical_name == "customer"
        assert concept.display_name == "Customer"
        assert concept.domain == "sales"
        assert concept.status == ConceptStatus.ACTIVE

    def test_concept_defaults(self):
        """Test concept default values."""
        concept = CanonicalConcept(
            canonical_id="test",
            canonical_name="test",
            display_name="Test",
            domain="test"
        )

        assert concept.confidence == 1.0
        assert concept.status == ConceptStatus.ACTIVE
        assert concept.version == 1
        assert len(concept.aliases) == 0
        assert len(concept.child_concept_ids) == 0

    def test_add_alias_new(self):
        """Test adding a new alias."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        concept.add_alias("Client", "customer", "test_dda", 0.95)

        assert len(concept.aliases) == 1
        assert concept.aliases[0].alias == "Client"
        assert concept.aliases[0].usage_count == 1

    def test_add_alias_existing(self):
        """Test adding existing alias increments usage."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        concept.add_alias("Client", "customer", "test1", 0.95)
        initial_count = concept.aliases[0].usage_count

        # Add the SAME alias again (case-insensitive)
        concept.add_alias("client", "customer", "test2", 0.90)

        # Should increment usage, not add new alias
        assert len(concept.aliases) == 1
        assert concept.aliases[0].usage_count == initial_count + 1

    def test_get_most_common_alias(self):
        """Test getting most common alias."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        concept.add_alias("Client", "customer", "test1", 0.95)
        concept.add_alias("Cust", "customer", "test2", 0.90)
        concept.add_alias("Cust", "customer", "test3", 0.90)  # Increment usage

        most_common = concept.get_most_common_alias()

        assert most_common == "Cust"  # Used twice

    def test_get_most_common_alias_empty(self):
        """Test getting most common alias when none exist."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        assert concept.get_most_common_alias() is None

    def test_is_active(self):
        """Test checking if concept is active."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            status=ConceptStatus.ACTIVE
        )

        assert concept.is_active() is True

        concept.status = ConceptStatus.DEPRECATED
        assert concept.is_active() is False

    def test_deprecate(self):
        """Test deprecating a concept."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        concept.deprecate(replaced_by="concept:client")

        assert concept.status == ConceptStatus.DEPRECATED
        assert concept.properties["replaced_by"] == "concept:client"

    def test_merge_into(self):
        """Test marking concept as merged."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        concept.merge_into("concept:client")

        assert concept.status == ConceptStatus.MERGED
        assert concept.properties["merged_into"] == "concept:client"

    def test_hierarchical_relationships(self):
        """Test parent-child relationships."""
        parent = CanonicalConcept(
            canonical_id="concept:party",
            canonical_name="party",
            display_name="Party",
            domain="common"
        )

        child = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            parent_concept_id="concept:party"
        )

        assert child.parent_concept_id == "concept:party"

        parent.child_concept_ids.append("concept:customer")
        assert "concept:customer" in parent.child_concept_ids


class TestConceptRegistry:
    """Test ConceptRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a concept registry."""
        return ConceptRegistry(domain="sales")

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            confidence=0.98
        )
        concept.add_alias("Client", "customer", "test", 0.95)
        concept.add_alias("Cust", "customer", "test", 1.0)
        return concept

    def test_registry_creation(self, registry):
        """Test creating a registry."""
        assert registry.domain == "sales"
        assert len(registry.concepts) == 0

    def test_add_concept(self, registry, sample_concept):
        """Test adding a concept to registry."""
        registry.add_concept(sample_concept)

        assert len(registry.concepts) == 1
        assert "concept:customer" in registry.concepts

    def test_add_concept_updates_indices(self, registry, sample_concept):
        """Test adding concept updates name and alias indices."""
        registry.add_concept(sample_concept)

        # Name index
        assert "customer" in registry.name_index
        assert registry.name_index["customer"] == "concept:customer"

        # Alias index
        assert "customer" in registry.alias_index
        assert registry.alias_index["customer"] == "concept:customer"

    def test_get_concept(self, registry, sample_concept):
        """Test getting concept by ID."""
        registry.add_concept(sample_concept)

        retrieved = registry.get_concept("concept:customer")

        assert retrieved is not None
        assert retrieved.canonical_id == "concept:customer"

    def test_get_concept_not_found(self, registry):
        """Test getting non-existent concept."""
        retrieved = registry.get_concept("concept:nonexistent")
        assert retrieved is None

    def test_find_by_name(self, registry, sample_concept):
        """Test finding concept by canonical name."""
        registry.add_concept(sample_concept)

        found = registry.find_by_name("customer")

        assert found is not None
        assert found.canonical_id == "concept:customer"

    def test_find_by_name_not_found(self, registry):
        """Test finding by name when not exists."""
        found = registry.find_by_name("nonexistent")
        assert found is None

    def test_find_by_alias(self, registry, sample_concept):
        """Test finding concept by alias."""
        registry.add_concept(sample_concept)

        found = registry.find_by_alias("customer")

        assert found is not None
        assert found.canonical_id == "concept:customer"

    def test_search_concepts_by_name(self, registry):
        """Test searching concepts by name."""
        concept1 = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )
        concept2 = CanonicalConcept(
            canonical_id="concept:customer_support",
            canonical_name="customer_support",
            display_name="Customer Support",
            domain="support"
        )

        registry.add_concept(concept1)
        registry.add_concept(concept2)

        results = registry.search_concepts("customer")

        assert len(results) == 2

    def test_search_concepts_by_alias(self, registry, sample_concept):
        """Test searching concepts by alias."""
        registry.add_concept(sample_concept)

        results = registry.search_concepts("client")

        assert len(results) >= 1
        assert any(c.canonical_id == "concept:customer" for c in results)

    def test_get_active_concepts(self, registry):
        """Test getting only active concepts."""
        active = CanonicalConcept(
            canonical_id="concept:active",
            canonical_name="active",
            display_name="Active",
            domain="test",
            status=ConceptStatus.ACTIVE
        )

        deprecated = CanonicalConcept(
            canonical_id="concept:deprecated",
            canonical_name="deprecated",
            display_name="Deprecated",
            domain="test",
            status=ConceptStatus.DEPRECATED
        )

        registry.add_concept(active)
        registry.add_concept(deprecated)

        active_concepts = registry.get_active_concepts()

        assert len(active_concepts) == 1
        assert active_concepts[0].canonical_id == "concept:active"

    def test_get_concept_hierarchy(self, registry):
        """Test getting concept hierarchy."""
        parent = CanonicalConcept(
            canonical_id="concept:party",
            canonical_name="party",
            display_name="Party",
            domain="common"
        )

        child = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            parent_concept_id="concept:party"
        )

        parent.child_concept_ids.append("concept:customer")

        registry.add_concept(parent)
        registry.add_concept(child)

        hierarchy = registry.get_concept_hierarchy("concept:customer")

        assert hierarchy["concept"]["id"] == "concept:customer"
        assert len(hierarchy["parents"]) == 1
        assert hierarchy["parents"][0]["id"] == "concept:party"
        assert len(hierarchy["children"]) == 0

    def test_merge_concepts(self, registry):
        """Test merging two concepts."""
        source = CanonicalConcept(
            canonical_id="concept:client",
            canonical_name="client",
            display_name="Client",
            domain="sales"
        )
        source.add_alias("Buyer", "client", "test", 0.9)

        target = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        registry.add_concept(source)
        registry.add_concept(target)

        success = registry.merge_concepts("concept:client", "concept:customer")

        assert success is True
        assert source.status == ConceptStatus.MERGED

        # Aliases should be transferred
        # Check that alias index points to target
        found = registry.find_by_alias("client")
        assert found.canonical_id == "concept:customer"

    def test_merge_concepts_nonexistent(self, registry):
        """Test merging non-existent concepts."""
        success = registry.merge_concepts("concept:a", "concept:b")
        assert success is False

    def test_export_to_json(self, registry, sample_concept):
        """Test exporting registry to JSON."""
        registry.add_concept(sample_concept)

        data = registry.export_to_json()

        assert data["domain"] == "sales"
        assert len(data["concepts"]) == 1
        assert "created_at" in data
        assert "last_modified" in data

    def test_import_from_json(self, sample_concept):
        """Test importing registry from JSON."""
        # Create and export
        registry1 = ConceptRegistry(domain="sales")
        registry1.add_concept(sample_concept)
        data = registry1.export_to_json()

        # Import
        registry2 = ConceptRegistry.import_from_json(data)

        assert registry2.domain == "sales"
        assert len(registry2.concepts) == 1

        concept = registry2.get_concept("concept:customer")
        assert concept is not None
        assert concept.canonical_name == "customer"


class TestConceptRelationship:
    """Test ConceptRelationship model."""

    def test_relationship_creation(self):
        """Test creating a concept relationship."""
        rel = ConceptRelationship(
            related_concept_id="concept:product",
            relationship_type="purchases",
            confidence=0.9,
            metadata={"frequency": "high"}
        )

        assert rel.related_concept_id == "concept:product"
        assert rel.relationship_type == "purchases"
        assert rel.confidence == 0.9
        assert rel.metadata["frequency"] == "high"


class TestConceptStatuses:
    """Test concept status transitions."""

    def test_status_enum_values(self):
        """Test status enum values."""
        assert ConceptStatus.ACTIVE == "ACTIVE"
        assert ConceptStatus.DEPRECATED == "DEPRECATED"
        assert ConceptStatus.MERGED == "MERGED"
        assert ConceptStatus.PROPOSED == "PROPOSED"

    def test_concept_lifecycle(self):
        """Test concept status lifecycle."""
        # Start as PROPOSED
        concept = CanonicalConcept(
            canonical_id="concept:new",
            canonical_name="new_concept",
            display_name="New Concept",
            domain="test",
            status=ConceptStatus.PROPOSED
        )

        assert concept.status == ConceptStatus.PROPOSED

        # Activate
        concept.status = ConceptStatus.ACTIVE
        assert concept.is_active()

        # Deprecate
        concept.deprecate()
        assert concept.status == ConceptStatus.DEPRECATED
        assert not concept.is_active()

        # Or merge
        concept.status = ConceptStatus.ACTIVE
        concept.merge_into("concept:other")
        assert concept.status == ConceptStatus.MERGED


class TestConceptUsageTracking:
    """Test usage tracking features."""

    def test_usage_count_increment(self):
        """Test incrementing usage count."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            usage_count=0
        )

        assert concept.usage_count == 0

        concept.usage_count += 1
        assert concept.usage_count == 1

    def test_last_used_tracking(self):
        """Test tracking last used time."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales"
        )

        assert concept.last_used is None

        concept.last_used = datetime.now()
        assert isinstance(concept.last_used, datetime)


class TestConceptVersioning:
    """Test concept versioning."""

    def test_version_increment(self):
        """Test incrementing version."""
        concept = CanonicalConcept(
            canonical_id="concept:customer",
            canonical_name="customer",
            display_name="Customer",
            domain="sales",
            version=1
        )

        assert concept.version == 1

        # Simulate version update
        concept.previous_version_id = "concept:customer_v1"
        concept.version = 2

        assert concept.version == 2
        assert concept.previous_version_id == "concept:customer_v1"
