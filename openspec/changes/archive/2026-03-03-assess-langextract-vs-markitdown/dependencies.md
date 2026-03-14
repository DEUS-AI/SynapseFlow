## Dependency Matrix

| Task ID | Depends On | Type | Reason |
|---------|-----------|------|--------|
| 1.1 | — | — | No dependencies, first task |
| 1.2 | — | — | No dependencies, documentation only |
| 1.3 | — | — | No dependencies, directory scaffolding |
| 2.1 | 1.1 | FS | Needs langextract dependency installed |
| 2.2 | 2.1 | FS | Examples are defined within the service class |
| 2.3 | 2.2 | FS | extract_from_file() uses the examples and service structure |
| 2.4 | 2.3 | FS | Grounding mapping extends the extraction method |
| 2.5 | 2.3 | FS | Layer assignment extends the extraction method |
| 2.6 | 2.1 | FS | Import guard wraps the service module |
| 3.1 | 2.1 | FS | Tests need the service class to exist |
| 3.2 | 2.3 | FS | Tests mock the extraction flow |
| 3.3 | 2.4 | FS | Tests verify grounding metadata |
| 3.4 | 2.5 | FS | Tests verify DIKW layer assignment |
| 3.5 | 2.6 | FS | Tests verify graceful degradation |
| 4.1 | 1.3, 2.3 | FS | Benchmark needs scaffolding + working adapter |
| 4.2 | 4.1 | FS | Metrics collection extends the benchmark runner |
| 4.3 | 4.2 | FS | Overlap analysis uses collected metrics |
| 4.4 | 4.2 | FS | JSON output uses collected metrics |
| 4.5 | 4.1 | FS | Config logging extends the benchmark runner |
| 5.1 | — | — | Template is static content, no code dependency |
| 5.2 | 4.4 | FS | Report generator reads the benchmark JSON output format |
| 5.3 | 5.2 | FS | Scoring rubric is part of the report generator |
| 5.4 | 5.2 | FS | Integration gap analysis is a section in the generator |
| 5.5 | 5.3 | FS | Recommendation logic uses aggregate scores |

## Critical Path

```
1.1 → 2.1 → 2.2 → 2.3 → 4.1 → 4.2 → 4.4 → 5.2 → 5.3 → 5.5
```

This is the longest chain (10 tasks) running through: dependency setup → adapter core → benchmark harness → report generation.

## Parallel Execution Waves

### Wave 1 (no dependencies)
- 1.1 Add langextract dependency
- 1.2 Add environment variable docs
- 1.3 Create benchmark directories
- 5.1 Create report template

### Wave 2 (depends on Wave 1)
- 2.1 Create LangExtractIngestionService skeleton (needs 1.1)

### Wave 3 (depends on Wave 2)
- 2.2 Define medical extraction examples (needs 2.1)
- 2.6 Add missing package handling (needs 2.1)
- 3.1 Unit tests for initialization (needs 2.1)

### Wave 4 (depends on Wave 3)
- 2.3 Implement extract_from_file() (needs 2.2)
- 3.5 Tests for graceful degradation (needs 2.6)

### Wave 5 (depends on Wave 4)
- 2.4 Source grounding mapping (needs 2.3)
- 2.5 DIKW layer assignment (needs 2.3)
- 3.2 Tests for extraction (needs 2.3)
- 4.1 Create benchmark runner (needs 1.3, 2.3)

### Wave 6 (depends on Wave 5)
- 3.3 Tests for grounding (needs 2.4)
- 3.4 Tests for DIKW layer (needs 2.5)
- 4.2 Metrics collection (needs 4.1)
- 4.5 Config logging (needs 4.1)

### Wave 7 (depends on Wave 6)
- 4.3 Entity overlap analysis (needs 4.2)
- 4.4 JSON results output (needs 4.2)

### Wave 8 (depends on Wave 7)
- 5.2 Create report generator (needs 4.4)

### Wave 9 (depends on Wave 8)
- 5.3 Implement scoring rubric (needs 5.2)
- 5.4 Implement integration gap analysis (needs 5.2)

### Wave 10 (depends on Wave 9)
- 5.5 Implement recommendation logic (needs 5.3)

## Float / Slack

| Task ID | Float | Notes |
|---------|-------|-------|
| 1.2 | High | Documentation-only, can be done anytime before final review |
| 1.3 | Medium | Needed by Wave 5 (4.1), can slip through Waves 2-4 |
| 2.4 | Low | Off critical path but blocks 3.3; same-file as critical path tasks |
| 2.5 | Low | Off critical path but blocks 3.4; same-file as critical path tasks |
| 2.6 | Medium | Off critical path, only blocks 3.5 |
| 3.1-3.5 | Medium | All tests are off critical path; can follow adapter work |
| 4.3 | Low | Overlap analysis off critical path but in same file as 4.4 |
| 4.5 | Medium | Config logging is independent within the benchmark file |
| 5.1 | High | Static template, can be created anytime |
| 5.4 | Low | Off critical path but in same file as 5.3 |

## Text DAG

```
Wave 1:    [1.1]          [1.2]   [1.3]         [5.1]
             │                      │
Wave 2:    [2.1]                    │
           ┌─┼──────┐              │
Wave 3:  [2.2] [2.6] [3.1]         │
           │     │                  │
Wave 4:  [2.3] [3.5]               │
         ┌─┼──────┬─────────────────┘
Wave 5: [2.4] [2.5] [3.2]  [4.1]
          │     │          ┌─┼────┐
Wave 6: [3.3] [3.4]    [4.2]   [4.5]
                        ┌──┘
Wave 7:              [4.3] [4.4]
                             │
Wave 8:                    [5.2]
                          ┌──┼──┐
Wave 9:                [5.3]  [5.4]
                         │
Wave 10:              [5.5]
```
