# Services Setup Guide

This document explains which services need to be running for all tests to pass.

## Required Services

### 1. Neo4j Database

**Purpose**: Knowledge graph storage and Neo4j integration tests

**Configuration** (from `neo4j_config.env`):
- URI: `bolt://localhost:7687`
- Username: `neo4j`
- Password: `password`

**Quick Start with Docker**:
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Verify Connection**:
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Or test connection
python setup_neo4j_demo.py
```

**Tests Affected**: `tests/test_neo4j_connection.py` (1 test)

---

### 2. RabbitMQ Message Broker

**Purpose**: Distributed event bus for agent communication

**Configuration**:
- Connection: `amqp://localhost:5672`
- Management UI: `http://localhost:15672` (guest/guest)

**Quick Start with Docker**:
```bash
docker run -d \
  --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3-management
```

**Verify Connection**:
```bash
# Check if RabbitMQ is running
docker ps | grep rabbitmq

# Access management UI
open http://localhost:15672
# Login: guest / guest
```

**Tests Affected**: `tests/test_rabbitmq_event_bus.py` (8 tests)

---

### 3. MarkItDown PDF Support (Optional)

**Purpose**: PDF document parsing for DDA documents

**Installation**:
```bash
uv pip install markitdown[pdf]
```

**Tests Affected**: `tests/application/test_markitdown_wrapper.py` (1 test)

---

## Quick Setup Script

Create a `docker-compose.yml` for easy service management:

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:latest
    container_name: neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  rabbitmq:
    image: rabbitmq:3-management
    container_name: rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=guest
      - RABBITMQ_DEFAULT_PASS=guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

volumes:
  neo4j_data:
  neo4j_logs:
  rabbitmq_data:
```

**Start all services**:
```bash
docker-compose up -d
```

**Stop all services**:
```bash
docker-compose down
```

**View logs**:
```bash
docker-compose logs -f
```

---

## Test Status Summary

### Without Services Running:
- ✅ **187 tests PASS** (all core functionality works)
- ❌ **10 tests FAIL** (require external services)

### With Services Running:
- ✅ **197 tests PASS** (all tests pass)

---

## Notes

1. **For Development**: You can run most tests without these services. Only integration tests require them.

2. **For CI/CD**: Consider using test containers or mocking these services in CI pipelines.

3. **For Production**: Both Neo4j and RabbitMQ are required for full functionality.

4. **Skip Integration Tests**: Run tests excluding integration tests:
   ```bash
   pytest -m "not integration"
   ```

