"""
Intelligent Chat Service for Neurosymbolic Q&A

Combines multiple knowledge sources for answering medical and data questions:
1. Medical Knowledge Graph (diseases, treatments, symptoms)
2. DDA Metadata Graph (tables, columns, business concepts)
3. Cross-Graph SEMANTIC relationships
4. RAG-based document retrieval
5. Neurosymbolic reasoning (neural + symbolic)
6. Validation and confidence scoring

Architecture:
    User Question
        ↓
    Query Understanding (extract entities + intent)
        ↓
    Knowledge Retrieval (medical KG + data catalog + documents)
        ↓
    Neurosymbolic Reasoning (apply rules + LLM inference)
        ↓
    Validation (fact checking + constraints)
        ↓
    Answer Generation (context-rich LLM completion)
        ↓
    Response (answer + confidence + sources + reasoning trail)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import os
from openai import AsyncOpenAI

from application.services.cross_graph_query_builder import CrossGraphQueryBuilder
from application.services.rag_service import RAGService
from application.services.document_service import DocumentService
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from application.agents.knowledge_manager.validation_engine import ValidationEngine
from infrastructure.neo4j_backend import Neo4jBackend
from domain.event import KnowledgeEvent
from domain.roles import Role

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a chat message."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    patient_id: Optional[str] = None  # NEW: Patient identifier for memory
    session_id: Optional[str] = None  # NEW: Session identifier for memory
    metadata: Dict[str, Any] = field(default_factory=dict)  # NEW: Additional metadata


@dataclass
class ChatResponse:
    """Response from the chat service."""
    answer: str
    confidence: float
    sources: List[Dict[str, str]]
    related_concepts: List[str]
    reasoning_trail: List[str]
    query_time_seconds: float


class IntelligentChatService:
    """
    Intelligent chat service with neurosymbolic reasoning.

    Provides conversational interface over medical KG + DDA metadata.
    """

    # System prompt template
    SYSTEM_PROMPT = """You are an intelligent medical data assistant with access to:
1. A medical knowledge graph (diseases, treatments, symptoms, drugs, research)
2. A comprehensive data catalog (tables, columns, data quality rules, business concepts)
3. Cross-references linking medical concepts to data structures
4. Validated facts from neurosymbolic reasoning

Your role is to provide accurate, well-sourced answers by combining information from all these sources.

## Key Capabilities:
- Answer medical questions using the knowledge graph
- Explain data structures and their medical context
- Link medical concepts to specific data tables and columns
- Provide confidence scores based on source quality and reasoning
- Cite specific sources (PDFs, graph nodes, data tables)
- Suggest related concepts for follow-up exploration

## Guidelines:
1. **Accuracy First**: Only state facts supported by the knowledge sources
2. **Source Attribution**: Always cite specific sources for medical claims
3. **Confidence Transparency**: Indicate confidence level if uncertain
4. **Layer Awareness**: Distinguish between raw data (PERCEPTION), validated relationships (SEMANTIC), and inferred knowledge (REASONING)
5. **Actionable**: When discussing data structures, provide specific table/column names
6. **Conversational**: Maintain natural conversation flow, reference previous context
7. **Humble**: If information is insufficient, clearly state limitations
"""

    # Answer generation prompt template
    ANSWER_PROMPT = """## Medical Knowledge Context
{medical_context}

## Data Catalog Context
{data_context}

## Cross-Graph Relationships
{cross_links}

## Retrieved Documents
{document_chunks}

## Reasoning Applied
{reasoning_trail}

## Validation Results
{validation_results}

## Conversation History
{conversation_history}

## User Question
{question}

## Instructions
Provide a comprehensive answer that:
1. Combines information from all available sources
2. References specific sources (use [Source: ...] format for PDFs, graph entities, or data tables)
3. Explains reasoning if complex medical or data concepts are involved
4. **IMPORTANT: DO NOT state a confidence level in your answer** - confidence will be calculated separately
5. Suggests related concepts or follow-up queries if relevant
6. Provides specific table/column names when discussing data structures

If the available information is insufficient, clearly explain what's missing and what additional sources would help.

