## Why

Episodic memory (Graphiti + FalkorDB) is completely broken for patient conversations. The `group_id` values use colons as separators (`patient:demo:session:19e7d4d9-...`), but Graphiti validates that group IDs contain only alphanumeric characters, dashes, and underscores. This causes every episode search and every episode write to fail, meaning no conversational context is stored or retrieved in the episodic memory layer.

## What Changes

- **Sanitize group_id construction**: Replace colon-separated `group_id` values with a format that uses only valid characters (alphanumeric, dashes, underscores).
- **Update group_id parsing**: Update the reverse-parsing logic in `_convert_episode()` to match the new format so session IDs can still be extracted from stored group IDs.
- **Update tests**: Align test assertions with the new group_id format.

## Capabilities

### New Capabilities
- `episodic-group-id`: Covers the construction, validation, and parsing of group_id values passed to Graphiti/FalkorDB for episodic memory operations.

### Modified Capabilities
_(No existing specs to modify)_

## Impact

- **Backend services**:
  - `EpisodicMemoryService` (`episodic_memory_service.py`) — 4 locations where group_id is constructed or parsed (lines 159, 328, 374, 562)
- **Tests**:
  - `test_episodic_memory.py` — assertions use the current colon-separated format (lines 119, 188, 268, 342)
- **Not affected**:
  - `domain_modeler.py`, `modeling_feedback_handler.py`, `build_kg.py` — these already use valid underscore-separated formats (`dda_...`, `feedback_...`, `kg_...`)
  - `GraphitiBackend` — uses a static `default` group_id, unaffected
- **Dependencies**: No new dependencies. Fix is internal to how IDs are formatted before passing to the existing Graphiti client.
- **Data migration**: Existing episodes stored with colon-separated group_ids in FalkorDB will become unreachable under the new format. This is acceptable since the current episodes are failing to store anyway. A fresh FalkorDB state is expected.
