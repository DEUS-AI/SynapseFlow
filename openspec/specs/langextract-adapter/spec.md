## ADDED Requirements

### Requirement: LangExtract ingestion service
The system SHALL provide a `LangExtractIngestionService` class in `src/application/services/langextract_ingestion.py` that uses Google's LangExtract library to extract structured entities and relationships from document text. The service SHALL follow the same interface pattern as existing ingestion services (`Neo4jPDFIngestionService`, `SimplePDFIngestionService`).

**Primary files**: `src/application/services/langextract_ingestion.py`, `tests/application/test_langextract_ingestion.py`

#### Scenario: Successful entity extraction from medical text
- **WHEN** the service receives a file path to a document that MarkItDown can convert to text
- **THEN** it SHALL convert the file to text, run LangExtract extraction, and return an `ExtractionResult` with entities and relationships mapped to SynapseFlow's entity taxonomy (Disease, Treatment, Symptom, Test, Drug, Gene, Pathway, Organization, Study)

#### Scenario: Source grounding metadata preserved
- **WHEN** LangExtract returns extractions with character-offset source grounding
- **THEN** the service SHALL include grounding offsets in each entity's metadata dict under the key `source_grounding`

#### Scenario: LangExtract unavailable
- **WHEN** the `langextract` package is not installed
- **THEN** the module SHALL set `LANGEXTRACT_AVAILABLE = False` and raise `ImportError` with a descriptive message when the service is instantiated

### Requirement: Configurable LLM model
The service SHALL accept a `model_id` parameter (default: `gemini-2.5-flash`) and an `api_key` parameter (default: read from `LANGEXTRACT_API_KEY` or `GEMINI_API_KEY` environment variable). It SHALL also accept `extraction_passes` (default: 1) and `max_workers` (default: 5) for controlling extraction depth and parallelism.

#### Scenario: Custom model configuration
- **WHEN** the service is instantiated with `model_id="gpt-4o"` and a valid OpenAI API key
- **THEN** it SHALL use OpenAI as the LangExtract backend with `fence_output=True` and `use_schema_constraints=False`

#### Scenario: Default configuration uses Gemini
- **WHEN** the service is instantiated without explicit model parameters
- **THEN** it SHALL use `gemini-2.5-flash` with `use_schema_constraints=True`

### Requirement: Medical entity extraction examples
The service SHALL define few-shot extraction examples tailored to SynapseFlow's medical entity taxonomy. Examples SHALL cover at minimum: Disease, Treatment, Symptom, and Drug entity types with appropriate attributes (name, type, description, confidence).

#### Scenario: Examples guide extraction to match taxonomy
- **WHEN** extracting from a medical text containing diseases, treatments, and symptoms
- **THEN** extracted entities SHALL use `extraction_class` values matching SynapseFlow types (Disease, Treatment, Symptom, etc.) rather than arbitrary LangExtract classes

### Requirement: DIKW layer assignment
All entities extracted by the service SHALL be assigned to the PERCEPTION layer with an initial confidence score derived from the extraction context. The confidence SHALL default to 0.7 matching the existing pipeline behavior.

#### Scenario: Extracted entities have PERCEPTION layer metadata
- **WHEN** extraction completes successfully
- **THEN** every entity in the result SHALL include `layer: "PERCEPTION"` and `confidence: 0.7` in its attributes
