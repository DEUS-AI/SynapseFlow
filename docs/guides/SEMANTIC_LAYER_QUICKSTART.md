# Semantic Layer Quick Start Guide

This guide shows you how to use the new semantic layer components added in Phase 1 of the neurosymbolic enhancement.

## Installation

First, install the new dependencies:

```bash
uv sync
# or
pip install sentence-transformers scikit-learn rapidfuzz
```

## 1. Semantic Normalization

Normalize entity names and terms to canonical forms.

### Basic Usage

```python
from application.services.semantic_normalizer import SemanticNormalizer

# Create normalizer
normalizer = SemanticNormalizer(domain="healthcare")

# Normalize text
normalized = normalizer.normalize("CustAddr")
print(normalized)  # Output: "customer_address"

# Check if two terms are equivalent
if normalizer.are_equivalent("Cust", "Customer"):
    print("These refer to the same concept!")

# Get similarity score
score = normalizer.get_similarity("ClientInfo", "CustomerData")
print(f"Similarity: {score}")  # Output: 0.5 (partial overlap)
```

### Advanced Usage

```python
# Add custom abbreviations
normalizer.add_abbreviation("pt", "patient", domain="healthcare")

# Add custom synonyms
normalizer.add_synonym("diagnosis", "medical_diagnosis", domain="healthcare")

# Normalize with trace (for debugging)
normalized, steps = normalizer.normalize_with_trace("PtDx")
print(f"Result: {normalized}")
print("Steps:")
for step in steps:
    print(f"  - {step}")

# Output:
# Result: patient_medical_diagnosis
# Steps:
#   - Original: PtDx
#   - Basic normalization: pt_dx
#   - Abbreviation expansion: patient_diagnosis
#   - Synonym mapping: patient_medical_diagnosis
#   - Final: patient_medical_diagnosis
```

### Export/Import Rules

```python
# Export rules for persistence
rules = normalizer.export_rules()

# Save to file
import json
with open("normalization_rules.json", "w") as f:
    json.dump(rules, f)

# Later: import rules
with open("normalization_rules.json", "r") as f:
    rules = json.load(f)

new_normalizer = SemanticNormalizer()
new_normalizer.import_rules(rules)
```

## 2. Entity Resolution

Prevent duplicate entities and maintain canonical forms.

### Basic Usage

```python
from application.services.entity_resolver import EntityResolver, ResolutionStrategy
from infrastructure.graphiti_backend import GraphitiBackend

# Initialize with graph backend
backend = GraphitiBackend(...)
resolver = EntityResolver(backend)

# Resolve an entity
resolution = await resolver.resolve_entity(
    entity_name="Customer",
    entity_type="BusinessConcept",
    strategy=ResolutionStrategy.HYBRID
)

# Check result
if resolution.is_duplicate:
    print(f"Found existing entity: {resolution.canonical_entity_id}")
    print(f"Recommended action: {resolution.recommended_action}")
    print(f"Confidence: {resolution.confidence}")

    # Show matches
    for match in resolution.matches:
        print(f"  - {match.entity_name} (score: {match.similarity_score:.2f})")
else:
    print("No duplicates found. Safe to create new entity.")
```

### Advanced Usage

```python
# Use specific resolution strategy
resolution = await resolver.resolve_entity(
    entity_name="Custmer",  # Typo
    entity_type="BusinessConcept",
    strategy=ResolutionStrategy.FUZZY_MATCH,
    properties={"domain": "sales", "description": "..."},
    context={"domain": "sales"}
)

# Custom thresholds
custom_resolver = EntityResolver(
    backend=backend,
    fuzzy_threshold=0.90,      # Stricter fuzzy matching
    semantic_threshold=0.95,   # Stricter semantic matching
    embedding_model="all-mpnet-base-v2"  # Better but slower model
)

# Merge duplicate entities
if resolution.recommended_action == "merge":
    await resolver.merge_entities(
        source_entity_id="concept:customer_duplicate",
        target_entity_id=resolution.canonical_entity_id,
        merge_strategy="preserve_all"
    )
```

### Integration Example

