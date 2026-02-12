.PHONY: install test lint format clean dev-install precommit build \
       clear-memory clear-demo-memory backend frontend services services-stop services-logs

install:
	uv pip install --system -e .[develop]

dev-install:
	uv pip install -e .[develop]

test:
	pytest

lint:
	ruff check .

format:
	black .
	ruff check --fix .

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

precommit:
	pre-commit run --all-files

build:
	echo "Build placeholder"

run:
	@ROLE=$${ROLE:-arx}; \
	docker build -f Dockerfile.$${ROLE} -t multi-agent-system-$${ROLE} . && \
	docker run --rm multi-agent-system-$${ROLE}

# ============================================
# Memory Management
# ============================================

# Clear all memories for a specific patient (usage: make clear-memory PATIENT=patient:demo)
clear-memory:
	@PATIENT_ID=$${PATIENT:-patient:demo}; \
	echo "Clearing memories for patient: $$PATIENT_ID"; \
	uv run python scripts/clear_patient_memories.py "$$PATIENT_ID"

# Shortcut: Clear demo patient memories (most common use case)
clear-demo-memory:
	@echo "Clearing all memories for patient:demo..."
	uv run python scripts/clear_patient_memories.py patient:demo

# ============================================
# Development Services
# ============================================

# Start the backend API server
backend:
	uv run uvicorn src.application.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start the frontend dev server
frontend:
	cd frontend && npm run dev

# Start required Docker services (Neo4j, Redis, Qdrant, FalkorDB)
services:
	docker-compose -f docker-compose.services.yml up -d
	docker-compose -f docker-compose.memory.yml up -d
	@echo "✅ Services started: Neo4j (7687), Redis (6380), Qdrant (6333), FalkorDB (6379)"

# Stop all Docker services
services-stop:
	docker-compose -f docker-compose.services.yml down
	docker-compose -f docker-compose.memory.yml down

# View service logs
services-logs:
	docker-compose -f docker-compose.services.yml logs -f
