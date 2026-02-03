# Demo Organization & End-to-End Demo Proposal

## Executive Summary

This document proposes a comprehensive reorganization of demo and test files currently scattered in the root directory, along with a unified end-to-end demo strategy that showcases the complete neurosymbolic knowledge management system across all three phases.

---

## Current State Analysis

### Root Directory Clutter (37 Python files)

**Test Files** (should be in `tests/` directory):
- `test_api.py`
- `test_direct_writer.py`
- `test_e2e_flow.py`
- `test_falkor_labels.py`
- `test_falkor_query.py`
- `test_falkor_simple.py`
- `test_llm_reasoning.py`
- `test_metadata_debug.py`
- `test_modeling.py`

**Verification/Inspection Scripts** (utility scripts):
- `check_graphs.py`
- `check_neo4j_data.py`
- `inspect_architecture.py`
- `inspect_falkordb.py`
- `inspect_neo4j.py`
- `verify_hybrid_ontology.py`
- `verify_metadata_enhancement.py`
- `verify_neo4j_backend.py`
- `verify_relationship_densification.py`

**Cleanup Scripts** (maintenance):
- `clear_falkordb.py`
- `clear_neo4j.py`

**Exploration Scripts** (development/debugging):
- `explore_graphiti.py`
- `explore_graphiti_structure.py`
- `debug_parser.py`

**Demo Scripts** (actual demos):
- `demo_presentation.py`
- `demo_metadata_query.py`
- `demo_config.py`
- `run_full_demo.py`
- `live_api_demo.py`
- `multi_agent_dda_demo.py`
- `setup_neo4j_demo.py`

**Batch Processing Scripts**:
- `process_all_ddas.py`
- `process_all_metadata.py`
- `process_batch_test.py`
- `enrich_all_domains.py`
- `generate_dda_documents.py`

**Query Scripts**:
- `run_all_queries.py`
- `run_neo4j_queries.py`

---

## Proposed New Structure

```
Notebooks/
├── demos/                          # ← NEW: All demo scripts
│   ├── __init__.py
│   ├── README.md                   # Demo documentation
│   ├── e2e_neurosymbolic_demo.py  # ← NEW: Main unified demo
│   ├── phase1_semantic_demo.py    # Phase 1 features
│   ├── phase2_integration_demo.py # Phase 2 features
│   ├── phase3_layer_demo.py       # Phase 3 features
│   ├── api_demo.py                # REST API demo
│   └── multi_agent_demo.py        # Multi-agent collaboration
│
├── scripts/                        # ← NEW: Utility scripts
│   ├── inspection/
│   │   ├── check_graphs.py
│   │   ├── inspect_neo4j.py
│   │   ├── inspect_falkordb.py
│   │   └── verify_ontology.py
│   ├── maintenance/
│   │   ├── clear_neo4j.py
│   │   ├── clear_falkordb.py
│   │   └── setup_backends.py
│   ├── batch/
│   │   ├── process_all_ddas.py
│   │   ├── enrich_domains.py
│   │   └── generate_metadata.py
│   └── dev/
│       ├── explore_graphiti.py
│       └── debug_parser.py
│
├── tests/                          # Existing test directory
│   ├── manual/                     # ← NEW: Manual/ad-hoc tests
│   │   ├── test_api.py            # Moved from root
│   │   ├── test_e2e_flow.py       # Moved from root
│   │   └── test_backends.py       # Combined backend tests
│   └── ... (existing test structure)
│
├── examples/                       # Existing DDAs
│   └── ... (unchanged)
│
└── docs/                           # ← NEW: Documentation
    ├── DEMO_GUIDE.md              # How to run demos
    ├── ARCHITECTURE.md            # System architecture
    └── API_REFERENCE.md           # API documentation
```

---

## Unified End-to-End Demo Strategy

### Demo Name: **"SynapseFlow: Neurosymbolic Knowledge Management Journey"**

### Demo Flow

