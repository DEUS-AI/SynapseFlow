.PHONY: install test lint format clean dev-install precommit build \
       clear-memory clear-demo-memory reset-all reset-dry-run \
       backend frontend services services-stop services-logs \
       deploy-frontend-swa

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

# Full reset — clear ALL derived data stores (requires --confirm)
reset-all:
	@echo "Resetting ALL SynapseFlow data stores..."
	uv run python scripts/maintenance/full_reset.py --confirm

# Preview what reset-all would clear (no deletions)
reset-dry-run:
	uv run python scripts/maintenance/full_reset.py

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
	docker compose -f docker-compose.services.yml up -d
	docker compose -f docker-compose.memory.yml up -d
	@echo "✅ Services started: Neo4j (7687), Redis (6380), Qdrant (6333), FalkorDB (6379)"

# Stop all Docker services
services-stop:
	docker compose -f docker-compose.services.yml down
	docker compose -f docker-compose.memory.yml down

# View service logs
services-logs:
	docker compose -f docker-compose.services.yml logs -f

# ============================================
# Azure Deployment
# ============================================

# Deploy frontend to Azure Static Web App
deploy-frontend-swa:
	cd frontend && npm ci && PUBLIC_API_URL=https://20-50-212-98.nip.io npm run build
	cp frontend/staticwebapp.config.json frontend/dist/client/
	npx @azure/static-web-apps-cli deploy frontend/dist/client \
		--env production \
		--deployment-token $$(az keyvault secret show --vault-name kv-odin-dev-we --name swa-deployment-token --query value -o tsv)
