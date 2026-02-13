## Context

`EpisodicMemoryService` constructs `group_id` values to partition episodes in Graphiti/FalkorDB. The current format uses colons as separators:

- Session-level episodes: `group_id = patient_id` (e.g., `patient:demo`)
- Turn-level episodes: `group_id = f"{patient_id}:{session_id}"` (e.g., `patient:demo:session:19e7d4d9-...`)

Graphiti (as of current version) validates group IDs with `validate_group_id()` which rejects any character that isn't alphanumeric, a dash, or an underscore. Colons fail validation on writes and cause RediSearch syntax errors on reads.

The `patient_id` format is `patient:demo` (contains a colon) and `session_id` format is `session:uuid` (also contains a colon). Both the prefix-colon-value pattern and the colon separator between them are invalid.

## Goals / Non-Goals

**Goals:**
- All `group_id` values passed to Graphiti conform to the allowed character set (alphanumeric, dashes, underscores)
- Session IDs can still be extracted from a stored `group_id` (reverse-parsing)
- Existing code patterns for DDA/KG group IDs (`dda_...`, `feedback_...`, `kg_...`) remain untouched

**Non-Goals:**
- Migrating existing episodes stored with old group_id format (they were never stored successfully)
- Changing the `patient_id` or `session_id` formats elsewhere in the system (only sanitize at the Graphiti boundary)

## Decisions

### D1: Centralise sanitization in a `_sanitize_group_id()` helper

**Choice**: Add a single static method `_sanitize_group_id(raw_id: str) -> str` that replaces colons with dashes. All group_id construction calls through this method.

**Rationale**: Colons are the only invalid character present in our IDs (the rest are alphanumeric, dashes from UUIDs, and underscores). A simple `str.replace(":", "-")` is sufficient. Centralising it prevents future occurrences of the same bug if new callers are added.

**Transformation examples**:
- `patient:demo` → `patient-demo`
- `patient:demo:session:19e7d4d9-d33b-48c1-b351-97511b67bc12` → `patient-demo--session-19e7d4d9-d33b-48c1-b351-97511b67bc12`

Note: the double-dash (`--`) between patient and session parts is intentional — it comes from the colon in `session:uuid` being replaced. This is a valid separator and makes parsing unambiguous.

### D2: Use a double-dash `--` as the patient/session separator

**Choice**: Construct composite group IDs as `f"{sanitize(patient_id)}--{sanitize(session_id)}"`, using `--` as the explicit separator between patient and session parts.

**Rationale**: Since individual IDs can contain single dashes (from UUIDs), we need a separator that won't appear inside either component. A double-dash (`--`) is unambiguous because:
- Patient IDs are formatted as `patient-{name}` (one dash after sanitize)
- Session IDs are formatted as `session-{uuid}` (dashes within UUID, but no consecutive `--`)

**Parsing**: `group_id.split("--", 1)` cleanly splits into `[patient_part, session_part]`.

### D3: Update `_convert_episode()` parsing to use `--` split

**Choice**: Replace the colon-based split in `_convert_episode()` with `"--"` split, and restore the original colon format only if needed for display (it isn't currently).

**Rationale**: The parsed `session_id` is only used within `ConversationEpisode` metadata. No downstream code re-uses it as a Neo4j or API key, so the sanitized form is fine.

## Risks / Trade-offs

- **Existing FalkorDB data unreachable**: Episodes stored with old colon-separated group_ids won't be findable under new IDs. Acceptable since writes were failing anyway — no valid data exists.
  → Mitigation: None needed. FalkorDB can be reset cleanly.

- **Patient-level group_id also has colons**: `patient_id` alone (e.g., `patient:demo`) is used as `group_id` for session-level episodes (line 80-81 in docstring, line 331 in `retrieve_recent_episodes`). This also needs sanitization.
  → Mitigation: All group_id usage goes through `_sanitize_group_id()`, including the patient-only case.
