## Context

The auto-title pipeline triggers after a session reaches 3 messages. It runs inside the WebSocket handler (`main.py:282-323`) and delegates to `ChatHistoryService.auto_generate_title()`, which attempts two strategies:

1. **Strategy 1 — Intent-based** (`ConversationalIntentService`): Classifies the first user message, extracts a `topic_hint`, and builds a title like "Knee Pain Discussion". Depends entirely on `_extract_topic()` finding a matching term.
2. **Strategy 2 — LLM fallback** (`openai gpt-4o-mini`): Sends the first 3 messages to the LLM and asks for a 3-5 word title. Only runs if `self.openai_client` is not `None`.

The current failure mode: `_extract_topic()` has 18 hardcoded medical terms. For any other topic, `topic_hint` is `None`, Strategy 1 skips silently, and if the OpenAI client is unavailable, Strategy 2 also skips. The function returns `None` without any warning log — the caller sees no error.

On the frontend, `SessionList` only updates titles via WebSocket `title_updated` events. If that message is never sent (because auto-title returned `None`), or if the WS message is lost (reconnect, race condition), the title stays stale until the user manually refreshes the page (which triggers `loadSessions()`).

## Goals / Non-Goals

**Goals:**
- Every conversation gets a meaningful title by the 3rd message, regardless of domain
- When title generation fails, operators can diagnose _why_ from logs alone
- Frontend always shows current titles, even if the WebSocket notification was missed

**Non-Goals:**
- Changing the title generation trigger threshold (stays at 3 messages)
- Adding user-facing error messages for title generation failures (this is background behaviour)
- Migrating title storage from Neo4j to PostgreSQL (separate effort)
- Changing the manual title edit flow (already works correctly)

## Decisions

### D1: Replace hardcoded term list with first-message summarisation

**Choice**: Remove `_extract_topic()` entirely from the title generation path. Instead, always use the LLM (Strategy 2) as the primary strategy, and keep a simplified pattern-based title as the _fallback_ when the LLM is unavailable.

**Rationale**: The intent service's `_extract_topic()` was designed for routing, not title generation. Trying to build titles from a single extracted keyword produces low-quality titles ("Pain Discussion") and fails for anything outside the medical domain. The LLM already generates better titles — it just wasn't being reached.

**Alternatives considered**:
- _Expand the keyword list_ — Doesn't scale, still produces mechanical titles, and doesn't solve the fundamental approach problem.
- _Use the LLM for topic extraction, then build the title from the topic_ — Adds an extra LLM call for no benefit over just asking for the title directly.

**Implementation**: In `auto_generate_title()`, swap the strategy order:
1. Try LLM title generation first (currently Strategy 2)
2. Fall back to a simple pattern-based title from the first user message (truncated + cleaned) if LLM is unavailable

### D2: Defensive `openai_client` initialisation with startup warning

**Choice**: At `ChatHistoryService.__init__()`, if no OpenAI API key is available, log a `WARNING`-level message: `"No OPENAI_API_KEY configured — auto-title generation will use fallback only"`. This makes the missing-key scenario visible at startup rather than silently failing per-session.

**Rationale**: The current code silently sets `self.openai_client = None` and never logs it. Operators discover the issue only after noticing titles aren't being generated.

### D3: Structured logging at every decision point

**Choice**: Add `logger.warning()` calls at each exit path in `auto_generate_title()` where a strategy is skipped or fails:
- No messages found for session
- No user message in first 3 messages
- LLM call failed (with exception details)
- LLM returned empty/invalid title
- Fallback title used (with reason)
- Neo4j persistence returned `False`
- Read-back verification mismatch

**Rationale**: The current code has `logger.info` for the happy path and `logger.warning` for some errors, but several `None`-return paths have no logging at all (lines 558-565 in `chat_history_service.py`).

### D4: Simple fallback title from first user message

**Choice**: When the LLM is unavailable or fails, generate a title by taking the first user message, truncating to ~40 characters at a word boundary, and appending "..." if truncated. Example: "I've been having trouble sleeping lately" → "Trouble Sleeping Lately".

**Rationale**: Any title is better than "New Conversation". This gives enough context to identify the session without requiring an LLM call.

**Implementation**: A private method `_fallback_title_from_message(content: str) -> str` that:
1. Strips leading filler ("hi", "hello", "hey doctor")
2. Capitalises the first ~4-5 significant words in title case
3. Caps at 50 characters

### D5: Frontend fetches fresh titles on SessionList mount

**Choice**: In `SessionList.tsx`, the existing `loadSessions()` call on mount already fetches titles from the API. The fix is to ensure this also runs when the component regains visibility (e.g., tab switch, navigation back to chat). Add a `visibilitychange` listener and a periodic soft-refresh (every 30s while the list is visible).

**Rationale**: The current `loadSessions()` runs on mount and when `sessionListKey` changes (from WS events). If the WS event is missed, the stale title persists until a full page reload. A lightweight periodic refresh closes this gap without adding complexity.

**Alternatives considered**:
- _Retry WS delivery_ — Would require server-side tracking of which clients received which messages. Overkill for this problem.
- _Store titles in localStorage as cache_ — Adds a second source of truth that can become stale. Not worth it.

## Risks / Trade-offs

- **LLM cost increase**: Making LLM the primary strategy means every session with 3+ messages incurs a gpt-4o-mini call (~$0.0001 per title). Previously, sessions matching medical keywords avoided this call.
  → Mitigation: gpt-4o-mini is extremely cheap; the cost is negligible even at thousands of sessions/day.

- **LLM latency on title generation**: ~200-500ms added to the WebSocket response cycle for the 3rd message.
  → Mitigation: Title generation already runs _after_ the response is sent to the user (line 282 is after `send_personal_message` on line 280). No user-facing latency impact.

- **Fallback title quality**: Truncated first-message titles may be awkward ("My Stomach Has Been...").
  → Mitigation: This is strictly better than "New Conversation" and only activates when the LLM is completely unavailable.

- **30s polling on SessionList**: Adds periodic API calls while the session list is visible.
  → Mitigation: The endpoint is lightweight (single Neo4j query). 30s interval is conservative. Only polls when the tab is active (visibility API).