```python
# In Knowledge Enricher
class KnowledgeEnricher:
    def __init__(self, llm_client, backend):
        self.llm = llm_client
        self.normalizer = SemanticNormalizer()
        self.resolver = EntityResolver(backend)

    async def enrich_entity(self, entity_data):
        # Extract concept name
        concept_name = await self._extract_concept(entity_data)

        # Normalize
        canonical_name = self.normalizer.normalize(concept_name)

        # Resolve
        resolution = await self.resolver.resolve_entity(
            canonical_name,
            "BusinessConcept",
            strategy=ResolutionStrategy.HYBRID
        )

        if resolution.is_duplicate:
            # Link to existing concept
            return self._create_link(
                entity_data["id"],
                resolution.canonical_entity_id
            )
        else:
            # Create new concept
            return self._create_concept(canonical_name)
```

## 3. Canonical Concepts

Manage authoritative business concepts and their variations.

### Basic Usage

```python
from domain.canonical_concepts import CanonicalConcept, ConceptRegistry

# Create a canonical concept
customer_concept = CanonicalConcept(
    canonical_id="concept:customer",
    canonical_name="customer",
    display_name="Customer",
    description="Individual or organization that purchases products or services",
    domain="sales",
    confidence=0.98,
    status="ACTIVE"
)

# Add aliases
customer_concept.add_alias("Client", "customer", "sales_dda.md", confidence=0.95)
customer_concept.add_alias("Cust", "customer", "abbreviation", confidence=1.0)
customer_concept.add_alias("Buyer", "customer", "synonym_mapping", confidence=0.90)

# Create registry
registry = ConceptRegistry(domain="sales")
registry.add_concept(customer_concept)

# Later: find by alias
concept = registry.find_by_alias("client")
print(concept.canonical_name)  # Output: "customer"
```

### Hierarchical Concepts

```python
# Create parent concept
party = CanonicalConcept(
    canonical_id="concept:party",
    canonical_name="party",
    display_name="Party",
    description="Any individual or organization",
    domain="common"
)

# Create child concept
customer = CanonicalConcept(
    canonical_id="concept:customer",
    canonical_name="customer",
    display_name="Customer",
    parent_concept_id="concept:party",  # Link to parent
    domain="sales"
)

# Update parent with child
party.child_concept_ids.append("concept:customer")

# Add to registry
registry.add_concept(party)
registry.add_concept(customer)

# Get hierarchy
hierarchy = registry.get_concept_hierarchy("concept:customer")
print(hierarchy)
# Output:
# {
#     "concept": {"id": "concept:customer", "name": "customer"},
#     "parents": [{"id": "concept:party", "name": "party"}],
#     "children": []
# }
```

### Concept Merging

```python
# Merge duplicate concepts
registry.merge_concepts(
    source_id="concept:client",
    target_id="concept:customer"
)

# Source concept is marked as MERGED
# All aliases transferred to target
# Alias index updated
```

### Persistence

```python
# Export registry
data = registry.export_to_json()

# Save to file
import json
with open("sales_concepts.json", "w") as f:
    json.dump(data, f, indent=2)

# Load from file
with open("sales_concepts.json", "r") as f:
    data = json.load(f)

registry = ConceptRegistry.import_from_json(data)
```

## 4. Confidence Modeling

Track and combine confidence scores from multiple sources.

### Basic Usage

```python
from domain.confidence_models import (
    Confidence, ConfidenceSource, create_confidence,
    neural_confidence, symbolic_confidence
)

# Create confidence scores
neural = neural_confidence(score=0.85, generated_by="llm_reasoner")
symbolic = symbolic_confidence(score=1.0, generated_by="validation_rule")

# Check confidence
if neural.is_high_confidence(threshold=0.8):
    print("High confidence neural prediction")

# Apply decay (for reasoning chains)
decayed = neural.decay(factor=0.9)
print(f"Decayed: {neural.score} → {decayed.score}")
```

### Combining Confidences

```python
from domain.confidence_models import (
    ConfidenceCombination, AggregationStrategy
)

# Create multiple confidences
scores = [
    neural_confidence(0.85, "llm_model"),
    symbolic_confidence(1.0, "validation_rule"),
    neural_confidence(0.75, "entity_resolver")
]

# Combine with weighted average
combined = ConfidenceCombination.combine(
    scores=scores,
    strategy=AggregationStrategy.WEIGHTED_AVERAGE,
    weights=[0.5, 0.3, 0.2]  # Prefer neural model
)

print(f"Combined score: {combined.combined_score}")  # 0.895
```

