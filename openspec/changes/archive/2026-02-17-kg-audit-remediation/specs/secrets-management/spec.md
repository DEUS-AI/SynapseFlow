## ADDED Requirements

### Requirement: No secrets committed to version control
The `.env` file SHALL be listed in `.gitignore` and SHALL NOT be tracked by git. A `.env.example` file SHALL exist with placeholder values (no real keys/passwords) for all required and optional environment variables.

#### Scenario: .env is gitignored
- **WHEN** `git status` is run after creating a `.env` file
- **THEN** the file SHALL appear as untracked (not modified/staged)

#### Scenario: .env.example has placeholders only
- **WHEN** `.env.example` is inspected
- **THEN** it SHALL contain placeholder values like `your-api-key-here` and `changeme` — no real API keys, passwords, or tokens

### Requirement: Required environment variables are validated at startup
A startup validation module SHALL check that all required environment variables are set and non-empty before the application starts. Missing required variables SHALL cause the application to exit with a clear error message listing all missing variables.

#### Scenario: Missing NEO4J_PASSWORD fails fast
- **WHEN** the application starts without `NEO4J_PASSWORD` set
- **THEN** it SHALL exit with an error message that includes `"NEO4J_PASSWORD"` in the list of missing variables

#### Scenario: Missing OPENAI_API_KEY fails fast
- **WHEN** the application starts without `OPENAI_API_KEY` set
- **THEN** it SHALL exit with an error message that includes `"OPENAI_API_KEY"` in the list of missing variables

#### Scenario: All required variables present allows startup
- **WHEN** all required environment variables (`NEO4J_URI`, `NEO4J_PASSWORD`, `OPENAI_API_KEY`) are set
- **THEN** the application SHALL start normally

#### Scenario: Optional variables produce warnings
- **WHEN** optional variables (`REDIS_HOST`, `QDRANT_URL`) are not set
- **THEN** the application SHALL log a warning but continue startup

### Requirement: No hardcoded password defaults in application code
The composition root and service initialization code SHALL NOT contain hardcoded password defaults (e.g., `os.getenv("NEO4J_PASSWORD", "password")`). Password retrieval SHALL fail explicitly if the environment variable is not set.

#### Scenario: Composition root has no password defaults
- **WHEN** `composition_root.py` is inspected for `os.getenv` or `os.environ.get` calls with password-related keys
- **THEN** none SHALL have a non-empty default value for password fields

#### Scenario: Service constructors receive passwords via injection
- **WHEN** services like `CrossGraphQueryBuilder` or `Neo4jPdfIngestion` need a Neo4j password
- **THEN** they SHALL receive it via constructor parameter from the composition root, not by reading env vars directly with fallback defaults
