## MODIFIED Requirements

### Requirement: MEDICAL_TYPE_ALIASES includes aliases for new and existing type variants
`MEDICAL_TYPE_ALIASES` SHALL include the following alias mappings:
- `"genus"` → `"organism"`
- `"model organism"` → `"organism"`
- `"model_organism"` → `"organism"`
- `"food component"` → `"food_component"`
- `"food_component"` → `"food_component"`
- `"food components"` → `"food_component"`
- `"nutrient"` → `"food_component"`
- `"nutrients"` → `"food_component"`
- `"dietary substance"` → `"food_component"`
- `"dietary_substance"` → `"food_component"`
- `"vitamin"` → `"food_component"`
- `"vitamins"` → `"food_component"`
- `"cytokine"` → `"protein"`
- `"cytokines"` → `"protein"`
- `"chemical"` → `"drug"`
- `"chemicals"` → `"drug"`

#### Scenario: Genus resolves to organism
- **WHEN** `resolve_medical_type("Genus")` is called
- **THEN** it SHALL return `"organism"`

#### Scenario: Model Organism resolves to organism
- **WHEN** `resolve_medical_type("Model Organism")` is called
- **THEN** it SHALL return `"organism"`

#### Scenario: Food Component resolves to food_component
- **WHEN** `resolve_medical_type("Food Component")` is called
- **THEN** it SHALL return `"food_component"`

#### Scenario: Nutrient resolves to food_component
- **WHEN** `resolve_medical_type("nutrient")` is called
- **THEN** it SHALL return `"food_component"`

#### Scenario: Vitamin resolves to food_component
- **WHEN** `resolve_medical_type("Vitamin")` is called
- **THEN** it SHALL return `"food_component"`

#### Scenario: Cytokine resolves to protein
- **WHEN** `resolve_medical_type("Cytokine")` is called
- **THEN** it SHALL return `"protein"`

#### Scenario: Chemical resolves to drug
- **WHEN** `resolve_medical_type("Chemical")` is called
- **THEN** it SHALL return `"drug"`