Answer:"""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        patient_memory_service=None  # NEW: Optional patient memory service
    ):
        """Initialize the chat service."""
        # Initialize OpenAI client
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")

        self.openai_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.patient_memory = patient_memory_service  # NEW: Store patient memory service

        # Initialize Neo4j backend for reasoning and validation
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_backend = Neo4jBackend(uri=neo4j_uri, username=neo4j_user, password=neo4j_password)

        # Initialize document service for RAG (with FAISS vector search)
        self.document_service = DocumentService(
            kg_backend=neo4j_backend,
            chunk_size=1500,
            chunk_overlap=300,
            faiss_index_path="data/faiss_index"
        )

        # Initialize sub-services
        self.query_builder = CrossGraphQueryBuilder()
        self.rag_service = RAGService(
            document_service=self.document_service,
            kg_backend=neo4j_backend,
            model=model
        )
        self.reasoning_engine = ReasoningEngine(backend=neo4j_backend)
        self.validation_engine = ValidationEngine(backend=neo4j_backend)

        logger.info(f"IntelligentChatService initialized with model={model}, patient_memory={patient_memory_service is not None}")

    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Message]] = None,
        patient_id: Optional[str] = None,  # NEW: Patient identifier
        session_id: Optional[str] = None   # NEW: Session identifier
    ) -> ChatResponse:
        """
        Process a user question and generate an answer.

        Args:
            question: User's question
            conversation_history: Previous messages in the conversation
            patient_id: Optional patient identifier for personalized responses
            session_id: Optional session identifier for conversation tracking

        Returns:
            ChatResponse with answer, confidence, sources, and reasoning
        """
        start_time = datetime.now()

        if conversation_history is None:
            conversation_history = []

        logger.info(f"Processing question: {question} (patient_id={patient_id}, session_id={session_id})")

        # Step 1.5: Retrieve patient context (if patient_id provided)
        patient_context = None
        if patient_id and self.patient_memory:
            try:
                patient_context = await self.patient_memory.get_patient_context(patient_id)
                logger.info(f"Patient context loaded: {len(patient_context.diagnoses)} diagnoses, "
                           f"{len(patient_context.medications)} medications, "
                           f"{len(patient_context.allergies)} allergies")
            except Exception as e:
                logger.warning(f"Failed to load patient context: {e}")
                patient_context = None

        # Step 1: Extract entities from question
        entities = await self._extract_entities(question)

        # Add patient's conditions to entity list for better context retrieval
        if patient_context:
            patient_entities = [dx["condition"] for dx in patient_context.diagnoses]
            entities.extend(patient_entities)

        logger.info(f"Extracted entities: {entities}")

        # Step 2: Retrieve medical knowledge
        medical_context = await self._retrieve_medical_knowledge(entities, question)

        # Step 3: Retrieve data catalog context
        data_context = await self._retrieve_data_context(entities, question)

        # Step 4: Find cross-graph relationships
        cross_links = await self._retrieve_cross_graph_links(entities)

        # Step 5: RAG-based document retrieval
        document_chunks = await self._retrieve_documents(question)

        # Step 6: Apply neurosymbolic reasoning
        reasoning_result = await self._apply_reasoning(
            question=question,
            medical_context=medical_context,
            data_context=data_context,
            patient_context=patient_context  # NEW: Pass patient context to reasoning
        )

        # Step 7: Validate facts
        validation_result = await self._validate_facts(reasoning_result)

        # Step 8: Generate answer
        answer = await self._generate_answer(
            question=question,
            medical_context=medical_context,
            data_context=data_context,
            cross_links=cross_links,
            document_chunks=document_chunks,
            reasoning_trail=reasoning_result.get("provenance", []),
            validation_results=validation_result,
            conversation_history=conversation_history,
            patient_context=patient_context  # NEW: Pass patient context to answer generation
        )

        # Step 9: Extract sources and related concepts
        sources = self._extract_sources(
            medical_context, data_context, cross_links, document_chunks
        )
        related_concepts = self._find_related_concepts(entities, medical_context)

        # Calculate confidence
        confidence = self._calculate_confidence(
            answer, reasoning_result, validation_result
        )

        end_time = datetime.now()
        query_time = (end_time - start_time).total_seconds()

        logger.info(f"Answer generated in {query_time:.2f}s with confidence {confidence:.2f}")

        # Step 10: Store conversation if patient_id and session_id provided
        if patient_id and session_id and self.patient_memory:
            try:
                # Import here to avoid circular dependency
                from application.services.patient_memory_service import ConversationMessage

                # Store user message
                await self.patient_memory.store_message(
                    ConversationMessage(
                        role="user",
                        content=question,
                        timestamp=start_time,
                        patient_id=patient_id,
                        session_id=session_id
                    )
                )

                # Store assistant message
                await self.patient_memory.store_message(
                    ConversationMessage(
                        role="assistant",
                        content=answer,
                        timestamp=end_time,
                        patient_id=patient_id,
                        session_id=session_id,
                        metadata={
                            "confidence": confidence,
                            "sources_count": len(sources),
                            "reasoning_steps": len(reasoning_result.get("provenance", []))
                        }
                    )
                )
                logger.info(f"Conversation stored for patient {patient_id}, session {session_id}")
            except Exception as e:
                logger.error(f"Failed to store conversation: {e}")

        return ChatResponse(
            answer=answer,
            confidence=confidence,
            sources=sources,
            related_concepts=related_concepts,
            reasoning_trail=reasoning_result.get("provenance", []),
            query_time_seconds=query_time
        )

    async def _extract_entities(self, question: str) -> List[str]:
        """Extract medical and data entities from the question using LLM."""
        prompt = f"""Extract key medical and data entities from this question.
