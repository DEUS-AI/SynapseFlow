## Why

Conversation titles silently fail to generate for most non-medical conversations. The auto-title pipeline has two strategies — intent-based topic extraction and LLM fallback — but both fail quietly: the topic extractor only recognises 18 hardcoded medical terms, and if the OpenAI key is missing or the LLM call errors, no title is ever set. The result is sessions stuck as "New Conversation" with no logs explaining why.

## What Changes

- **Robust topic extraction**: Replace the hardcoded medical-term list in `ConversationalIntentService._extract_topic()` with a general-purpose extraction approach that works for any conversation topic.
- **Reliable LLM fallback**: Ensure Strategy 2 (GPT-4o-mini title generation) always fires when Strategy 1 produces no title, and fails loudly with proper error logging instead of silently returning `None`.
- **Observable failure path**: Add structured logging/warnings at every decision point in the auto-title pipeline so silent failures become visible (strategy skipped, no topic_hint, no OpenAI client, persistence verification failed).
- **Persistence verification & retry**: Strengthen the read-back verification after title writes to Neo4j, and surface verification failures to logs with enough context to debug.
- **Title display resilience**: Ensure the frontend `SessionList` handles the case where a title update WebSocket message is missed (e.g., poll on session list load, not only on WS event).

## Capabilities

### New Capabilities
- `auto-title-generation`: Covers the end-to-end pipeline for automatically generating and persisting conversation titles — topic extraction, LLM fallback, Neo4j write, verification, and frontend notification.

### Modified Capabilities
_(No existing specs to modify)_

## Impact

- **Backend services**:
  - `ConversationalIntentService._extract_topic()` — topic extraction logic rewritten
  - `ChatHistoryService.auto_generate_title()` — fallback chain and logging overhauled
  - `PatientMemoryService.update_session_title()` — verification logging added
  - `main.py` WebSocket handler (auto-title trigger block) — logging and error surfacing
- **Frontend**:
  - `SessionList.tsx` — resilience on load (fetch fresh titles, not only rely on WS)
  - `ChatInterface.tsx` — no structural change, but depends on WS message format staying stable
- **Dependencies**: No new dependencies. Existing `openai` async client, Neo4j driver, WebSocket manager.
- **APIs**: No endpoint signature changes. Internal behaviour only.
