## 1. Update structural marking queries

- [x] 1.1 Add `'ConversationSession', 'Message'` to the label list in `MARK_STRUCTURAL_QUERY` (line 483 of remediation_service.py)
- [x] 1.2 Add `'ConversationSession', 'Message'` to the structural label list in `PRE_STATS_QUERY` (line 530)
- [x] 1.3 Add `'ConversationSession', 'Message'` to the exclusion label list in `UNMAPPED_TYPES_QUERY` (line 543)

## 2. Remove conversation-to-usage mapping

- [x] 2.1 Delete the `conversation_mapping` tuple (lines 323-337) from `REMEDIATION_QUERIES`

## 3. Add migration query for already-remediated nodes

- [x] 3.1 Add a migration query early in `REMEDIATION_QUERIES` that removes `_ontology_mapped` and `_canonical_type` from ConversationSession/Message nodes and sets `_is_structural=true`, `_exclude_from_ontology=true`, guarded by `NOT coalesce(n._is_structural, false)`

## 4. Update tests

- [x] 4.1 Add test verifying `conversation_mapping` is not in `REMEDIATION_QUERIES`
- [x] 4.2 Add test verifying `ConversationSession` and `Message` appear in `MARK_STRUCTURAL_QUERY`
- [x] 4.3 Add test verifying `ConversationSession` and `Message` appear in `PRE_STATS_QUERY` and `UNMAPPED_TYPES_QUERY`
- [x] 4.4 Add test verifying the migration query exists and is idempotent (guarded by `NOT _is_structural`)
- [x] 4.5 Run full test suite to confirm no regressions
