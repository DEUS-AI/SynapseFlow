## ADDED Requirements

### Requirement: Application uses lifespan context manager for startup initialization
The FastAPI application SHALL use an async `lifespan` context manager passed to the `FastAPI()` constructor to run startup initialization logic, instead of the deprecated `@app.on_event("startup")` decorator.

#### Scenario: Startup initialization runs via lifespan
- **WHEN** the FastAPI application starts
- **THEN** the lifespan context manager SHALL execute all initialization steps (layer services, crystallization pipeline, hypergraph analytics) before yielding control to the application

#### Scenario: No deprecated on_event decorator present
- **WHEN** inspecting the application module
- **THEN** there SHALL be zero uses of `@app.on_event("startup")` or `@app.on_event("shutdown")`

### Requirement: Initialization behavior is preserved
The lifespan context manager SHALL execute the same initialization logic in the same order as the previous `startup_event` function, with identical error handling (non-fatal warnings that allow the API to continue).

#### Scenario: Layer services initialization failure is non-fatal
- **WHEN** `initialize_layer_services()` raises an exception during startup
- **THEN** the application SHALL log a warning and continue starting

#### Scenario: Crystallization pipeline initialization failure is non-fatal
- **WHEN** `initialize_crystallization_pipeline()` raises an exception during startup
- **THEN** the application SHALL log a warning and continue starting

#### Scenario: Hypergraph analytics initialization failure is non-fatal
- **WHEN** hypergraph analytics initialization raises an exception during startup
- **THEN** the application SHALL log a warning and continue starting
