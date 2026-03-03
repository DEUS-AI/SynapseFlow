## Configuration

- **Agent count**: 3
- **Total tasks**: 23
- **Tasks per agent**: ~7-8 tasks each

## Token Cost Warning

> **Multi-agent execution scales token costs.** Each agent maintains its own context window.
> With 3 agents, expect roughly 3× the token usage of a single-agent run.
> Estimated cost multiplier: **3×**

## Feasibility Assessment

3 agents maps well to the natural capability boundaries in this change:

1. **LangExtract adapter** (Groups 1+2) — core service implementation
2. **Benchmark harness** (Groups 1+4) — benchmark infrastructure and metrics
3. **Report & tests** (Groups 3+5) — adapter tests and report generation

The main cross-agent sync point is that Agent B (benchmark) and Agent C (tests) both depend on Agent A finishing the core adapter service (task 2.3). This is a single, well-defined sync point — manageable for 3 agents.

File ownership is fully isolated: each agent owns distinct files with no overlap.

## Agent Assignments

### Agent 1: adapter-core

**Tasks:**
- 1.1 Add langextract dependency to pyproject.toml
- 1.2 Add environment variable documentation
- 2.1 Create LangExtractIngestionService skeleton
- 2.2 Define medical entity extraction examples
- 2.3 Implement extract_from_file() method
- 2.4 Implement source grounding metadata mapping
- 2.5 Implement DIKW PERCEPTION layer assignment
- 2.6 Add graceful handling for missing package

**File ownership:**
- `pyproject.toml`
- `.env.example`
- `src/application/services/langextract_ingestion.py`

**Execution order:**
1.1 → 1.2 → 2.1 → 2.2 → 2.3 → 2.4 + 2.5 (parallel) → 2.6

**Cross-agent dependencies:**
- None — this agent has no upstream dependencies from other agents

### Agent 2: benchmark-harness

**Tasks:**
- 1.3 Create benchmark directories and __init__.py files
- 4.1 Create benchmark runner
- 4.2 Implement metrics collection
- 4.3 Implement entity overlap analysis
- 4.4 Implement JSON results output
- 4.5 Add configuration logging

**File ownership:**
- `tests/benchmarks/__init__.py`
- `tests/benchmarks/conftest.py`
- `tests/benchmarks/results/.gitkeep`
- `tests/benchmarks/benchmark_extraction.py`

**Execution order:**
1.3 → (wait for Agent 1 task 2.3) → 4.1 → 4.2 → 4.3 + 4.4 (parallel) → 4.5

**Cross-agent dependencies:**
- Task 4.1 depends on Agent 1 completing task 2.3 (working adapter needed for benchmark)

### Agent 3: report-and-tests

**Tasks:**
- 3.1 Unit tests for service initialization
- 3.2 Unit tests for extraction with mocked responses
- 3.3 Unit tests for source grounding mapping
- 3.4 Unit tests for DIKW layer assignment
- 3.5 Unit tests for missing package degradation
- 5.1 Create Markdown report template
- 5.2 Create report generator script
- 5.3 Implement scoring rubric
- 5.4 Implement integration gap analysis
- 5.5 Implement recommendation logic

**File ownership:**
- `tests/application/test_langextract_ingestion.py`
- `tests/benchmarks/report_template.md`
- `tests/benchmarks/generate_report.py`

**Execution order:**
5.1 (immediate) → (wait for Agent 1 task 2.1) → 3.1 → (wait for 2.3) → 3.2 → (wait for 2.4) → 3.3 → (wait for 2.5) → 3.4 → (wait for 2.6) → 3.5 → (wait for Agent 2 task 4.4) → 5.2 → 5.3 + 5.4 (parallel) → 5.5

**Cross-agent dependencies:**
- Task 3.1 depends on Agent 1 completing task 2.1 (service class exists)
- Task 3.2 depends on Agent 1 completing task 2.3 (extraction method exists)
- Task 3.3 depends on Agent 1 completing task 2.4 (grounding mapping exists)
- Task 3.4 depends on Agent 1 completing task 2.5 (DIKW assignment exists)
- Task 3.5 depends on Agent 1 completing task 2.6 (import guard exists)
- Task 5.2 depends on Agent 2 completing task 4.4 (JSON output format defined)

## File Ownership Isolation

| File | Owner Agent | Notes |
|------|-------------|-------|
| `pyproject.toml` | adapter-core | Dependency addition only |
| `.env.example` | adapter-core | Documentation update |
| `src/application/services/langextract_ingestion.py` | adapter-core | New file, sole owner |
| `tests/benchmarks/__init__.py` | benchmark-harness | New file |
| `tests/benchmarks/conftest.py` | benchmark-harness | New file |
| `tests/benchmarks/results/.gitkeep` | benchmark-harness | New file |
| `tests/benchmarks/benchmark_extraction.py` | benchmark-harness | New file, sole owner |
| `tests/application/test_langextract_ingestion.py` | report-and-tests | New file, sole owner |
| `tests/benchmarks/report_template.md` | report-and-tests | New file |
| `tests/benchmarks/generate_report.py` | report-and-tests | New file, sole owner |

No file ownership conflicts. All files are owned by exactly one agent.

## Cross-Agent Dependencies

| Waiting Agent | Blocked Task | Depends On | Owning Agent |
|---------------|-------------|------------|--------------|
| benchmark-harness | 4.1 | 2.3 (extract_from_file) | adapter-core |
| report-and-tests | 3.1 | 2.1 (service skeleton) | adapter-core |
| report-and-tests | 3.2 | 2.3 (extraction method) | adapter-core |
| report-and-tests | 3.3 | 2.4 (grounding mapping) | adapter-core |
| report-and-tests | 3.4 | 2.5 (DIKW assignment) | adapter-core |
| report-and-tests | 3.5 | 2.6 (import guard) | adapter-core |
| report-and-tests | 5.2 | 4.4 (JSON output format) | benchmark-harness |

**Summary**: Agent 1 (adapter-core) is the primary upstream dependency. Agents 2 and 3 can start their independent work immediately (1.3, 5.1) while waiting for adapter-core to complete key milestones.

## Claude Code Team Setup

To execute this plan, run `/opsx:multiagent-apply` on this change. It will automate the steps below.

Alternatively, set up the team manually:

**1. Create the team** using `TeamCreate`:
- `team_name`: `assess-langextract-vs-markitdown`
- `description`: "Assess LangExtract vs MarkItDown for document extraction quality"

**2. Populate the shared task list** using `TaskCreate` for each task:
- `subject`: task description (e.g., "1.1 Add langextract dependency")
- `description`: include the `Files:` annotation and relevant context
- `activeForm`: present-continuous form (e.g., "Adding langextract dependency")

Then use `TaskUpdate` with `addBlockedBy` to set dependency relationships, and `TaskUpdate` with `owner` to pre-assign tasks per the agent assignments above.

**3. Spawn teammates** using the `Agent` tool for each agent:
- `name`: agent name from assignments above (adapter-core, benchmark-harness, report-and-tests)
- `team_name`: `assess-langextract-vs-markitdown`
- `subagent_type`: "general-purpose"
- `isolation`: "worktree"
- `prompt`: include assigned tasks, file ownership, execution order, and cross-agent dependencies

**4. Monitor and shutdown:** Use `TaskList` to track progress. Send `shutdown_request` via `SendMessage` when all tasks are complete.
