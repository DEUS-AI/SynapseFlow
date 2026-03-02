## ADDED Requirements

### Requirement: Agent processes SHALL expose an A2A-compatible receive endpoint
Each agent running as a container SHALL expose a `POST /v1/tasks/send` HTTP endpoint that accepts inbound A2A messages. This completes the bidirectional A2A communication — the existing `A2ACommunicationChannel.send()` posts to this endpoint on the target agent.

#### Scenario: Agent receives a message via A2A endpoint
- **WHEN** `POST /v1/tasks/send` is called on the DataArchitect container (port 8001) with a valid A2A message payload
- **THEN** the agent SHALL deserialize the message into a `domain.communication.Message`, enqueue it for the target agent, and return HTTP 200 with `{"status": "accepted", "taskId": "<message-id>"}`

#### Scenario: Malformed A2A message is rejected
- **WHEN** `POST /v1/tasks/send` is called with a payload missing required fields (`taskId` or `message`)
- **THEN** the endpoint SHALL return HTTP 400 with a description of the missing fields

#### Scenario: Agent is overloaded
- **WHEN** `POST /v1/tasks/send` is called and the agent's message queue exceeds a configurable threshold (default: 1000 messages)
- **THEN** the endpoint SHALL return HTTP 429 with `{"error": "queue_full", "retry_after": 5}`

### Requirement: A2ACommunicationChannel.receive() SHALL return messages from the inbound queue
The `A2ACommunicationChannel.receive(agent_id)` method SHALL return messages that were received by the A2A endpoint, instead of returning `None` with a print statement. Messages SHALL be stored in an async queue per agent and consumed FIFO.

#### Scenario: Message sent and received across containers
- **WHEN** Container A sends a message to Container B via `A2ACommunicationChannel.send()`
- **AND** Container B has the A2A receive endpoint running
- **THEN** `A2ACommunicationChannel.receive(agent_id)` on Container B SHALL return that message

#### Scenario: No messages available
- **WHEN** `receive(agent_id)` is called and no messages are queued for that agent
- **THEN** the method SHALL return `None` without blocking

### Requirement: A2ACommunicationChannel SHALL resolve agent URLs from configuration
The `A2ACommunicationChannel` SHALL use the agent configuration (`agents.yaml` or `agents.distributed.yaml`) to resolve target agent URLs when sending messages, instead of requiring a single `base_url` for all agents.

#### Scenario: Message routed to correct agent URL
- **WHEN** `send(message)` is called with `receiver_id="knowledge_manager"`
- **THEN** the channel SHALL look up the KnowledgeManager's URL from configuration (e.g., `http://knowledge_manager:8003`) and POST to `http://knowledge_manager:8003/v1/tasks/send`

#### Scenario: Unknown receiver agent
- **WHEN** `send(message)` is called with a `receiver_id` not found in the agent configuration
- **THEN** the channel SHALL raise an `AgentNotFoundError` with the unknown agent ID

### Requirement: A2A message format SHALL preserve domain Message semantics
The A2A wire format SHALL include all fields of the domain `Message` dataclass: `id`, `sender_id`, `receiver_id`, `content`, and `metadata`. The content field SHALL support both string and structured (dict) payloads via JSON serialization.

#### Scenario: Structured content round-trips through A2A
- **WHEN** a `Message` with `content={"type": "escalate_operations", "operations": [...]}` is sent via A2A
- **THEN** the receiving agent SHALL reconstruct a `Message` with the identical dict content, not a string representation

#### Scenario: Message metadata is preserved
- **WHEN** a `Message` with `metadata={"priority": "high", "correlation_id": "abc-123"}` is sent via A2A
- **THEN** the receiving agent SHALL have `message.metadata["priority"] == "high"` and `message.metadata["correlation_id"] == "abc-123"`
