## 1. Sanitization Helper

- [x] 1.1 Add `_sanitize_group_id(raw_id: str) -> str` static method to `EpisodicMemoryService` that replaces colons with dashes
- [x] 1.2 Update the class docstring (lines 78-81) to reflect the new group_id format (`--` separator, no colons)

## 2. Group ID Construction

- [x] 2.1 Update `store_turn_episode()` (line 159): replace `f"{patient_id}:{session_id}"` with `f"{self._sanitize_group_id(patient_id)}--{self._sanitize_group_id(session_id)}"`
- [x] 2.2 Update `retrieve_recent_episodes()` (line 328): replace `f"{patient_id}:{session_id}"` with sanitized composite format
- [x] 2.3 Update `retrieve_recent_episodes()` (line 331): sanitize patient-only group_id (`patient_id` → `self._sanitize_group_id(patient_id)`)
- [x] 2.4 Update `search_episodes()` (line 372): sanitize patient-only group_id
- [x] 2.5 Update `search_episodes()` (line 374): replace `f"{patient_id}:{session_id}"` with sanitized composite format

## 3. Group ID Parsing

- [x] 3.1 Update `_convert_episode()` (lines 559-564): replace colon-based split with `"--"` split to extract session_id
- [x] 3.2 Ensure legacy colon-separated group_ids don't crash parsing (no `--` found → session_id is None)

## 4. Tests

- [x] 4.1 Write unit tests for `_sanitize_group_id`: colon replacement, passthrough for clean IDs, empty string
- [x] 4.2 Update `test_episodic_memory.py` assertions (lines 119, 188, 268, 342) to use the new dash/double-dash format
- [x] 4.3 Write test for `_convert_episode` parsing: composite group_id extracts session_id, patient-only returns None, legacy colon format returns None gracefully