### Neurosymbolic Combination

```python
from domain.confidence_models import ConfidencePropagation

# Initialize propagator
propagator = ConfidencePropagation(decay_factor=0.95, min_threshold=0.1)

# Combine neural and symbolic
neural = neural_confidence(0.8, "llm")
symbolic_certainty = 1.0  # From validation rule

combined = propagator.combine_with_rule(
    neural_confidence=neural,
    symbolic_certainty=symbolic_certainty,
    alpha=0.6  # 60% neural, 40% symbolic
)

print(f"Neurosymbolic confidence: {combined.score}")  # 0.88
print(f"Source: {combined.source}")  # HYBRID
```

### Confidence Tracking

```python
from domain.confidence_models import ConfidenceTracker

tracker = ConfidenceTracker()

# Record confidence over time
tracker.record(0.75, "Initial extraction")
tracker.record(0.82, "After validation")
tracker.record(0.88, "After user feedback")

# Analyze trend
trend = tracker.get_trend()
print(f"Trend: {trend}")  # "increasing"

# Get statistics
print(f"Average: {tracker.get_average()}")  # 0.817
print(f"Latest: {tracker.get_latest()}")    # 0.88
```

## 5. Layer Assignment

Ensure entities are assigned to correct knowledge layers.

### Adding Layer to Entities

```python
from domain.knowledge_layers import KnowledgeLayer

# When creating entity
entity = {
    "id": "table:customers",
    "labels": ["Table", "DataEntity"],
    "properties": {
        "name": "customers",
        "origin": "sales_db",
        "layer": KnowledgeLayer.PERCEPTION.value  # Required!
    }
}

# Semantic layer entity
concept = {
    "id": "concept:customer",
    "labels": ["BusinessConcept"],
    "properties": {
        "name": "customer",
        "description": "...",
        "layer": KnowledgeLayer.SEMANTIC.value,
        "confidence": 0.95  # Optional for SEMANTIC
    }
}

# Reasoning layer entity
rule = {
    "id": "rule:customer_completeness",
    "labels": ["DataQualityRule"],
    "properties": {
        "name": "Customer Completeness",
        "expression": "...",
        "layer": KnowledgeLayer.REASONING.value,
        "confidence": 1.0  # Required for REASONING!
    }
}
```

### Validation

```python
from domain.event import KnowledgeEvent
from domain.roles import Role
from application.agents.knowledge_manager.validation_engine import ValidationEngine

# Create validation engine
validator = ValidationEngine(backend)

# Create event
event = KnowledgeEvent(
    action="create_entity",
    data=entity,
    role=Role.DATA_ENGINEER
)

# Validate
result = await validator.validate_event(event)

if result["is_valid"]:
    print("✓ Entity passes validation")
else:
    print("✗ Validation failed:")
    for error in result["errors"]:
        print(f"  - {error}")

# Check warnings
for warning in result["warnings"]:
    print(f"⚠ {warning}")
```

## 6. Complete Integration Example

Putting it all together:

