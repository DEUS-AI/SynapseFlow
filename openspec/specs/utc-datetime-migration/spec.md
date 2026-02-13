## ADDED Requirements

### Requirement: All UTC timestamps use timezone-aware datetime
All code that obtains the current UTC time SHALL use `datetime.now(timezone.utc)` instead of the deprecated `datetime.utcnow()`. The returned datetime objects SHALL carry `tzinfo=datetime.timezone.utc`.

#### Scenario: Service generates a current UTC timestamp
- **WHEN** any backend service needs the current UTC time (e.g., for `created_at`, `timestamp`, `assessed_at`, `last_observed`)
- **THEN** it SHALL call `datetime.now(timezone.utc)` which returns a timezone-aware datetime

#### Scenario: Timestamp serialized to ISO format
- **WHEN** a timezone-aware UTC datetime is serialized via `.isoformat()`
- **THEN** the output string SHALL include the `+00:00` suffix (e.g., `2024-01-01T10:00:00+00:00`)

### Requirement: Consistent timezone import pattern
All files that use UTC timestamps SHALL import `timezone` from the `datetime` module using `from datetime import datetime, timezone`. No file SHALL use `datetime.datetime.utcnow()` or `datetime.utcnow()`.

#### Scenario: Import statement in a migrated file
- **WHEN** a file contains `datetime.now(timezone.utc)`
- **THEN** the file SHALL have `from datetime import datetime, timezone` (or equivalent) in its imports

#### Scenario: No deprecated calls remain
- **WHEN** the codebase is searched for `utcnow()`
- **THEN** zero occurrences SHALL be found in `src/` (excluding comments and documentation)
