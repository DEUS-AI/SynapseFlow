## Why

`datetime.utcnow()` was deprecated in Python 3.12 (and generates `DeprecationWarning` at runtime). It returns a naive datetime that lacks timezone info, making it ambiguous and error-prone. The codebase has 26 occurrences across 8 files, and every call produces a deprecation warning in the server logs. The replacement is `datetime.now(datetime.timezone.utc)` which returns a timezone-aware UTC datetime.

## What Changes

- **Replace all `datetime.utcnow()` calls** with `datetime.now(timezone.utc)` across 8 source files (26 occurrences)
- **Add `timezone` import** where needed (`from datetime import datetime, timezone`)
- **No behavioral change**: the returned datetime values represent the same instant in time, but are now timezone-aware (carry `tzinfo=UTC`)

## Capabilities

### New Capabilities
- `utc-datetime-migration`: Covers the migration from deprecated `datetime.utcnow()` to timezone-aware `datetime.now(timezone.utc)` across all backend services

### Modified Capabilities
_(None — this is a purely internal code quality fix with no spec-level behavior changes)_

## Impact

- **Backend services** (8 files, 26 occurrences):
  - `src/application/services/crystallization_service.py` — 7 occurrences
  - `src/interfaces/kg_operations_api.py` — 5 occurrences
  - `src/application/services/temporal_scoring.py` — 5 occurrences
  - `src/application/agents/knowledge_manager/agent.py` — 3 occurrences
  - `src/application/commands/knowledge_commands.py` — 2 occurrences
  - `src/application/services/promotion_gate.py` — 2 occurrences
  - `src/application/services/entity_resolver.py` — 1 occurrence
  - `src/application/api/main.py` — 1 occurrence
- **Dependencies**: None. Uses only stdlib `datetime.timezone`.
- **Risk**: Low. `datetime.now(timezone.utc)` returns the same UTC time but timezone-aware. Code that compares naive vs aware datetimes could raise `TypeError`, but all comparisons in these files are against other `utcnow()` calls (which will also be migrated).
- **Tests**: Existing tests may need minor updates if they assert on naive datetime values or mock `datetime.utcnow`.
