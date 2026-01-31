"""Document Quality Service.

Evaluates document quality for RAG systems using multiple metrics:
- Contextual Relevancy & Precision (RAGAS-inspired)
- Context Sufficiency
- Information Density
- Structural Clarity
- Entity Density & Coherence
- Chunking Quality (HOPE-inspired)
"""

import re
import os
import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass

from domain.quality_models import (
    DocumentQualityReport,
    ContextualRelevancyScore,
    ContextSufficiencyScore,
    InformationDensityScore,
    StructuralClarityScore,
    EntityDensityScore,
    ChunkingQualityScore,
    QualityLevel,
)
from application.services.text_chunker import TextChunk


@dataclass
class QualityConfig:
    """Configuration for quality assessment."""
    # Thresholds
    min_facts_per_chunk: int = 3
    max_redundancy_ratio: float = 0.3
    optimal_chunk_size: int = 1500
    chunk_size_tolerance: float = 0.3  # 30% deviation acceptable

    # Sample sizes
    sample_query_count: int = 5
    max_chunks_to_analyze: int = 50

    # Weights for overall score
    weights: Dict[str, float] = None

    def __post_init__(self):
        if self.weights is None:
            self.weights = {
                "contextual_relevancy": 0.25,
                "context_sufficiency": 0.20,
                "information_density": 0.15,
                "structural_clarity": 0.15,
                "entity_density": 0.15,
                "chunking_quality": 0.10,
            }


