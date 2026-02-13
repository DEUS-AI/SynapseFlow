## Context

The application entry point (`src/application/api/main.py`) uses `@app.on_event("startup")` (line 75) to run async initialization for layer services, crystallization pipeline, and hypergraph analytics. This decorator is deprecated since Starlette 0.26+ / FastAPI 0.93+ and will be removed in a future release. The `app` object is created at module level (line 34) without a `lifespan` parameter.

## Goals / Non-Goals

**Goals:**
- Eliminate the deprecation warning by migrating to `lifespan` context manager
- Preserve identical initialization behavior and error handling

**Non-Goals:**
- Adding shutdown cleanup logic (none exists today; can be added later via the `yield` pattern)
- Refactoring the initialization logic itself

## Decisions

### 1. Define `lifespan` as an async generator above `app`

**Decision**: Define an `async def lifespan(app)` function using `contextlib.asynccontextmanager` above the `app = FastAPI(...)` line, and pass it as `lifespan=lifespan` to the constructor.

**Rationale**: The `lifespan` must be defined before `app` is created. Using `@asynccontextmanager` is the standard FastAPI pattern. The function runs startup code before `yield` and would run shutdown code after `yield` (not needed now, but the pattern is ready for future use).

**Alternative considered**: Using a raw `AsyncGenerator` protocol — rejected as less readable and not the documented pattern.

### 2. Move startup logic verbatim into lifespan

**Decision**: Move the body of the current `startup_event()` function directly into the `lifespan` function before the `yield` statement. Keep all `try/except` blocks, log messages, and initialization order unchanged.

**Rationale**: This is a pure structural migration — no behavioral changes. Keeping the code identical minimizes risk and makes the diff easy to review.

### 3. Import `asynccontextmanager` from contextlib

**Decision**: Add `from contextlib import asynccontextmanager` to the module imports.

**Rationale**: This is a stdlib import with no new dependencies. It's the standard decorator for the lifespan pattern.

## Risks / Trade-offs

- **[Low] Test interaction** — No tests directly exercise the startup event handler. The initialization functions themselves are tested independently. → No test changes required.
- **[Low] Module-level `app` reference order** — The `lifespan` function must be defined before `app = FastAPI(...)`. Since `app` is currently at line 34, the lifespan function goes between the imports and the `app` constructor. → Straightforward ordering.
