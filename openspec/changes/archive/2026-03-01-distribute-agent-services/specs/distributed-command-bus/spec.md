## ADDED Requirements

### Requirement: CommandBus SHALL support dispatching commands across process boundaries
A `DistributedCommandBus` implementation SHALL exist that serializes commands and dispatches them to remote agent processes via RabbitMQ RPC. It SHALL implement the same `CommandBus` abstract interface (`domain/command_bus.py`) as the existing in-memory implementation.

#### Scenario: Command dispatched to remote agent
- **WHEN** the API process dispatches a `ModelingCommand` via the `DistributedCommandBus`
- **AND** the DataArchitect agent is running in a separate container
- **THEN** the command SHALL be serialized to JSON, sent via RabbitMQ RPC to the `data_architect` queue, and the response SHALL be deserialized and returned to the caller

#### Scenario: Remote agent processes command and returns result
- **WHEN** a remote agent receives a serialized command via RabbitMQ RPC
- **THEN** the agent SHALL deserialize the command, dispatch it to its local handler, and return the serialized result via the RPC response

#### Scenario: Remote agent is unreachable
- **WHEN** a command is dispatched to a remote agent that is not running
- **AND** the RPC call times out after the configured timeout (default 30 seconds)
- **THEN** the `DistributedCommandBus` SHALL raise a `CommandDispatchError` with the target agent role and command type

### Requirement: Commands SHALL be serializable for distributed dispatch
All `Command` subclasses that need distributed dispatch SHALL be serializable to JSON and deserializable back to the original type. A command registry SHALL map command type names to their Python classes for deserialization.

#### Scenario: ModelingCommand round-trips through serialization
- **WHEN** a `ModelingCommand` is serialized to JSON and then deserialized
- **THEN** the resulting object SHALL be equal to the original command with all fields preserved

#### Scenario: Unknown command type fails deserialization
- **WHEN** a message with command type `"UnknownCommand"` is received
- **THEN** deserialization SHALL raise a `CommandDeserializationError` with the unknown type name

### Requirement: Deployment mode SHALL determine CommandBus implementation
The system SHALL select the `CommandBus` implementation based on the `deployment_mode` in agent configuration. `local` mode SHALL use the existing in-memory `CommandBus`. `distributed` mode SHALL use the `DistributedCommandBus` backed by RabbitMQ RPC.

#### Scenario: Local mode uses in-memory CommandBus
- **WHEN** `config/agents.yaml` has `deployment_mode: local`
- **THEN** `bootstrap_command_bus()` SHALL return the existing in-memory `CommandBus`

#### Scenario: Distributed mode uses RabbitMQ CommandBus
- **WHEN** `config/agents.distributed.yaml` has `deployment_mode: distributed`
- **THEN** `bootstrap_command_bus()` SHALL return a `DistributedCommandBus` connected to RabbitMQ

### Requirement: Each agent SHALL register its command handlers on startup
When an agent starts in distributed mode, it SHALL register RPC handlers on RabbitMQ for all commands it can handle. The RPC queue name SHALL follow the pattern `cmd_<agent_role>` so callers can route commands to the correct agent.

#### Scenario: DataArchitect registers its handlers
- **WHEN** the DataArchitect agent starts in distributed mode
- **THEN** it SHALL create an RPC consumer on queue `cmd_data_architect` that accepts `ModelingCommand` and routes it to the registered handler

#### Scenario: Command routed to correct agent queue
- **WHEN** the API dispatches a `GenerateMetadataCommand`
- **THEN** the `DistributedCommandBus` SHALL send it to queue `cmd_data_engineer` based on a command-to-agent routing table
