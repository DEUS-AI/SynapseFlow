## 1. crystallization_service.py (7 occurrences)

- [x] 1.1 Update import: add `timezone` to `from datetime import datetime, timedelta` (line 24)
- [x] 1.2 Replace 7 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 219, 327, 392, 457, 458, 518, 607)

## 2. kg_operations_api.py (5 occurrences)

- [x] 2.1 Update import: add `timezone` to `from datetime import datetime` (line 14)
- [x] 2.2 Replace 5 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 176, 212, 303, 445, 685)

## 3. temporal_scoring.py (5 occurrences)

- [x] 3.1 Update import: add `timezone` to `from datetime import datetime, timedelta` (line 16)
- [x] 3.2 Replace 5 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 67, 109, 173, 175, 215)

## 4. knowledge_manager/agent.py (3 occurrences)

- [x] 4.1 Update import: add `timezone` to `from datetime import datetime` (line 8)
- [x] 4.2 Replace 3 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 58, 81, 82)

## 5. knowledge_commands.py (2 occurrences)

- [x] 5.1 Update import: add `timezone` to `from datetime import datetime` (line 6)
- [x] 5.2 Replace 2 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 40, 93)

## 6. promotion_gate.py (2 occurrences)

- [x] 6.1 Update import: add `timezone` to `from datetime import datetime, timedelta` (line 21)
- [x] 6.2 Replace 2 `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (lines 573, 624)

## 7. entity_resolver.py (1 occurrence)

- [x] 7.1 Update import: add `timezone` to `from datetime import datetime` (line 21)
- [x] 7.2 Replace 1 `datetime.utcnow()` call with `datetime.now(timezone.utc)` (line 866)

## 8. main.py (1 occurrence, local import)

- [x] 8.1 Update local import: change `from datetime import datetime` to `from datetime import datetime, timezone` (line 2777)
- [x] 8.2 Replace `datetime.utcnow().isoformat() + "Z"` with `datetime.now(timezone.utc).isoformat()` (line 2799) — the `+00:00` suffix replaces the manual `"Z"` append

## 9. Verification

- [x] 9.1 Run `grep -r "utcnow" src/` to confirm zero remaining occurrences
- [x] 9.2 Run existing tests to confirm no regressions
