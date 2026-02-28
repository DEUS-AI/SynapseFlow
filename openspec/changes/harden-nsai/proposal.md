## Why

The ReasoningEngine is the core of SynapseFlow's neurosymbolic AI — 1800 lines, 19 rules, 3 strategies — with zero dedicated tests and 71 hardcoded numeric thresholds. Across all NSAI components, only 8.5% of thresholds (8/94) live in config objects. This makes the system fragile, opaque, and difficult to tune. AutomaticLayerTransition proves the pattern works: 100% config-driven, 56+ tests — the rest of the NSAI stack should follow.

## What Changes

- Add a comprehensive test suite for the ReasoningEngine covering pure-logic rules, strategy selection, provenance tracking, and custom rule management
- Extract all 71 hardcoded thresholds from ReasoningEngine into a `ReasoningEngineConfig` dataclass with sensible defaults, following the AutomaticLayerTransition pattern
- Extract hardcoded thresholds from LLMReasoner (2) and ValidationEngine (4) into config objects
- Add structured logging to the reasoning pipeline: which rules fired, confidence values in/out, strategy selected, and inference chains

## Capabilities

### New Capabilities
- `reasoning-engine-tests`: Dedicated test suite for ReasoningEngine covering unit tests for pure-logic rules, strategy behavior, provenance, and custom rule API
- `nsai-threshold-config`: Centralized configuration for all NSAI thresholds — ReasoningEngine, LLMReasoner, and ValidationEngine — via injectable config dataclasses
- `reasoning-observability`: Structured logging and tracing for the reasoning pipeline — rule execution, confidence flow, strategy decisions

### Modified Capabilities
<!-- No existing spec-level requirements are changing — this is additive hardening -->

## Impact

- **Code**: `reasoning_engine.py`, `llm_reasoner.py`, `validation_engine.py` — constructor signatures gain optional config parameters (backward-compatible with defaults)
- **Tests**: New test file(s) under `tests/application/agents/knowledge_manager/`
- **Dependencies**: None — uses stdlib logging and existing dataclass patterns
- **APIs**: No API changes — config is internal, not exposed via REST
