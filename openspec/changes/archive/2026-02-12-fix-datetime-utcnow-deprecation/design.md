## Context

Python 3.12 deprecated `datetime.utcnow()` because it returns a naive datetime (no `tzinfo`), making it ambiguous whether a value is UTC or local time. The replacement `datetime.now(timezone.utc)` returns a timezone-aware datetime. The codebase has 26 occurrences across 8 files, all following the same pattern: `datetime.utcnow()` used directly or chained with `.isoformat()` / `.strftime()`.

All affected files already import `datetime` from the `datetime` module. None currently import `timezone`.

## Goals / Non-Goals

**Goals:**
- Replace all 26 `datetime.utcnow()` calls with `datetime.now(timezone.utc)`
- Add `timezone` to existing import statements
- Eliminate all deprecation warnings from server logs

**Non-Goals:**
- Migrating `datetime.now()` calls (without UTC) — those are used intentionally for local time
- Adding timezone awareness to domain models or stored data formats
- Changing how timestamps are serialized (`.isoformat()` will now include `+00:00` suffix, which is valid ISO 8601)

## Decisions

### D1: Direct replacement — `datetime.utcnow()` → `datetime.now(timezone.utc)`

**Choice**: Simple find-and-replace of `datetime.utcnow()` with `datetime.now(timezone.utc)` in all 8 files.

**Rationale**: Both return the current UTC time. The only difference is that `datetime.now(timezone.utc)` includes `tzinfo=UTC`. Since all usages either serialize to string (`.isoformat()`, `.strftime()`) or store the value in a field that is compared against other `utcnow()` results (which will also be migrated), there is no naive-vs-aware comparison risk.

**Alternative considered**: Creating a `utc_now()` helper function to centralize the call. Rejected — it adds indirection for a trivial one-liner that is idiomatic Python.

### D2: Add `timezone` to existing imports

**Choice**: Extend existing `from datetime import datetime` lines to include `timezone` (e.g., `from datetime import datetime, timezone`). For `main.py` which has local imports inside functions, add `timezone` to those same local imports.

**Rationale**: Follows the existing import style in each file. No new import lines needed — just extending existing ones.

### D3: Accept `.isoformat()` output change

**Choice**: Allow the `.isoformat()` output to change from `2024-01-01T10:00:00` to `2024-01-01T10:00:00+00:00`.

**Rationale**: The `+00:00` suffix is valid ISO 8601 and is handled correctly by all JSON parsers, JavaScript `Date()`, Python `datetime.fromisoformat()`, and Neo4j. No downstream consumers will break.

## Risks / Trade-offs

- **ISO format change in API responses**: Endpoints that serialize timestamps via `.isoformat()` will now include `+00:00`. This is a non-breaking change — all standard parsers handle it — but external consumers that do exact string matching on timestamp format may notice.
  → Mitigation: The `+00:00` suffix is actually more correct and explicit. No action needed.

- **Naive vs aware comparisons**: If any code path compares a migrated `datetime.now(timezone.utc)` value against a naive datetime from an external source (e.g., a database query), Python will raise `TypeError`.
  → Mitigation: All comparisons in the affected files are against other `utcnow()` calls that will also be migrated in the same change. No mixed comparisons exist.

- **`main.py` local imports**: `main.py` uses local imports inside functions (e.g., `from datetime import datetime` inside endpoint handlers). These need `timezone` added to each local import, not just a top-level import.
  → Mitigation: Tasks will explicitly call out each local import location.
