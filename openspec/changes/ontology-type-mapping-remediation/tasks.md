## 1. Domain Layer — ODINMedical Extension

- [x] 1.1 Add `FOOD_COMPONENT = "FoodComponent"` constant to `ODINMedical` class in the SEMANTIC layer section of `src/domain/ontologies/odin_medical.py`
- [x] 1.2 Add `"food_component"` entry to `MEDICAL_ONTOLOGY_REGISTRY` with `odin_class=ODINMedical.FOOD_COMPONENT`, `layer="SEMANTIC"`, `parent_type="biological_entity"`, `auto_relationships=["ASSOCIATED_WITH", "INTERACTS_WITH"]`, `external_systems=[MeSH, SNOMED_CT]`, `hierarchy_path=["biological_entity", "food_component"]`, `confidence_threshold=0.85`
- [x] 1.3 Add type aliases to `MEDICAL_TYPE_ALIASES`: `"genus"→"organism"`, `"model organism"→"organism"`, `"model_organism"→"organism"`, `"food component"→"food_component"`, `"food_component"→"food_component"`, `"food components"→"food_component"`, `"nutrient"→"food_component"`, `"nutrients"→"food_component"`, `"dietary substance"→"food_component"`, `"dietary_substance"→"food_component"`, `"vitamin"→"food_component"`, `"vitamins"→"food_component"`

## 2. Domain Layer — ODIN Schemas and Schema.org

- [x] 2.1 Add `"FoodComponent"` entry to `ODIN_SCHEMAS` in `src/domain/ontology_quality_models.py` with `namespace="odin:medical"`, `required_properties=["name", "id"]`, `optional_properties=["description", "layer", "confidence", "_canonical_type"]`, `allowed_relationships=["ASSOCIATED_WITH", "INTERACTS_WITH"]`
- [x] 2.2 Add `"FoodComponent": "Thing"` to `SCHEMA_ORG_MAPPINGS` in `src/domain/ontology_quality_models.py`

## 3. Application Layer — New Remediation Queries

- [x] 3.1 Add `food_component_mapping` query to `REMEDIATION_QUERIES` in `src/application/services/remediation_service.py` matching `type IN ['FoodComponent', 'food_component', 'Food Component', 'Nutrient', 'nutrient', 'Vitamin', 'vitamin', 'DietarySubstance']` or labels `['FoodComponent', 'Nutrient']`
- [x] 3.2 Add `genus_mapping` query matching `type IN ['Genus', 'genus']` or labels `['Genus']`, setting `_canonical_type='organism'`
- [x] 3.3 Add `model_organism_mapping` query matching `type IN ['Model Organism', 'model_organism', 'ModelOrganism']` or labels `['ModelOrganism']`, setting `_canonical_type='organism'`
- [x] 3.4 Add `unknown_type_flag_review` query matching `type IN ['Unknown', 'unknown']`, setting `_needs_review=true`, `_review_reason='unknown_type'` (NOT setting `_ontology_mapped`)

## 4. Application Layer — Orphan Classification and Consistency

- [x] 4.1 Add `orphan_source_classification` query to `REMEDIATION_QUERIES` (after `orphan_node_flagging`) matching `WHERE n._is_orphan = true` and setting `_orphan_source` via CASE: `'episodic'` for EntityNode/EpisodicNode labels, `'knowledge'` for ODIN/medical labels, `'unclassified'` otherwise
- [x] 4.2 Add `type_consistency_normalization` query as the **last** entry in `REMEDIATION_QUERIES` matching `WHERE n._ontology_mapped = true` with mismatched `_canonical_type`, correcting via CASE expression and setting `_consistency_fixed=true`
- [x] 4.3 Update `ORPHANS_QUERY` to include `n._orphan_source` in the RETURN clause
- [x] 4.4 Update `get_orphans()` method to include `orphan_source` in the returned dicts

## 5. Tests

- [x] 5.1 Add tests for `resolve_medical_type()` with new aliases: Genus→organism, Model Organism→organism, Food Component→food_component, Nutrient→food_component, Vitamin→food_component
- [x] 5.2 Add test that `is_medical_type("food_component")` returns `True` and `is_medical_type("Unknown")` returns `False`
- [x] 5.3 Add test that `get_medical_ontology_config("food_component")` returns valid config with correct layer and relationships
- [x] 5.4 Add test that `get_layer_for_medical_type("food_component")` returns `"SEMANTIC"`
- [x] 5.5 Add test that `ODIN_SCHEMAS["FoodComponent"]` exists with correct required_properties and namespace
- [x] 5.6 Add test that `SCHEMA_ORG_MAPPINGS["FoodComponent"]` equals `"Thing"`
