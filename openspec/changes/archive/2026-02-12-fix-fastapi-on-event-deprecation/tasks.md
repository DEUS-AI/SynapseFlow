## 1. Add import

- [x] 1.1 Add `from contextlib import asynccontextmanager` to module imports in `src/application/api/main.py`

## 2. Create lifespan context manager

- [x] 2.1 Define `@asynccontextmanager async def lifespan(app)` function above the `app = FastAPI(...)` constructor, containing the startup initialization logic (layer services, crystallization pipeline, hypergraph analytics) with a `yield` after initialization
- [x] 2.2 Pass `lifespan=lifespan` to the `FastAPI()` constructor

## 3. Remove deprecated handler

- [x] 3.1 Remove the `@app.on_event("startup")` decorator and `startup_event()` function

## 4. Verification

- [x] 4.1 Verify no `on_event` references remain in `src/application/api/main.py`
- [x] 4.2 Run existing tests to confirm no regressions