The demo will showcase a complete journey from raw data to intelligent insights across all three phases:

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: SEMANTIC LAYER                                     │
│  ─────────────────────────                                   │
│  Input: Healthcare DDA (Crohn's Disease)                     │
│  ├─→ Entity Extraction (Tables, Columns)                     │
│  ├─→ Semantic Normalization (abbreviations, synonyms)        │
│  ├─→ Entity Resolution (deduplication)                       │
│  └─→ Canonical Concept Registry                              │
│                                                               │
│  Output: Normalized, deduplicated PERCEPTION layer entities  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: NEUROSYMBOLIC INTEGRATION                         │
│  ──────────────────────────────────                          │
│  ├─→ Business Concept Inference (LLM)                        │
│  ├─→ Confidence Scoring (adaptive alpha)                     │
│  ├─→ Semantic Grounding (hybrid search)                      │
│  ├─→ Symbolic Validation (SHACL)                            │
│  └─→ Feedback Integration (drift detection)                  │
│                                                               │
│  Output: Validated SEMANTIC layer with confidence scores     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: LAYER TRANSITIONS & CROSS-LAYER REASONING        │
│  ────────────────────────────────────────────────            │
│  ├─→ PERCEPTION → SEMANTIC transition                        │
│  │   ├─ Infer business concepts from data structure          │
│  │   └─ Validate semantic properties                         │
│  ├─→ SEMANTIC → REASONING transition                         │
│  │   ├─ Derive quality rules                                 │
│  │   └─ Track confidence & provenance                        │
│  ├─→ REASONING → APPLICATION transition                      │
│  │   ├─ Suggest query patterns                               │
│  │   └─ Generate optimization recommendations                │
│  └─→ APPLICATION feedback loop                               │
│      └─ Identify data gaps, recommend improvements           │
│                                                               │
│  Output: Complete DIKW hierarchy with lineage tracking       │
└─────────────────────────────────────────────────────────────┘
```

### Demo Script Structure

```python
# demos/e2e_neurosymbolic_demo.py

class NeurosymbolicDemo:
    """
    End-to-end demonstration of the complete neurosymbolic system.

    Demonstrates:
    - Entity extraction & normalization (Phase 1)
    - Neural-symbolic integration (Phase 2)
    - Layer transitions & cross-layer reasoning (Phase 3)
    - Knowledge lineage & provenance tracking
    """

    def __init__(self, backend_type="graphiti"):
        self.setup_backend(backend_type)
        self.metrics = DemoMetrics()

    async def run_complete_demo(self):
        """Run complete end-to-end demo."""
        print("🚀 SynapseFlow: Neurosymbolic Knowledge Journey\n")

        # Stage 1: Load & Parse DDA
        dda_path = "examples/crohns_disease_dda.md"
        self.print_stage("STAGE 1: Document Ingestion")
        parsed_dda = await self.ingest_document(dda_path)

        # Stage 2: Semantic Layer Processing (Phase 1)
        self.print_stage("STAGE 2: Semantic Layer (Phase 1)")
        normalized_entities = await self.apply_semantic_layer(parsed_dda)
        self.show_normalization_results(normalized_entities)
        self.show_entity_resolution_results(normalized_entities)

        # Stage 3: Neurosymbolic Integration (Phase 2)
        self.print_stage("STAGE 3: Neurosymbolic Integration (Phase 2)")
        enriched_concepts = await self.apply_neurosymbolic_integration(normalized_entities)
        self.show_confidence_scores(enriched_concepts)
        self.show_semantic_grounding_results(enriched_concepts)

        # Stage 4: Layer Transitions (Phase 3)
        self.print_stage("STAGE 4: Layer Transitions (Phase 3)")
        await self.demonstrate_layer_transitions(enriched_concepts)

        # Stage 5: Cross-Layer Reasoning
        self.print_stage("STAGE 5: Cross-Layer Reasoning")
        await self.demonstrate_cross_layer_reasoning()

        # Stage 6: Query & Analytics
        self.print_stage("STAGE 6: Knowledge Queries")
        await self.demonstrate_queries()

        # Final Summary
        self.print_summary()

    async def demonstrate_layer_transitions(self, entities):
        """Demonstrate complete layer progression."""
        print("  📊 Transitioning entities through DIKW layers...\n")

        for entity in entities[:3]:  # Show first 3 for demo
            print(f"  Entity: {entity['name']}")

            # PERCEPTION → SEMANTIC
            print("    ├─→ PERCEPTION → SEMANTIC")
            reasoning = await self.cross_layer_reasoning(entity, "PERCEPTION")
            print(f"    │   └─ Inferred: {reasoning['inferences'][0]['concept']}")

            transition = await self.execute_transition(
                entity, "PERCEPTION", "SEMANTIC"
            )
            print(f"    │   └─ Status: {transition.status}")

            # SEMANTIC → REASONING
            print("    ├─→ SEMANTIC → REASONING")
            quality_rules = await self.cross_layer_reasoning(entity, "SEMANTIC")
            print(f"    │   └─ Quality rules: {len(quality_rules['inferences'])}")

            # REASONING → APPLICATION
            print("    └─→ REASONING → APPLICATION")
            query_patterns = await self.cross_layer_reasoning(entity, "REASONING")
            print(f"        └─ Query patterns: {len(query_patterns['inferences'])}")

            print()

    def print_summary(self):
        """Print demo summary with metrics."""
        print("\n" + "="*60)
        print("  📊 DEMO SUMMARY")
        print("="*60)

        print(f"\n  Phase 1 (Semantic Layer):")
        print(f"    • Entities extracted: {self.metrics.entities_extracted}")
        print(f"    • Duplicates resolved: {self.metrics.duplicates_resolved}")
        print(f"    • Normalization rate: {self.metrics.normalization_rate:.1%}")

        print(f"\n  Phase 2 (Neurosymbolic Integration):")
        print(f"    • Concepts inferred: {self.metrics.concepts_inferred}")
        print(f"    • Average confidence: {self.metrics.avg_confidence:.2f}")
        print(f"    • Validation success rate: {self.metrics.validation_rate:.1%}")

        print(f"\n  Phase 3 (Layer Transitions):")
        print(f"    • Transitions completed: {self.metrics.transitions_completed}")
        print(f"    • Cross-layer inferences: {self.metrics.cross_layer_inferences}")
        print(f"    • Lineage chains tracked: {self.metrics.lineage_chains}")

        print(f"\n  Knowledge Graph Statistics:")
        print(f"    • Total nodes: {self.metrics.total_nodes}")
        print(f"    • Total relationships: {self.metrics.total_relationships}")
        print(f"    • Graph density: {self.metrics.graph_density:.3f}")

        print("\n" + "="*60)
```

### Interactive Features

The demo will include:

1. **Visual Progress Indicators**
   - Progress bars for batch operations
   - Real-time entity counts
   - Confidence score distributions

2. **Colored Output**
   - Green: Successful operations
   - Yellow: Warnings/suggestions
   - Blue: Information
   - Red: Errors (if any)

3. **Pause Points**
   - Allow user to inspect intermediate results
   - Optional detailed view of each step
   - Export results to JSON/CSV

4. **Comparison Mode**
   - Before/after entity resolution
   - With/without semantic normalization
   - Neural vs symbolic results

---

## Implementation Plan

### Phase 1: Cleanup (Week 1)

1. **Create Directory Structure**
   ```bash
   mkdir -p demos scripts/{inspection,maintenance,batch,dev} docs tests/manual
   ```

2. **Move Files to New Locations**
   - Test files → `tests/manual/`
   - Demo scripts → `demos/`
   - Utility scripts → `scripts/` (by category)

3. **Update Import Paths**
   - Fix all import statements in moved files
   - Update any hardcoded paths

4. **Create Migration Script**
   ```python
   # scripts/maintenance/migrate_files.py
   # Automates the file movement and import updates
   ```

### Phase 2: Unified Demo (Week 2)

1. **Create Base Demo Framework**
   - `demos/__init__.py` with shared utilities
   - `DemoMetrics` class for tracking
   - `DemoVisualizer` for pretty output

2. **Implement Phase-Specific Demos**
   - `phase1_semantic_demo.py`
   - `phase2_integration_demo.py`
   - `phase3_layer_demo.py`

3. **Build Unified Demo**
   - `e2e_neurosymbolic_demo.py`
   - Integrates all three phases
   - Interactive CLI interface

### Phase 3: Documentation (Week 2)

1. **Create Demo Guide**
   - `docs/DEMO_GUIDE.md`
   - Prerequisites
   - Usage instructions
   - Troubleshooting

2. **Update README**
   - Add demo section
   - Link to documentation
   - Quick start guide

3. **API Documentation**
   - Generate from docstrings
   - Add examples for each endpoint

---

## Demo Execution Modes

### 1. Quick Demo (5 minutes)
```bash
python demos/e2e_neurosymbolic_demo.py --mode quick
```
- Single DDA (sample)
- Key highlights only
- Minimal output

### 2. Standard Demo (15 minutes)
```bash
python demos/e2e_neurosymbolic_demo.py --mode standard
```
- Healthcare DDA (Crohn's Disease)
- All three phases
- Detailed metrics

### 3. Full Demo (30 minutes)
```bash
python demos/e2e_neurosymbolic_demo.py --mode full
```
- Multiple DDAs
- Comparative analysis
- Export results

### 4. Interactive Mode
```bash
python demos/e2e_neurosymbolic_demo.py --interactive
```
- Step-by-step execution
- User can inspect at each stage
- Modify parameters on-the-fly

---

## Benefits of Proposed Structure

### For Development
✅ **Clear separation** between tests, demos, and utilities
✅ **Easier navigation** - logical grouping by purpose
✅ **Better version control** - meaningful diffs
✅ **Reduced clutter** - clean root directory

### For Demonstrations
✅ **Single entry point** for complete demo
✅ **Modular demos** for specific features
✅ **Professional presentation** with metrics
✅ **Easy to showcase** progress across all phases

### For New Contributors
✅ **Clear onboarding** - know where everything is
✅ **Example-driven learning** - see it in action
✅ **Documentation-first** approach
✅ **Consistent structure** - follows best practices

---

## Migration Checklist

- [ ] Create new directory structure
- [ ] Move test files to `tests/manual/`
- [ ] Move demo files to `demos/`
- [ ] Move utility scripts to `scripts/` (categorized)
- [ ] Update all import statements
- [ ] Create `demos/README.md`
- [ ] Implement base demo framework
- [ ] Create phase-specific demos
- [ ] Build unified end-to-end demo
- [ ] Write `docs/DEMO_GUIDE.md`
- [ ] Update root `README.md`
- [ ] Test all demos
- [ ] Archive old root scripts (optional backup)
- [ ] Update `.gitignore` if needed

---

## Timeline

**Week 1: Cleanup & Organization**
- Days 1-2: Create structure, move files
- Days 3-4: Fix imports, test migrations
- Day 5: Documentation updates

**Week 2: Demo Implementation**
- Days 1-3: Base framework + phase demos
- Days 4-5: Unified E2E demo
- Weekend: Testing & refinement

---

## Next Steps

1. **Approve this proposal** ✋
2. **Execute cleanup** 🧹
3. **Implement demos** 🎬
4. **Test & iterate** 🔄
5. **Launch** 🚀

---

## Questions for Discussion

1. **Backend Preference**: Which backend should be default for demos?
   - Graphiti (cloud-based, more features)
   - Neo4j (local, visual browser)
   - In-Memory (fastest, no setup)

2. **Demo Data**: Which DDA should be the showcase example?
   - Crohn's Disease (medical domain, complex)
   - Sample DDA (simpler, generic)
   - Multiple DDAs for comparison

3. **Presentation Format**:
   - CLI-only (current)
   - Jupyter Notebook (interactive)
   - Web UI (most impressive)

4. **Export Options**:
   - JSON (structured data)
   - CSV (for analysis)
   - PDF Report (for presentations)
   - All of the above

---

**Ready to proceed?** Let me know if you'd like me to:
1. Start with the cleanup (move files)
2. Implement the unified demo first
3. Modify the proposal based on your feedback
