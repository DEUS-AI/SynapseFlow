# Manual Tests Directory

This directory contains ad-hoc and exploratory test scripts that were used during development.

## ⚠️ Important Note

These are **manual/exploratory tests**, not part of the automated test suite. For automated tests, see the main `tests/` directory.

## Available Test Scripts

### API Tests
- **`test_api.py`** - Manual API endpoint testing
- **`test_e2e_flow.py`** - End-to-end flow testing

### Backend Tests
- **`test_direct_writer.py`** - Direct graph writer testing
- **`test_falkor_labels.py`** - FalkorDB label testing
- **`test_falkor_query.py`** - FalkorDB query testing
- **`test_falkor_simple.py`** - Simple FalkorDB operations
- **`test_modeling.py`** - Domain modeling testing

### Component Tests
- **`test_llm_reasoning.py`** - LLM reasoning component testing
- **`test_metadata_debug.py`** - Metadata generation debugging

## Usage

These scripts are typically run individually for debugging or exploration:

```bash
# From project root
python tests/manual/test_api.py
python tests/manual/test_e2e_flow.py
```

## Difference from Automated Tests

| Automated Tests (`tests/`) | Manual Tests (`tests/manual/`) |
|----------------------------|--------------------------------|
| Run via pytest | Run directly with python |
| Part of CI/CD | Not in CI/CD |
| Isolated & repeatable | May require setup |
| Uses fixtures & mocks | May use real backends |
| Fast execution | Can be slow |

## Migration to Automated Tests

If a manual test proves valuable, consider converting it to an automated test:

1. Extract test logic
2. Add pytest fixtures
3. Use mocks for external dependencies
4. Move to appropriate `tests/` subdirectory
5. Add to test suite

## Maintenance

These tests may:
- Become outdated as code evolves
- Require manual setup (databases, APIs)
- Have hardcoded values or paths
- Not follow strict testing conventions

Use them as starting points for exploration, not as reliable regression tests.

## Related Documentation

- [Main Test Suite](../README.md) - Automated test documentation
- [Contributing Guide](../../CONTRIBUTING.md) - How to write tests
- [Architecture](../../docs/ARCHITECTURE.md) - System architecture

## Questions?

For questions about these tests or to propose new automated tests, please open an issue or contact the development team.
