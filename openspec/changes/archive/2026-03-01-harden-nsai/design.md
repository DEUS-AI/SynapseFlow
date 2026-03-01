## Context

The ReasoningEngine (`reasoning_engine.py`, ~1800 lines) is the core of SynapseFlow's neurosymbolic AI system. It has 19 rules across 3 action categories (`create_entity`, `create_relationship`, `chat_query`), 3 reasoning strategies (`neural_first`, `symbolic_first`, `collaborative`), and confidence/provenance tracking. Despite being central, it has zero dedicated tests and 71 hardcoded numeric thresholds scattered across its methods.

Across all NSAI components, only 8.5% of thresholds (8 out of 94) are in config objects. The `AutomaticLayerTransitionService` is the gold standard — fully config-driven via `PromotionThresholds` dataclass, with 56+ tests. The rest of the NSAI stack doesn't follow this pattern.

The LLMReasoner has 2 hardcoded confidence values (0.7, 0.8) and the ValidationEngine has 4 hardcoded limits (100, 1000, 50, confidence bounds). These are smaller but follow the same scattered-threshold anti-pattern.

## Goals / Non-Goals

**Goals:**
- Test the ReasoningEngine's public API and pure-logic rules without requiring external services
- Extract all hardcoded thresholds into injectable config dataclasses with backward-compatible defaults
- Add structured logging so rule execution, confidence flow, and strategy decisions are observable

**Non-Goals:**
- Refactoring the ReasoningEngine's internal structure (rule organization, strategy pattern, etc.)
- Adding new reasoning capabilities or rules
- Testing LLM-dependent code paths (neural rules that require Graphiti)
- Changing any threshold values — defaults must exactly match current hardcoded values
- Adding metrics export (Prometheus, StatsD, etc.) — just structured logging for now
- Modifying MedicalRulesEngine or EntityResolver thresholds (already better covered)

## Decisions

### D1: Config dataclass pattern — follow AutomaticLayerTransition

**Decision:** Use `@dataclass` with default values, injected via constructor with `config=None` defaulting to `ReasoningEngineConfig()`.

**Rationale:** `PromotionThresholds` in `automatic_layer_transition.py` already establishes this exact pattern. Constructor gains `config: Optional[ReasoningEngineConfig] = None` — if None, uses defaults. Zero breaking changes.

**Alternatives considered:**
- Environment variables: Too many (71 values), poor grouping
- YAML/JSON config file: Overkill for internal tuning, adds file dependency
- Registry/dict pattern: Loses type safety and IDE autocomplete

### D2: Group thresholds into sub-configs with a top-level composite

**Decision:** Create sub-dataclasses for natural threshold clusters, composed into a top-level `ReasoningEngineConfig`:

```python
@dataclass
class ConfidenceThresholds:
    property_inference_id_pattern: float = 0.8
    property_inference_person: float = 0.7
    ...

@dataclass
class ScoringConfig:
    base_availability_score: float = 0.5
    entity_boost_per_item: float = 0.1
    max_entity_boost_items: int = 3
    ...

@dataclass
class ReasoningEngineConfig:
    confidence: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    cross_layer: CrossLayerConfig = field(default_factory=CrossLayerConfig)
```

**Rationale:** Flat dataclass with 71 fields would be unwieldy. Sub-configs group thresholds by concern, making it easier to override just what matters.

### D3: Test pure-logic rules directly, mock backend for graph rules

**Decision:** Test rules like `_infer_properties`, `_classify_entity`, `_suggest_inverse_relationship`, `_validate_relationship_logic`, `_assess_data_availability`, `_score_answer_confidence` as unit tests with real `KnowledgeEvent` objects and no mocks. For rules that call `self.backend` (transitive closure, cross-layer queries), use `AsyncMock` on the backend.

**Rationale:** The pure-logic rules are immediately testable — they take a `KnowledgeEvent` and return dicts. No external dependencies. The backend-calling rules need a mock, but the mock surface is small (`list_relationships`, `query_raw`). LLM-dependent rules (`_llm_semantic_inference`, `_infer_semantic_links`) are out of scope — they early-return `None` when `llm=None`, which is itself testable.

### D4: Structured logging via stdlib `logging` with rule execution context

**Decision:** Add `logger.info()` calls at key points in the reasoning pipeline:
- When a strategy is selected (with action type)
- When each rule fires (with rule name, confidence values)
- Summary after all rules complete (count of inferences, suggestions, warnings)

Use existing `logger = logging.getLogger(__name__)` — no new dependencies.

**Rationale:** The engine already has `logger` but only uses it for init messages. Adding structured info at rule execution points makes the reasoning pipeline observable through standard log aggregation. No new dependencies, no performance cost when logging is filtered.

### D5: LLMReasoner and ValidationEngine get minimal configs

**Decision:** Add `LLMReasonerConfig` (2 fields) and `ValidationLimits` (3 fields) dataclasses in their respective files. Same pattern: `config=None` defaults to fresh instance.

**Rationale:** Small enough to not warrant sub-configs, but still worth extracting to complete the threshold centralization.

## Risks / Trade-offs

- **Large config surface** — 71 thresholds is a lot of config fields. Mitigated by sub-configs and keeping defaults identical to current values. Nobody needs to set any of these unless they want to tune.
- **Test maintenance** — ReasoningEngine tests will be coupled to the rule output format (dicts with specific keys). Mitigated by testing through the public API (`apply_reasoning`) where possible, and keeping rule-level tests focused on behavior not shape.
- **Logging noise** — Adding info-level logs to every rule execution could be noisy. Mitigated by using DEBUG level for per-rule logs and INFO only for strategy selection and summary.