```python
from application.services.semantic_normalizer import SemanticNormalizer
from application.services.entity_resolver import EntityResolver, ResolutionStrategy
from domain.canonical_concepts import ConceptRegistry, CanonicalConcept
from domain.knowledge_layers import KnowledgeLayer
from domain.confidence_models import neural_confidence

class SemanticLayerService:
    """Unified service for semantic layer operations."""

    def __init__(self, backend, domain="general"):
        self.backend = backend
        self.normalizer = SemanticNormalizer(domain=domain)
        self.resolver = EntityResolver(backend)
        self.concept_registry = ConceptRegistry(domain=domain)

    async def process_entity(self, raw_entity_name, entity_type, confidence=0.8):
        """
        Process an entity through the semantic layer pipeline.

        Steps:
        1. Normalize name
        2. Resolve duplicates
        3. Update concept registry
        4. Return canonical entity reference
        """
        # 1. Normalize
        canonical_name = self.normalizer.normalize(raw_entity_name)
        print(f"Normalized: {raw_entity_name} → {canonical_name}")

        # 2. Resolve
        resolution = await self.resolver.resolve_entity(
            canonical_name,
            entity_type,
            strategy=ResolutionStrategy.HYBRID
        )

        if resolution.is_duplicate:
            print(f"Found duplicate: {resolution.canonical_entity_id}")

            # Update concept registry with new alias
            concept = self.concept_registry.find_by_name(canonical_name)
            if concept:
                concept.add_alias(
                    raw_entity_name,
                    canonical_name,
                    source="entity_processing",
                    confidence=confidence
                )

            return {
                "action": "link",
                "canonical_id": resolution.canonical_entity_id,
                "confidence": resolution.confidence
            }
        else:
            # 3. Create new canonical concept
            concept = CanonicalConcept(
                canonical_id=f"concept:{canonical_name}",
                canonical_name=canonical_name,
                display_name=raw_entity_name,  # Use original as display
                domain=self.concept_registry.domain,
                confidence=confidence,
                properties={"layer": KnowledgeLayer.SEMANTIC.value}
            )

            concept.add_alias(
                raw_entity_name,
                canonical_name,
                source="entity_processing",
                confidence=confidence
            )

            self.concept_registry.add_concept(concept)

            return {
                "action": "create",
                "canonical_id": concept.canonical_id,
                "concept": concept
            }

# Usage
service = SemanticLayerService(graphiti_backend, domain="healthcare")

# Process multiple entity variations
entities = ["Patient", "Pt", "Patient Record", "Patients"]

for entity_name in entities:
    result = await service.process_entity(
        entity_name,
        "BusinessConcept",
        confidence=0.9
    )
    print(f"{entity_name} → {result['action']} {result['canonical_id']}\n")

# Output:
# Normalized: Patient → patient
# Patient → create concept:patient
#
# Normalized: Pt → patient
# Found duplicate: concept:patient
# Pt → link concept:patient
#
# Normalized: Patient Record → patient_record
# Patient Record → create concept:patient_record
#
# Normalized: Patients → patient
# Found duplicate: concept:patient
# Patients → link concept:patient
```

## Testing

### Unit Test Example

```python
import pytest
from application.services.semantic_normalizer import SemanticNormalizer

def test_normalization():
    normalizer = SemanticNormalizer()

    # Test abbreviation expansion
    assert normalizer.normalize("CustAddr") == "customer_address"

    # Test synonym mapping
    assert normalizer.normalize("Client") == "customer"

    # Test equivalence
    assert normalizer.are_equivalent("Cust", "Customer") == True

@pytest.mark.asyncio
async def test_entity_resolution(mock_backend):
    from application.services.entity_resolver import EntityResolver

    resolver = EntityResolver(mock_backend)

    # Add existing entity
    mock_backend.add_entity("concept:customer", {"name": "Customer"})

    # Resolve duplicate
    result = await resolver.resolve_entity("Customer", "BusinessConcept")

    assert result.is_duplicate == True
    assert result.canonical_entity_id == "concept:customer"
```

## Performance Tips

1. **Entity Resolution Caching**: Embeddings are cached automatically. Reuse resolver instance.

2. **Batch Processing**: Process multiple entities together to amortize overhead:
   ```python
   entities = ["Customer", "Client", "Buyer"]
   results = await asyncio.gather(*[
       resolver.resolve_entity(name, "BusinessConcept")
       for name in entities
   ])
   ```

3. **Lazy Loading**: Models load only when needed. First call is slower, subsequent calls are fast.

4. **Custom Thresholds**: Adjust thresholds based on your use case:
   - High precision: Increase thresholds (0.95+)
   - High recall: Decrease thresholds (0.75-0.85)

## Troubleshooting

### "sentence-transformers not installed"
```bash
pip install sentence-transformers
```

### "SHACL validation disabled"
```bash
pip install pyshacl rdflib
```

### "Embedding model not found"
The model downloads automatically on first use. Ensure internet connection.

### "Layer validation failed"
Ensure all entities have a `layer` property:
```python
entity["properties"]["layer"] = "PERCEPTION"  # or SEMANTIC, REASONING, APPLICATION
```

## Next Steps

- Review [Phase 1 Implementation Summary](PHASE1_IMPLEMENTATION_SUMMARY.md) for detailed documentation
- See [Architecture](ARCHITECTURE.md) for system overview
- Check [examples/](../examples/) for sample DDAs
- Run tests: `pytest tests/application/test_entity_resolver.py -v`

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Review validation results for specific failures
3. Consult implementation summary for integration guidance
