## ADDED Requirements

### Requirement: Strategy selection logging
The ReasoningEngine SHALL log at INFO level when a reasoning strategy is selected, including the action type and strategy name.

#### Scenario: Strategy logged on apply_reasoning
- **WHEN** `apply_reasoning` is called with any strategy
- **THEN** an INFO log SHALL be emitted with the format: `"Reasoning: strategy={strategy} action={action} rules={rule_count}"`

### Requirement: Rule execution logging
The ReasoningEngine SHALL log at DEBUG level when each individual rule executes, including the rule name and whether it produced results.

#### Scenario: Rule that produces results
- **WHEN** a reasoning rule executes and returns non-None results
- **THEN** a DEBUG log SHALL be emitted with format: `"Rule fired: {rule_name} inferences={count} suggestions={count} warnings={count}"`

#### Scenario: Rule that produces no results
- **WHEN** a reasoning rule executes and returns None
- **THEN** a DEBUG log SHALL be emitted with format: `"Rule skipped: {rule_name} (no results)"`

#### Scenario: Rule that raises an exception
- **WHEN** a reasoning rule raises an exception during execution
- **THEN** a WARNING log SHALL be emitted (this already exists and SHALL be preserved)

### Requirement: Reasoning summary logging
The ReasoningEngine SHALL log a summary at INFO level after all rules have been applied for a single `apply_reasoning` call.

#### Scenario: Summary after reasoning completes
- **WHEN** `apply_reasoning` completes
- **THEN** an INFO log SHALL be emitted with format: `"Reasoning complete: strategy={strategy} action={action} rules_fired={count} inferences={count} suggestions={count} warnings={count} time={time_ms}ms"`

### Requirement: Cross-layer reasoning logging
The ReasoningEngine SHALL log at DEBUG level when cross-layer reasoning rules are applied.

#### Scenario: Cross-layer rule application
- **WHEN** `apply_cross_layer_reasoning` is called
- **THEN** a DEBUG log SHALL be emitted indicating which layer transition was evaluated and how many inferences were produced
