# Demos Directory

This directory contains demonstration scripts showcasing the SynapseFlow neurosymbolic knowledge management system.

## Available Demos

### Main Demos

- **`run_full_demo.py`** - Complete end-to-end demonstration including all phases
- **`demo_presentation.py`** - Interactive presentation demo with API showcase
- **`multi_agent_dda_demo.py`** - Multi-agent collaboration demo
- **`live_api_demo.py`** - Live API demonstration

### Specialized Demos

- **`demo_metadata_query.py`** - Metadata querying capabilities
- **`setup_neo4j_demo.py`** - Neo4j backend setup and demo
- **`demo_config.py`** - Demo configuration utilities

## Running Demos

### Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (copy `.env.example` to `.env`):
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Optional: Start backend services**:
   ```bash
   # For Neo4j
   docker-compose -f docker-compose.services.yml up neo4j

   # For FalkorDB
   docker-compose -f docker-compose.services.yml up falkordb
   ```

### Quick Start

Run the main demo:
```bash
python demos/run_full_demo.py
```

Run the presentation demo:
```bash
python demos/demo_presentation.py
```

## Demo Features

Each demo showcases different aspects of the system:

- ✅ **Phase 1**: Entity extraction, semantic normalization, deduplication
- ✅ **Phase 2**: Neurosymbolic integration, confidence tracking, validation
- ✅ **Phase 3**: Layer transitions, cross-layer reasoning, lineage tracking
- ✅ **Multi-agent**: Agent collaboration and event-driven architecture
- ✅ **API**: REST API operations and knowledge graph queries

## Creating New Demos

To create a new demo:

1. Create a new Python file in this directory
2. Import necessary components from `src/`
3. Follow the pattern from existing demos
4. Add entry to this README

Example structure:
```python
#!/usr/bin/env python3
"""My Custom Demo"""

import asyncio
from src.composition_root import bootstrap_knowledge_management

async def run_demo():
    # Your demo logic here
    pass

if __name__ == "__main__":
    asyncio.run(run_demo())
```

## Troubleshooting

- **Import errors**: Make sure you're running from the project root
- **Backend connection errors**: Check that services are running
- **Missing dependencies**: Run `pip install -r requirements.txt`

For more help, see the main [README.md](../README.md)
