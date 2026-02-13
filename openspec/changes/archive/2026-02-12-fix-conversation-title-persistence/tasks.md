## 1. Startup Warning and Initialisation

- [x] 1.1 Add WARNING log in `ChatHistoryService.__init__()` when `openai_api_key` is not provided and `self.openai_client` is set to `None`
- [x] 1.2 Add INFO log when `openai_client` is successfully initialised

## 2. Fallback Title Generator

- [x] 2.1 Add `_fallback_title_from_message(content: str) -> str` method to `ChatHistoryService` that strips greeting filler ("hi", "hello", "hey doctor", etc.), extracts first 4-5 significant words, applies title case, and caps at 50 characters
- [x] 2.2 Write unit tests for `_fallback_title_from_message`: greeting stripping, truncation at word boundary, title casing, short messages, empty input

## 3. Rewrite `auto_generate_title()` Strategy Order

- [x] 3.1 Restructure `auto_generate_title()` to try LLM generation first (move current Strategy 2 code to run before Strategy 1)
- [x] 3.2 Add empty/whitespace validation on LLM-returned title — treat as failure and fall through to fallback
- [x] 3.3 Replace the intent-based title branch with the new `_fallback_title_from_message()` as the secondary strategy when LLM is unavailable or fails
- [x] 3.4 Add WARNING log for each early-return path: no messages found, no user message in first 3 messages
- [x] 3.5 Add WARNING log when LLM call raises an exception (with exception details), before falling through to fallback
- [x] 3.6 Add INFO log when fallback title is used, including the generated title and the reason (no client / LLM error)

## 4. Persistence Verification Logging

- [x] 4.1 In `PatientMemoryService.update_session_title()`, ensure the WARNING log on `result` being empty includes the session_id and attempted title
- [x] 4.2 In the WebSocket handler auto-title block (`main.py`), add WARNING log when read-back verification fails, including expected vs actual title values

## 5. Frontend SessionList Resilience

- [x] 5.1 Add `useEffect` with `document.addEventListener('visibilitychange', ...)` in `SessionList.tsx` that calls `loadSessions()` when the tab becomes visible
- [x] 5.2 Add `setInterval` (30s) in the same `useEffect` that periodically calls `loadSessions()` while the document is visible, clearing the interval on unmount and when the tab is hidden
- [x] 5.3 Verify that the existing WebSocket `title_updated` → `sessionListKey` refresh path still works alongside the new polling

## 6. Integration Testing

- [x] 6.1 Write test: `auto_generate_title` with mocked OpenAI client returns LLM-generated title and persists it
- [x] 6.2 Write test: `auto_generate_title` with `openai_client=None` uses fallback and persists a message-based title
- [x] 6.3 Write test: `auto_generate_title` with LLM raising exception falls through to fallback
- [x] 6.4 Write test: `auto_generate_title` with LLM returning empty string falls through to fallback
- [x] 6.5 Write test: verify WARNING logs are emitted for each failure path (no messages, no user message, LLM error, persistence failure)
