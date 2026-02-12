## ADDED Requirements

### Requirement: LLM-primary title generation
The system SHALL use LLM (gpt-4o-mini) as the primary strategy for generating conversation titles. The LLM SHALL receive the first 3 messages of the session and return a concise title (3-5 words).

#### Scenario: Successful LLM title generation
- **WHEN** a session reaches 3 messages and the title is still "New Conversation"
- **THEN** the system calls gpt-4o-mini with the first 3 messages and persists the returned title to Neo4j

#### Scenario: LLM generates title for non-medical conversation
- **WHEN** a session's first user message is "Can you help me understand my lab results?" (no hardcoded keyword match)
- **THEN** the system generates a meaningful title via LLM (e.g., "Lab Results Discussion") instead of leaving it as "New Conversation"

#### Scenario: LLM returns empty or whitespace-only title
- **WHEN** the LLM response is empty or contains only whitespace
- **THEN** the system SHALL treat this as a failed generation and fall through to the fallback strategy

### Requirement: Message-based fallback title
The system SHALL generate a fallback title from the first user message when the LLM is unavailable or fails. The fallback title SHALL be derived by stripping greeting filler, extracting the first 4-5 significant words, applying title case, and capping at 50 characters.

#### Scenario: Fallback when no OpenAI client available
- **WHEN** `OPENAI_API_KEY` is not configured and a session reaches 3 messages
- **THEN** the system generates a title from the first user message (e.g., "I've been having trouble sleeping" → "Trouble Sleeping Lately")

#### Scenario: Fallback when LLM call raises an exception
- **WHEN** the LLM API call fails with a network or API error
- **THEN** the system falls through to the message-based fallback and generates a title

#### Scenario: Greeting filler is stripped from fallback title
- **WHEN** the first user message starts with "Hi doctor, my knee hurts"
- **THEN** the fallback title strips the greeting and produces "My Knee Hurts" (not "Hi Doctor My Knee")

#### Scenario: Long messages are truncated at word boundary
- **WHEN** the first user message exceeds 50 characters of significant content
- **THEN** the fallback title truncates at a word boundary within 50 characters

### Requirement: Title persistence to Neo4j with verification
The system SHALL persist generated titles to the `ConversationSession` Neo4j node and verify the write by reading back the title. If persistence fails or verification mismatches, the system SHALL log a warning with session ID and attempted title.

#### Scenario: Successful persistence and verification
- **WHEN** a title is generated (by either strategy)
- **THEN** the system writes the title via `update_session_title()`, reads it back, and only sends the WebSocket notification after confirming the persisted value matches

#### Scenario: Neo4j write returns false
- **WHEN** `update_session_title()` returns `False` (session node not found)
- **THEN** the system logs a warning including the session ID and does NOT send a WebSocket title_updated event

#### Scenario: Read-back verification mismatch
- **WHEN** the title is written but the read-back returns a different value
- **THEN** the system logs a warning with both the expected and actual title values

### Requirement: Startup warning when LLM unavailable
The system SHALL log a WARNING-level message at `ChatHistoryService` initialisation when no OpenAI API key is configured, indicating that auto-title generation will use fallback only.

#### Scenario: Service starts without OPENAI_API_KEY
- **WHEN** `ChatHistoryService` is initialised and `OPENAI_API_KEY` is not set
- **THEN** a WARNING log is emitted: "No OPENAI_API_KEY configured — auto-title generation will use fallback only"

#### Scenario: Service starts with valid OPENAI_API_KEY
- **WHEN** `ChatHistoryService` is initialised and `OPENAI_API_KEY` is set
- **THEN** no warning is logged about auto-title configuration

### Requirement: Structured logging at every decision point
The system SHALL log at WARNING level for every code path in `auto_generate_title()` that results in a strategy being skipped or a title not being generated, including the reason.

#### Scenario: No messages found for session
- **WHEN** `auto_generate_title()` is called but the session has no messages
- **THEN** the system logs a warning: "No messages found for session {session_id}"

#### Scenario: No user message in first 3 messages
- **WHEN** the first 3 messages contain no user-role message
- **THEN** the system logs a warning: "No user message found in first 3 messages for session {session_id}"

#### Scenario: LLM call fails
- **WHEN** the LLM API call raises an exception
- **THEN** the system logs a warning with the exception details and proceeds to fallback

#### Scenario: Fallback title used
- **WHEN** the fallback strategy is used (LLM unavailable or failed)
- **THEN** the system logs an info message indicating fallback was used and the generated title

### Requirement: Frontend periodic title refresh
The `SessionList` component SHALL refresh session data periodically (every 30 seconds) while visible, and on visibility change (tab switch back), to ensure titles are current even if WebSocket notifications were missed.

#### Scenario: Session list refreshes while tab is active
- **WHEN** the SessionList component is mounted and the browser tab is visible
- **THEN** the component fetches fresh session data from the API every 30 seconds

#### Scenario: Session list refreshes on tab return
- **WHEN** the user switches away from the tab and returns
- **THEN** the component immediately fetches fresh session data from the API

#### Scenario: Polling stops when tab is hidden
- **WHEN** the browser tab becomes hidden (user switches to another tab)
- **THEN** the periodic refresh pauses until the tab becomes visible again

#### Scenario: WebSocket title update still works
- **WHEN** a `title_updated` WebSocket message is received
- **THEN** the session list refreshes immediately (existing behaviour preserved)
