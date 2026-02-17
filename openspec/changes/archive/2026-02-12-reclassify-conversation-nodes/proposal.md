## Why

ConversationSession and Message nodes are currently mapped to the APPLICATION layer with `_canonical_type='usage'` by the remediation pipeline (query #20). This is incorrect — the APPLICATION layer in the DIKW model is reserved for actionable clinical knowledge (Guidelines, Protocols, Studies, Organizations), not session metadata. Conversation nodes are operational/audit data that should be classified as structural, like Chunk and Document nodes, so they don't dilute ontology coverage and compliance metrics.

## What Changes

- Replace the `conversation_mapping` remediation query (#20) that maps ConversationSession/Message to APPLICATION/usage with a structural marking query that sets `_is_structural=true` and `_exclude_from_ontology=true`
- Add ConversationSession and Message to the existing `MARK_STRUCTURAL_QUERY` label list so they're consistently treated as infrastructure nodes
- Update the `PRE_STATS_QUERY` structural detection to include ConversationSession/Message labels
- Add a one-time migration query that fixes any already-remediated conversation nodes (removes `_ontology_mapped`, `_canonical_type='usage'`, and sets `_is_structural=true`)

## Capabilities

### New Capabilities
- `conversation-node-classification`: Defines how ConversationSession and Message nodes are classified in the DIKW knowledge graph — as structural/operational rather than knowledge entities

### Modified Capabilities
- `kg-remediation-api`: The remediation pipeline's handling of conversation nodes changes from ontology mapping to structural marking

## Impact

- `src/application/services/remediation_service.py` — Replace conversation_mapping query, update MARK_STRUCTURAL_QUERY and PRE_STATS_QUERY
- Quality metrics — Conversation nodes will no longer count toward knowledge entity totals or coverage percentages
- Existing remediated data — A migration query is needed to fix nodes already mapped as APPLICATION/usage