class DocumentQualityService:
    """Evaluates document quality for RAG systems."""

    def __init__(
        self,
        config: Optional[QualityConfig] = None,
        llm_client: Any = None,
        embedding_client: Any = None,
    ):
        """Initialize the quality service.

        Args:
            config: Quality assessment configuration
            llm_client: Optional LLM client for semantic analysis
            embedding_client: Optional embedding client for similarity checks
        """
        self.config = config or QualityConfig()
        self.llm_client = llm_client
        self.embedding_client = embedding_client

    async def assess_document(
        self,
        document_id: str,
        document_name: str,
        markdown_text: str,
        chunks: List[TextChunk],
        entities: Optional[List[Dict[str, Any]]] = None,
        expected_topics: Optional[List[str]] = None,
    ) -> DocumentQualityReport:
        """Perform complete quality assessment on a document.

        Args:
            document_id: Unique document identifier
            document_name: Human-readable document name
            markdown_text: Full document text in markdown format
            chunks: List of text chunks
            entities: Optional pre-extracted entities
            expected_topics: Optional list of expected topics to verify coverage

        Returns:
            DocumentQualityReport with all metrics
        """
        start_time = time.time()

        report = DocumentQualityReport(
            document_id=document_id,
            document_name=document_name,
            chunk_count=len(chunks),
            total_tokens=self._estimate_tokens(markdown_text),
        )

        # Compute individual metrics
        report.contextual_relevancy = await self._assess_contextual_relevancy(
            chunks, expected_topics
        )
        report.context_sufficiency = await self._assess_context_sufficiency(
            markdown_text, chunks, expected_topics
        )
        report.information_density = await self._assess_information_density(
            chunks
        )
        report.structural_clarity = self._assess_structural_clarity(
            markdown_text
        )
        report.entity_density = await self._assess_entity_density(
            chunks, entities
        )
        report.chunking_quality = self._assess_chunking_quality(
            chunks, markdown_text
        )

        # Compute overall score
        report.compute_overall_score(self.config.weights)

        # Generate recommendations
        report.generate_recommendations()

        report.processing_time_ms = int((time.time() - start_time) * 1000)

        return report

    async def _assess_contextual_relevancy(
        self,
        chunks: List[TextChunk],
        expected_topics: Optional[List[str]] = None,
    ) -> ContextualRelevancyScore:
        """Assess contextual relevancy and precision.

        Simulates retrieval queries and measures how well chunks respond.
        """
        score = ContextualRelevancyScore()

        if not chunks:
            return score

        # Generate sample queries from chunk content
        sample_queries = await self._generate_sample_queries(chunks, expected_topics)
        score.sample_queries = sample_queries

        if not sample_queries:
            # Can't assess without queries - use structural heuristics
            score.context_precision = 0.7  # Assume moderate
            score.context_recall = 0.7
            score.compute_f1()
            return score

        # For each query, check how many chunks are relevant
        relevant_counts = []
        total_relevant = 0

        for query in sample_queries:
            # Find chunks that contain query terms
            query_terms = set(query.lower().split())
            relevant_chunks = 0

            for chunk in chunks[:self.config.max_chunks_to_analyze]:
                chunk_terms = set(chunk.text.lower().split())
                overlap = len(query_terms & chunk_terms)
                if overlap >= len(query_terms) * 0.3:  # 30% term overlap
                    relevant_chunks += 1

            coverage = relevant_chunks / min(5, len(chunks))  # Top-5 retrieval
            score.query_coverage[query] = min(coverage, 1.0)
            total_relevant += relevant_chunks
            relevant_counts.append(relevant_chunks)

        # Precision: relevant retrieved / total retrieved
        avg_retrieved = 5  # Simulating top-5 retrieval
        avg_relevant = sum(relevant_counts) / len(relevant_counts) if relevant_counts else 0
        score.context_precision = min(avg_relevant / avg_retrieved, 1.0)

        # Recall: relevant retrieved / total relevant in corpus
        total_possible = len(chunks) * len(sample_queries)
        score.context_recall = total_relevant / total_possible if total_possible > 0 else 0.5

        score.compute_f1()

        return score

    async def _assess_context_sufficiency(
        self,
        markdown_text: str,
        chunks: List[TextChunk],
        expected_topics: Optional[List[str]] = None,
    ) -> ContextSufficiencyScore:
        """Assess whether document has sufficient context coverage."""
        score = ContextSufficiencyScore()

        # If expected topics provided, check coverage
        if expected_topics:
            score.expected_topics = expected_topics
            text_lower = markdown_text.lower()

            for topic in expected_topics:
                if topic.lower() in text_lower:
                    score.found_topics.append(topic)
                else:
                    score.missing_topics.append(topic)

            score.topic_coverage = len(score.found_topics) / len(expected_topics)
        else:
            # Extract topics from document and estimate coverage
            extracted_topics = self._extract_topics_from_text(markdown_text)
            score.expected_topics = extracted_topics
            score.found_topics = extracted_topics
            score.topic_coverage = 0.8  # Assume 80% if we can't verify

        # Check claim coverage via keyword density
        # Medical/technical documents should have specific terms
        technical_indicators = [
            "study", "research", "evidence", "treatment", "diagnosis",
            "patient", "clinical", "trial", "data", "analysis",
            "methodology", "results", "conclusion", "reference"
        ]

        indicator_count = sum(
            1 for ind in technical_indicators
            if ind in markdown_text.lower()
        )
        score.claim_coverage = min(indicator_count / len(technical_indicators), 1.0)

        # Overall completeness
        score.completeness = (score.topic_coverage + score.claim_coverage) / 2

        return score

    async def _assess_information_density(
        self,
        chunks: List[TextChunk],
    ) -> InformationDensityScore:
        """Assess information density and redundancy."""
        score = InformationDensityScore()

        if not chunks:
            return score

        # Analyze each chunk for unique facts (approximated by unique noun phrases)
        chunk_facts = []
        all_facts = []

        for chunk in chunks[:self.config.max_chunks_to_analyze]:
            # Extract "facts" as unique meaningful phrases
            facts = self._extract_facts_from_chunk(chunk.text)
            chunk_facts.append(facts)
            all_facts.extend(facts)

            # Track chunk density
            density = len(facts) / max(len(chunk.text.split()), 1) * 100
            score.chunk_densities.append(density)

            if len(facts) < self.config.min_facts_per_chunk:
                score.low_density_chunks.append(chunk.id)

        # Calculate unique facts per chunk
        unique_facts = len(set(all_facts))
        score.unique_facts_per_chunk = unique_facts / len(chunks) if chunks else 0

        # Calculate redundancy (duplicate facts)
        fact_counts = Counter(all_facts)
        duplicate_count = sum(c - 1 for c in fact_counts.values() if c > 1)
        score.redundancy_ratio = duplicate_count / len(all_facts) if all_facts else 0

        # Identify high-redundancy chunks
        for i, facts in enumerate(chunk_facts):
            redundant = sum(1 for f in facts if fact_counts[f] > 1)
            if redundant / len(facts) > 0.5 if facts else False:
                score.high_redundancy_chunks.append(chunks[i].id)

        # Signal-to-noise ratio (inverse of redundancy, bounded)
        score.signal_to_noise = 1.0 - min(score.redundancy_ratio, 0.8)

        # Information per token
        total_tokens = sum(len(c.text.split()) for c in chunks)
        score.information_per_token = (unique_facts / total_tokens * 100) if total_tokens > 0 else 0

        # Semantic density (using extracted facts as proxy for concepts)
        avg_facts_per_chunk = sum(len(f) for f in chunk_facts) / len(chunk_facts) if chunk_facts else 0
        score.semantic_density = avg_facts_per_chunk / 10  # Normalize to 0-1 range

        return score

    def _assess_structural_clarity(
        self,
        markdown_text: str,
    ) -> StructuralClarityScore:
        """Assess document structural organization."""
        score = StructuralClarityScore()

        # Extract headings with their levels
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        headings = []

        for line in markdown_text.split('\n'):
            match = re.match(heading_pattern, line.strip())
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headings.append((level, text))

        score.heading_count = len(headings)

        if not headings:
            # No headings - poor structure
            score.heading_hierarchy_score = 0.3
            score.section_coherence = 0.5
            score.logical_flow = 0.5
            return score

        score.max_depth = max(h[0] for h in headings)

        # Check hierarchy violations
        prev_level = 0
        violations = []
        orphans = 0

        for i, (level, text) in enumerate(headings):
            # Check for level jumps (e.g., H1 directly to H3)
            if level > prev_level + 1:
                violations.append({
                    "type": "level_skip",
                    "heading": text,
                    "from_level": prev_level,
                    "to_level": level,
                })

            # Check for orphan sections (deep headings without parent)
            if i == 0 and level > 1:
                orphans += 1

            prev_level = level

        score.hierarchy_violations = violations
        score.orphan_sections = orphans

        # Calculate hierarchy score
        violation_penalty = len(violations) * 0.1
        orphan_penalty = orphans * 0.15
        score.heading_hierarchy_score = max(0, 1.0 - violation_penalty - orphan_penalty)

        # Section coherence (check if content relates to headings)
        # Simplified: check if section keywords appear in content
        sections = self._split_by_headings(markdown_text)
        coherent_sections = 0

        for heading, content in sections:
            if not content.strip():
                continue

            # Check if heading keywords appear in content
            heading_words = set(heading.lower().split())
            content_words = set(content.lower().split())

            # Remove common words
            common_words = {'the', 'a', 'an', 'and', 'or', 'is', 'are', 'of', 'to', 'in', 'for'}
            heading_words -= common_words

            if heading_words & content_words:
                coherent_sections += 1
            else:
                score.incoherent_sections.append(heading)

        score.section_coherence = coherent_sections / len(sections) if sections else 0.5

        # Logical flow (simplified: check if sections follow expected patterns)
        expected_patterns = [
            ["introduction", "background", "overview"],
            ["method", "methodology", "approach"],
            ["result", "finding", "outcome"],
            ["discussion", "analysis"],
            ["conclusion", "summary"],
        ]

        pattern_matches = 0
        heading_texts = [h[1].lower() for h in headings]

        for pattern in expected_patterns:
            for term in pattern:
                if any(term in h for h in heading_texts):
                    pattern_matches += 1
                    break

        score.logical_flow = min(pattern_matches / len(expected_patterns), 1.0)

        return score

    async def _assess_entity_density(
        self,
        chunks: List[TextChunk],
        entities: Optional[List[Dict[str, Any]]] = None,
    ) -> EntityDensityScore:
        """Assess entity extraction quality and coherence."""
        score = EntityDensityScore()

        if not chunks:
            return score

        # If entities not provided, extract them heuristically
        if entities is None:
            entities = []
            for chunk in chunks[:self.config.max_chunks_to_analyze]:
                chunk_entities = self._extract_entities_heuristic(chunk.text)
                for e in chunk_entities:
                    e["chunk_id"] = chunk.id
                entities.extend(chunk_entities)

        if not entities:
            score.entity_extraction_rate = 0.0
            score.entities_per_chunk = 0.0
            return score

        score.total_entities = len(entities)

        # Count unique entities by name
        entity_names = [e.get("name", "").lower() for e in entities]
        unique_names = set(entity_names)
        score.unique_entities = len(unique_names)

        # Entities per chunk
        chunks_with_entities = len(set(e.get("chunk_id") for e in entities))
        score.entity_extraction_rate = chunks_with_entities / len(chunks)
        score.entities_per_chunk = len(entities) / len(chunks)

        # Entity consistency (same entity referenced with same name)
        name_variations = Counter(entity_names)
        inconsistent = sum(1 for name, count in name_variations.items() if count > 3)
        score.entity_consistency = 1.0 - (inconsistent / len(unique_names) if unique_names else 0)

        # Find ambiguous entities (appear with different types)
        entity_types_by_name = {}
        for e in entities:
            name = e.get("name", "").lower()
            etype = e.get("type", "unknown")
            if name not in entity_types_by_name:
                entity_types_by_name[name] = set()
            entity_types_by_name[name].add(etype)

        for name, types in entity_types_by_name.items():
            if len(types) > 1:
                score.ambiguous_entities.append(name)

        # Cross-reference score (entities appearing in multiple chunks)
        chunks_per_entity = {}
        for e in entities:
            name = e.get("name", "").lower()
            chunk_id = e.get("chunk_id")
            if name not in chunks_per_entity:
                chunks_per_entity[name] = set()
            chunks_per_entity[name].add(chunk_id)

        multi_chunk_entities = sum(1 for chunks in chunks_per_entity.values() if len(chunks) > 1)
        score.cross_reference_score = multi_chunk_entities / len(unique_names) if unique_names else 0

        # Relationship density (approximate from co-occurrence)
        # Entities appearing in same chunk are potentially related
        relationships = 0
        for chunk in chunks[:self.config.max_chunks_to_analyze]:
            chunk_entities = [e for e in entities if e.get("chunk_id") == chunk.id]
            # Each pair of entities in same chunk = potential relationship
            n = len(chunk_entities)
            relationships += n * (n - 1) // 2

        score.total_relationships = relationships
        score.relationship_density = relationships / score.unique_entities if score.unique_entities else 0

        # Ontology alignment (check if entity types are standard)
        standard_types = {
            "person", "organization", "location", "date", "medication",
            "disease", "treatment", "symptom", "procedure", "study",
            "table", "column", "concept", "process", "system"
        }

        aligned_entities = sum(
            1 for e in entities
            if e.get("type", "").lower() in standard_types
        )
        score.ontology_alignment = aligned_entities / len(entities) if entities else 0

        return score

    def _assess_chunking_quality(
        self,
        chunks: List[TextChunk],
        markdown_text: str,
    ) -> ChunkingQualityScore:
        """Assess the quality of document chunking."""
        score = ChunkingQualityScore()

        if not chunks:
            return score

        # Size distribution analysis
        sizes = [len(c.text) for c in chunks]
        mean_size = sum(sizes) / len(sizes)
        variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
        score.size_variance = variance / (mean_size ** 2) if mean_size > 0 else 1.0

        # Optimal size ratio
        optimal_min = self.config.optimal_chunk_size * (1 - self.config.chunk_size_tolerance)
        optimal_max = self.config.optimal_chunk_size * (1 + self.config.chunk_size_tolerance)

        optimal_chunks = sum(1 for s in sizes if optimal_min <= s <= optimal_max)
        score.optimal_size_ratio = optimal_chunks / len(chunks)

        # Boundary coherence (check if chunks end at sentence boundaries)
        coherent_boundaries = 0
        for chunk in chunks:
            text = chunk.text.strip()
            # Good boundaries: ends with period, question mark, or heading
            if text.endswith(('.', '!', '?', ':', '\n')) or text.endswith('#'):
                coherent_boundaries += 1
            # Also accept if it ends with a complete sentence
            elif re.search(r'\.\s*$', text):
                coherent_boundaries += 1

        score.boundary_coherence = coherent_boundaries / len(chunks)

        # Self-containment (check if chunks have subject/context)
        self_contained = 0
        for chunk in chunks:
            text = chunk.text.strip()
            # Heuristic: self-contained if starts with capital letter or heading
            # and doesn't start with pronouns or conjunctions
            start_words = ["it", "this", "that", "these", "those", "and", "but", "or", "however"]
            first_word = text.split()[0].lower() if text.split() else ""

            if first_word not in start_words or text.startswith('#'):
                self_contained += 1

        score.self_containment = self_contained / len(chunks)

        # Context preservation (check if important patterns span chunk boundaries)
        # Look for split sentences or incomplete thoughts
        context_preserved = 0
        for i, chunk in enumerate(chunks[:-1]):
            next_chunk = chunks[i + 1]

            # Check if chunk ends mid-sentence (no punctuation)
            ends_complete = chunk.text.strip()[-1] in '.!?:' if chunk.text.strip() else True

            # Check if next chunk starts with continuation
            starts_fresh = not next_chunk.text.strip()[0].islower() if next_chunk.text.strip() else True

            if ends_complete and starts_fresh:
                context_preserved += 1

        score.context_preservation = context_preserved / (len(chunks) - 1) if len(chunks) > 1 else 1.0

        # Overall retrieval quality
        score.retrieval_quality = (
            score.boundary_coherence * 0.3 +
            score.self_containment * 0.3 +
            score.context_preservation * 0.2 +
            score.optimal_size_ratio * 0.2
        )

        return score

    # --- Helper Methods ---

    async def _generate_sample_queries(
        self,
        chunks: List[TextChunk],
        expected_topics: Optional[List[str]] = None,
    ) -> List[str]:
        """Generate sample queries for relevancy testing."""
        queries = []

        # Use expected topics as queries if provided
        if expected_topics:
            queries.extend([f"What is {topic}?" for topic in expected_topics[:3]])

        # Extract key terms from chunks to create queries
        all_text = " ".join(c.text for c in chunks[:10])

        # Find noun phrases (simplified extraction)
        capitalized_terms = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', all_text)
        term_counts = Counter(capitalized_terms)

        # Top terms become queries
        for term, count in term_counts.most_common(5):
            if count >= 2 and len(term) > 3:
                queries.append(f"What is {term}?")

        return queries[:self.config.sample_query_count]

    def _extract_topics_from_text(self, text: str) -> List[str]:
        """Extract main topics from document text."""
        # Extract from headings
        heading_pattern = r'^#{1,3}\s+(.+)$'
        topics = []

        for line in text.split('\n'):
            match = re.match(heading_pattern, line.strip())
            if match:
                topics.append(match.group(1).strip())

        # Also extract prominent terms
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        word_counts = Counter(words)

        for word, count in word_counts.most_common(10):
            if count >= 3 and word not in topics:
                topics.append(word)

        return topics[:20]

    def _extract_facts_from_chunk(self, text: str) -> List[str]:
        """Extract fact-like statements from chunk text."""
        facts = []

        # Split into sentences
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            # Heuristic: sentences with specific patterns are facts
            fact_indicators = [
                r'\d+',  # Contains numbers
                r'\b(is|are|was|were|has|have|caused?|leads?|results?|shows?)\b',
                r'\b(treatment|medication|disease|patient|study|research)\b',
            ]

            for pattern in fact_indicators:
                if re.search(pattern, sentence, re.IGNORECASE):
                    # Normalize to lowercase key phrase
                    key = re.sub(r'\s+', ' ', sentence.lower()[:50])
                    facts.append(key)
                    break

        return facts

    def _extract_entities_heuristic(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using heuristic patterns."""
        entities = []

        # Find capitalized terms (potential named entities)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(pattern, text)

        seen = set()
        for match in matches:
            if match.lower() in seen:
                continue
            seen.add(match.lower())

            # Guess type based on context
            entity_type = self._guess_entity_type(match, text)

            entities.append({
                "name": match,
                "type": entity_type,
                "confidence": 0.6,
            })

        return entities[:20]  # Limit per chunk

    def _guess_entity_type(self, name: str, context: str) -> str:
        """Guess entity type based on name and context."""
        name_lower = name.lower()
        context_lower = context.lower()

        # Medical patterns
        if any(x in name_lower for x in ["disease", "syndrome", "disorder", "itis"]):
            return "disease"
        if any(x in name_lower for x in ["patient", "subject", "participant"]):
            return "person"
        if any(x in context_lower for x in ["drug", "medication", "treatment", "therapy"]):
            return "medication"
        if any(x in name_lower for x in ["study", "trial", "research"]):
            return "study"

        # Technical patterns
        if any(x in name_lower for x in ["table", "column", "schema"]):
            return "table"
        if any(x in name_lower for x in ["system", "service", "api"]):
            return "system"

        return "concept"

    def _split_by_headings(self, text: str) -> List[Tuple[str, str]]:
        """Split document into (heading, content) pairs."""
        sections = []
        current_heading = "Document"
        current_content = []

        for line in text.split('\n'):
            if re.match(r'^#{1,6}\s+', line):
                # Save previous section
                if current_content:
                    sections.append((current_heading, '\n'.join(current_content)))

                current_heading = re.sub(r'^#+\s+', '', line).strip()
                current_content = []
            else:
                current_content.append(line)

        # Don't forget last section
        if current_content:
            sections.append((current_heading, '\n'.join(current_content)))

        return sections

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (roughly 4 chars per token)."""
        return len(text) // 4


# --- Quick Assessment Function ---

async def quick_quality_check(
    markdown_text: str,
    document_name: str = "document",
) -> Dict[str, Any]:
    """Perform a quick quality check without full analysis.

    Args:
        markdown_text: Document text
        document_name: Name for identification

    Returns:
        Quick quality summary
    """
    service = DocumentQualityService()

    # Quick chunking
    from application.services.text_chunker import TextChunker
    chunker = TextChunker()
    doc_id = hashlib.sha256(markdown_text.encode()).hexdigest()[:16]
    chunks = chunker.chunk_text(markdown_text, doc_id=doc_id)

    # Quick assessment
    report = await service.assess_document(
        document_id=doc_id,
        document_name=document_name,
        markdown_text=markdown_text,
        chunks=chunks,
    )

    return {
        "quality_level": report.quality_level.value,
        "overall_score": round(report.overall_score, 2),
        "chunk_count": report.chunk_count,
        "recommendations": report.improvement_priority[:3],
    }
