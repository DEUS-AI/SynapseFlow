## 1. Dependency Upgrade

- [x] 1.1 Update `pyproject.toml`: change `"graphiti-core[falkordb]"` to `"graphiti-core[falkordb] >=0.27.1,<0.28"`
- [x] 1.2 Run `uv sync` and verify resolution succeeds without conflicts
- [x] 1.3 Run `uv pip check` to confirm no broken transitive dependencies

## 2. Import and API Compatibility

- [x] 2.1 Run `uv run python -c "from graphiti_core import Graphiti; from graphiti_core.search.search import search; from graphiti_core.search.search_config import SearchResults; from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER; from graphiti_core.search.search_filters import SearchFilters; from graphiti_core.nodes import EpisodeType, EpisodicNode, EntityNode; from graphiti_core.edges import EntityEdge; from graphiti_core.driver.falkordb_driver import FalkorDriver; print('All imports OK')"` to verify all import paths still resolve
- [x] 2.2 Fix any import path changes (if 2.1 fails)

## 3. Test Suite

- [x] 3.1 Run `uv run pytest tests/test_episodic_memory.py -v` and verify all episodic memory tests pass
- [x] 3.2 Run `uv run pytest tests/ -v` full test suite and fix any failures caused by the upgrade
- [x] 3.3 Review mocks in `tests/test_episodic_memory.py` — update any mock return values if internal search helpers now return `tuple[list, list[float]]` instead of `list`

## 4. Integration Verification

- [x] 4.1 Start FalkorDB container (`docker-compose -f docker-compose.services.yml up -d`)
- [x] 4.2 Smoke-test episode search: call `search_episodes()` with a patient_id and verify no `RediSearch: Syntax error` in logs
- [x] 4.3 Verify `build_indices_and_constraints()` still works on service initialization
