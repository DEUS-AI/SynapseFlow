## Why

FastAPI's `@app.on_event("startup")` decorator is deprecated since Starlette 0.26+ / FastAPI 0.93+. It emits a `DeprecationWarning` on every server start and will be removed in a future version. The recommended replacement is the `lifespan` async context manager pattern, which also supports shutdown cleanup in a single function.

## What Changes

- **Replace `@app.on_event("startup")` with a `lifespan` async context manager** that runs the same initialization logic
- **Pass the `lifespan` parameter to `FastAPI()`** constructor instead of using the decorator
- **Remove the `@app.on_event("startup")` decorated function**

## Capabilities

### New Capabilities
- `fastapi-lifespan`: Covers the migration from deprecated `on_event` startup handler to the `lifespan` context manager pattern

### Modified Capabilities
_(None — this is a purely internal structural change with no spec-level behavior changes)_

## Impact

- **Backend API** (1 file):
  - `src/application/api/main.py` — single `@app.on_event("startup")` handler at line 75, and `FastAPI()` constructor at line 34
- **Dependencies**: None. Uses only FastAPI's built-in `lifespan` parameter (available since FastAPI 0.93+)
- **Risk**: Low. The initialization logic (layer services, crystallization pipeline, hypergraph analytics) stays identical — only the wrapper changes from decorator to context manager.
- **Tests**: No test changes expected since the startup logic itself doesn't change.