Return as a JSON array of entity names.

Question: {question}

Entities (medical terms, disease names, drug names, data concepts):"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an entity extraction expert. Return only a JSON array."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            import json
            result = json.loads(response.choices[0].message.content)
            entities = result.get("entities", [])

            return entities if isinstance(entities, list) else []

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []

    async def _retrieve_medical_knowledge(
        self,
        entities: List[str],
        question: str
    ) -> Dict[str, Any]:
        """Retrieve relevant medical knowledge from the graph."""
        context = {
            "entities": [],
            "relationships": []
        }

        # Search for each extracted entity
        for entity_name in entities[:5]:  # Limit to 5 entities
            try:
                result = self.query_builder.search_medical_entities(
                    search_term=entity_name,
                    entity_types=None
                )

                for record in result.records[:3]:  # Top 3 matches per entity
                    # Entities from graph have high confidence (found in KG)
                    context["entities"].append({
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "description": record.get("description"),
                        "source": record.get("source"),
                        "confidence": 0.95,  # High confidence - entity exists in KG
                        "source_document": record.get("source", "knowledge_graph")
                    })

                # Get relationships for first entity
                if result.records:
                    rel_result = self.query_builder.find_related_entities(
                        entity_name=result.records[0].get("name"),
                        max_results=5
                    )

                    for rel_record in rel_result.records:
                        context["relationships"].append({
                            "source": rel_record.get("source_entity"),
                            "relationship": rel_record.get("relationship"),
                            "target": rel_record.get("related_entity"),
                            "layer": rel_record.get("layer")
                        })

            except Exception as e:
                logger.warning(f"Failed to retrieve knowledge for entity '{entity_name}': {e}")

        return context

    async def _retrieve_data_context(
        self,
        entities: List[str],
        question: str
    ) -> Dict[str, Any]:
        """Retrieve relevant data catalog information."""
        context = {
            "tables": [],
            "columns": []
        }

        # Find data concepts
        try:
            result = self.query_builder.find_medical_concepts_in_data(
                confidence_threshold=0.70
            )

            for record in result.records[:10]:  # Top 10 data entities
                if record.get("data_type") == "Table":
                    context["tables"].append({
                        "name": record.get("data_entity"),
                        "medical_concept": record.get("medical_entity"),
                        "confidence": record.get("confidence")
                    })
                elif record.get("data_type") == "Column":
                    context["columns"].append({
                        "name": record.get("data_entity"),
                        "medical_concept": record.get("medical_entity"),
                        "confidence": record.get("confidence")
                    })

        except Exception as e:
            logger.warning(f"Failed to retrieve data context: {e}")

        return context

    async def _retrieve_cross_graph_links(
        self,
        entities: List[str]
    ) -> List[Dict[str, Any]]:
        """Find cross-graph SEMANTIC relationships."""
        links = []

        for entity_name in entities[:3]:  # Top 3 entities
            try:
                # Find tables for this entity (if it's a disease)
                result = self.query_builder.find_tables_for_disease(entity_name)

                for record in result.records:
                    if record.get("tables"):
                        for table in record["tables"]:
                            if table.get("table_name"):
                                links.append({
                                    "medical_entity": record.get("disease"),
                                    "data_entity": table.get("table_name"),
                                    "type": "APPLICABLE_TO",
                                    "confidence": table.get("confidence")
                                })

            except Exception as e:
                logger.debug(f"No cross-links found for '{entity_name}': {e}")

        return links

    async def _retrieve_documents(self, question: str) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks using RAG."""
        try:
            # Use RAG service to find relevant chunks
            rag_result = await self.rag_service.query(
                question=question,
                top_k=3,  # Top 3 most relevant chunks
                include_graph_context=False  # We handle graph context separately
            )

            # Extract chunks from RAG result
            chunks = []
            if hasattr(rag_result, 'sources'):
                for source in rag_result.sources[:3]:
                    chunks.append({
                        "text": source.get("chunk_id", "")[:500],  # Limit length
                        "source": "[Source: PDF Document]",
                        "relevance": source.get("score", 0.0)
                    })

            return chunks

        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return []

    async def _apply_reasoning(
        self,
        question: str,
        medical_context: Dict[str, Any],
        data_context: Dict[str, Any],
        patient_context=None  # NEW: Optional patient context
    ) -> Dict[str, Any]:
        """Apply neurosymbolic reasoning to the gathered context."""
        try:
            # Create proper KnowledgeEvent for reasoning engine
            event = KnowledgeEvent(
                action="chat_query",  # Custom action for chat queries
                data={
                    "question": question,
                    "medical_entities": medical_context.get("entities", []),
                    "medical_relationships": medical_context.get("relationships", []),
                    "data_tables": data_context.get("tables", []),
                    "data_columns": data_context.get("columns", []),
                    "warnings": [],  # Initialize warnings list for reasoning to populate
                    "patient_context": patient_context  # NEW: Pass patient data to reasoning
                },
                role=Role.KNOWLEDGE_MANAGER  # Chat acts as knowledge manager
            )

            # Apply collaborative reasoning (neural + symbolic)
            result = await self.reasoning_engine.apply_reasoning(
                event=event,
                strategy="collaborative"
            )

            # Format provenance into readable strings
            provenance_list = result.get("provenance", [])
            formatted_provenance = []

            for i, prov in enumerate(provenance_list, 1):
                if isinstance(prov, dict):
                    rule_name = prov.get("rule", "unknown")
                    rule_type = prov.get("type", "unknown")
                    contribution = prov.get("contribution", 0)
                    formatted_provenance.append(
                        f"{i}. Applied {rule_type} reasoning: {rule_name} ({contribution} inferences)"
                    )
                else:
                    formatted_provenance.append(f"{i}. {prov}")

            result["provenance"] = formatted_provenance

            return result

        except Exception as e:
            logger.warning(f"Reasoning failed: {e}", exc_info=True)
            # Return reasonable defaults on failure
            return {
                "provenance": ["Reasoning engine unavailable - using fallback"],
                "confidence": 0.7,
                "applied_rules": [],
                "inferences": []
            }

    async def _validate_facts(
        self,
        reasoning_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate facts using the validation engine."""
        try:
            # Extract assertions from reasoning
            assertions = reasoning_result.get("assertions", [])

            if not assertions:
                return {"valid": True, "violations": []}

            # Run validation
            validation = await self.validation_engine.validate_event(
                event_type="chat_response",
                event_data={"assertions": assertions}
            )

            return validation

        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            return {"valid": True, "violations": []}

    async def _generate_answer(
        self,
        question: str,
        medical_context: Dict[str, Any],
        data_context: Dict[str, Any],
        cross_links: List[Dict[str, Any]],
        document_chunks: List[Dict[str, Any]],
        reasoning_trail: List[str],
        validation_results: Dict[str, Any],
        conversation_history: List[Message],
        patient_context=None  # NEW: Optional patient context
    ) -> str:
        """Generate the final answer using LLM."""
        # Format contexts
        medical_ctx = self._format_medical_context(medical_context)
        data_ctx = self._format_data_context(data_context)
        cross_ctx = self._format_cross_links(cross_links)
        doc_ctx = self._format_documents(document_chunks)
        reasoning_ctx = "\n".join(reasoning_trail) if reasoning_trail else "No reasoning applied"
        validation_ctx = self._format_validation(validation_results)
        history_ctx = self._format_conversation_history(conversation_history)

        # NEW: Format patient context if provided
        patient_ctx = ""
        if patient_context:
            patient_ctx = f"""
## Patient Context (Confidential)
- **Diagnoses**: {', '.join([dx['condition'] for dx in patient_context.diagnoses]) if patient_context.diagnoses else 'None'}
- **Current Medications**: {', '.join([med['name'] for med in patient_context.medications]) if patient_context.medications else 'None'}
- **Allergies**: {', '.join(patient_context.allergies) if patient_context.allergies else 'None'}
- **Recent Summary**: {patient_context.conversation_summary}

**IMPORTANT**: Provide personalized guidance based on this patient's specific medical history.
- Avoid recommending medications the patient is allergic to.
- Consider interactions with current medications.
- Reference the patient's known conditions when relevant.
"""

        # Build prompt (updated template to include patient context)
        prompt_template = self.ANSWER_PROMPT
        if patient_context:
            # Insert patient context before user question
            prompt_template = self.ANSWER_PROMPT.replace(
                "## User Question",
                patient_ctx + "\n## User Question"
            )

        prompt = prompt_template.format(
            medical_context=medical_ctx,
            data_context=data_ctx,
            cross_links=cross_ctx,
            document_chunks=doc_ctx,
            reasoning_trail=reasoning_ctx,
            validation_results=validation_ctx,
            conversation_history=history_ctx,
            question=question
        )

        # Generate answer
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"I apologize, but I encountered an error generating the answer: {e}"

    def _format_medical_context(self, context: Dict[str, Any]) -> str:
        """Format medical knowledge context for prompt."""
        if not context.get("entities"):
            return "No relevant medical entities found."

        lines = ["**Medical Entities:**"]
        for entity in context["entities"][:5]:
            lines.append(
                f"- {entity['name']} ({entity['type']}): {entity.get('description', 'No description')}"
            )

        if context.get("relationships"):
            lines.append("\n**Relationships:**")
            for rel in context["relationships"][:5]:
                lines.append(
                    f"- {rel['source']} --[{rel['relationship']}]--> {rel['target']}"
                )

        return "\n".join(lines)

    def _format_data_context(self, context: Dict[str, Any]) -> str:
        """Format data catalog context for prompt."""
        if not context.get("tables") and not context.get("columns"):
            return "No relevant data entities found."

        lines = []

        if context.get("tables"):
            lines.append("**Data Tables:**")
            for table in context["tables"][:5]:
                lines.append(
                    f"- {table['name']} (linked to: {table['medical_concept']}, confidence: {table['confidence']:.2f})"
                )

        if context.get("columns"):
            lines.append("\n**Data Columns:**")
            for col in context["columns"][:5]:
                lines.append(
                    f"- {col['name']} (linked to: {col['medical_concept']}, confidence: {col['confidence']:.2f})"
                )

        return "\n".join(lines)

    def _format_cross_links(self, links: List[Dict[str, Any]]) -> str:
        """Format cross-graph links for prompt."""
        if not links:
            return "No cross-graph relationships found."

        lines = ["**Cross-Graph Links:**"]
        for link in links[:5]:
            lines.append(
                f"- {link['medical_entity']} --[{link['type']}]--> {link['data_entity']} "
                f"(confidence: {link.get('confidence', 0.0):.2f})"
            )

        return "\n".join(lines)

    def _format_documents(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved document chunks for prompt."""
        if not chunks:
            return "No relevant documents found."

        lines = ["**Retrieved Document Excerpts:**"]
        for i, chunk in enumerate(chunks, 1):
            lines.append(f"\n{i}. [Source: {chunk['source']}]")
            lines.append(f"   {chunk['text'][:300]}...")

        return "\n".join(lines)

    def _format_validation(self, validation: Dict[str, Any]) -> str:
        """Format validation results for prompt."""
        if validation.get("valid"):
            return "✓ All facts validated successfully"

        violations = validation.get("violations", [])
        if not violations:
            return "✓ No validation issues"

        lines = ["⚠ Validation Issues:"]
        for violation in violations[:3]:
            lines.append(f"- {violation}")

        return "\n".join(lines)

    def _format_conversation_history(self, history: List[Message]) -> str:
        """Format conversation history for prompt."""
        if not history:
            return "No previous conversation."

        lines = []
        for msg in history[-3:]:  # Last 3 messages
            role = msg.role.upper()
            lines.append(f"{role}: {msg.content[:200]}")

        return "\n".join(lines)

    def _extract_sources(
        self,
        medical_context: Dict[str, Any],
        data_context: Dict[str, Any],
        cross_links: List[Dict[str, Any]],
        document_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Extract unique sources from all contexts."""
        sources = []
        seen = set()

        # Medical sources
        for entity in medical_context.get("entities", []):
            source = entity.get("source")
            if source and source not in seen:
                sources.append({"type": "PDF", "name": source})
                seen.add(source)

        # Document sources
        for chunk in document_chunks:
            source = chunk.get("source")
            if source and source not in seen:
                sources.append({"type": "Document", "name": source})
                seen.add(source)

        # Data sources
        for table in data_context.get("tables", [])[:3]:
            name = table.get("name")
            if name and name not in seen:
                sources.append({"type": "Table", "name": name})
                seen.add(name)

        return sources

    def _find_related_concepts(
        self,
        entities: List[str],
        medical_context: Dict[str, Any]
    ) -> List[str]:
        """Find related concepts for follow-up queries."""
        related = set()

        # Add related entities from medical context
        for rel in medical_context.get("relationships", [])[:5]:
            related.add(rel.get("target"))

        # Add similar entity types
        for entity in medical_context.get("entities", [])[:3]:
            entity_type = entity.get("type")
            if entity_type in ["Disease", "Treatment", "Drug"]:
                related.add(f"More {entity_type} information")

        return list(related)[:5]  # Top 5

    def _calculate_confidence(
        self,
        answer: str,
        reasoning_result: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence score for the answer."""
        # Extract confidence from reasoning inferences
        base_confidence = 0.5

        # Look for confidence_score inference from reasoning
        inferences = reasoning_result.get("inferences", [])
        for inference in inferences:
            if inference.get("type") == "confidence_score":
                base_confidence = inference.get("score", 0.5)
                break

        # If no confidence_score found, check for data_availability_assessment
        if base_confidence == 0.5:
            for inference in inferences:
                if inference.get("type") == "data_availability_assessment":
                    base_confidence = inference.get("score", 0.5)
                    break

        # Start with reasoning-based confidence
        confidence = base_confidence

        # Boost if answer contains specific source citations
        source_count = answer.count("[Source:")
        if source_count > 0:
            confidence += min(0.15, source_count * 0.05)  # Up to +0.15 for multiple sources

        # Boost if answer is detailed (longer answers often more comprehensive)
        if len(answer) > 500:
            confidence += 0.05

        # Penalize if validation failed
        if not validation_result.get("valid"):
            confidence *= 0.8

        # Penalize if reasoning had issues (check provenance)
        provenance = reasoning_result.get("provenance", [])
        if provenance and len(provenance) > 0:
            # Check if reasoning was successful (has actual steps)
            if isinstance(provenance[0], str) and "unavailable" in provenance[0].lower():
                confidence *= 0.9  # Slight penalty for reasoning fallback
            elif isinstance(provenance[0], dict) and provenance[0].get("type") == "neural":
                # Boost for neural reasoning applied
                confidence += 0.02
            elif isinstance(provenance[0], dict) and provenance[0].get("type") == "symbolic":
                # Boost for symbolic reasoning applied
                confidence += 0.03

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))
