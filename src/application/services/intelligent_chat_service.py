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
from application.services.neurosymbolic_query_service import NeurosymbolicQueryService
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from application.agents.knowledge_manager.validation_engine import ValidationEngine
from infrastructure.neo4j_backend import Neo4jBackend
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.confidence_models import CrossLayerConfidencePropagation

# Conversational layer imports (Phase 6)
from application.services.conversational_intent_service import ConversationalIntentService
from application.services.memory_context_builder import MemoryContextBuilder
from application.services.response_modulator import ResponseModulator
from domain.conversation_models import IntentType
from config.persona_config import get_persona

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
    # Phase 6: Enhanced metadata from Crystallization Pipeline
    medical_alerts: List[Dict[str, Any]] = field(default_factory=list)
    routing: Optional[Dict[str, Any]] = None
    temporal_context: Optional[Dict[str, Any]] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)


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
        patient_memory_service=None,  # NEW: Optional patient memory service
        mem0=None,  # NEW: Mem0 instance for memory context
        enable_conversational_layer: bool = True  # NEW: Enable conversational personality layer
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

        # Initialize neurosymbolic query service for layer-aware queries
        self.neurosymbolic_service = NeurosymbolicQueryService(
            backend=neo4j_backend,
            reasoning_engine=self.reasoning_engine,
            confidence_propagator=CrossLayerConfidencePropagation()
        )

        # Initialize conversational layer (Phase 6)
        self.enable_conversational = enable_conversational_layer
        if self.enable_conversational and patient_memory_service and mem0:
            self.intent_service = ConversationalIntentService(openai_api_key=api_key)
            self.memory_builder = MemoryContextBuilder(
                patient_memory_service=patient_memory_service,
                mem0=mem0
            )
            self.response_modulator = ResponseModulator(
                llm_client=self.openai_client,
                persona=get_persona(),
                openai_api_key=api_key
            )
            logger.info("Conversational personality layer enabled")
        else:
            self.intent_service = None
            self.memory_builder = None
            self.response_modulator = None
            logger.info("Conversational personality layer disabled")

        logger.info(f"IntelligentChatService initialized with model={model}, patient_memory={patient_memory_service is not None}")

    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Message]] = None,
        patient_id: Optional[str] = None,  # NEW: Patient identifier
        session_id: Optional[str] = None,  # NEW: Session identifier
        response_id: Optional[str] = None  # NEW: Response ID for feedback tracking
    ) -> ChatResponse:
        """
        Process a user question and generate an answer.

        Args:
            question: User's question
            conversation_history: Previous messages in the conversation
            patient_id: Optional patient identifier for personalized responses
            session_id: Optional session identifier for conversation tracking
            response_id: Optional response ID for feedback tracking (persisted with message)

        Returns:
            ChatResponse with answer, confidence, sources, and reasoning
        """
        start_time = datetime.now()

        if conversation_history is None:
            conversation_history = []

        logger.info(f"Processing question: {question} (patient_id={patient_id}, session_id={session_id})")

        # === PHASE 6: CONVERSATIONAL LAYER ===
        # Step 0: Intent classification and memory context building
        intent = None
        memory_context = None

        if self.enable_conversational and patient_id and self.intent_service and self.memory_builder:
            try:
                # Build memory context
                memory_context = await self.memory_builder.build_context(
                    patient_id=patient_id,
                    session_id=session_id
                )
                logger.debug(f"Memory context built: {len(memory_context.recent_topics)} topics, "
                            f"returning_user={memory_context.is_returning_user()}")

                # Classify intent
                intent = await self.intent_service.classify(question, memory_context)
                logger.info(f"Intent classified: {intent.intent_type.value} (confidence: {intent.confidence:.2f})")

                # Check if we've already exchanged messages in this session
                # If so, treat follow-up small talk as general inquiry instead of new greeting
                already_greeted = len(conversation_history) > 0 if conversation_history else False

                is_greeting_intent = intent.intent_type in [IntentType.GREETING, IntentType.GREETING_RETURN]
                is_simple_intent = intent.intent_type in [IntentType.ACKNOWLEDGMENT, IntentType.FAREWELL]

                # Handle greetings ONLY if we haven't already exchanged messages
                # Otherwise, treat as general conversation that should flow naturally
                if (is_greeting_intent and not already_greeted) or is_simple_intent:
                    # Generate personalized response without knowledge graph query
                    response_text = await self.response_modulator.generate_response(
                        user_message=question,
                        intent=intent,
                        memory_context=memory_context
                    )

                    query_time = (datetime.now() - start_time).total_seconds()
                    return ChatResponse(
                        answer=response_text,
                        confidence=0.95,  # High confidence for simple greetings
                        sources=[],
                        related_concepts=[],
                        reasoning_trail=[f"Intent: {intent.intent_type.value}"],
                        query_time_seconds=query_time
                    )
                elif is_greeting_intent and already_greeted:
                    # We've already greeted - treat follow-up small talk as general conversation
                    # This allows natural conversation flow with "how are you", "what can you help with" etc.
                    logger.info(f"Follow-up small talk detected after {len(conversation_history)} messages, treating as general inquiry")
                    intent.requires_medical_knowledge = True  # Process through normal flow

            except Exception as e:
                logger.error(f"Conversational layer error: {e}", exc_info=True)
                # Continue with normal flow if conversational layer fails
                intent = None
                memory_context = None

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

        # Calculate confidence based on actual data found
        confidence = self._calculate_confidence(
            answer=answer,
            reasoning_result=reasoning_result,
            validation_result=validation_result,
            medical_context=medical_context,
            document_chunks=document_chunks,
            sources=sources
        )

        # === PHASE 6: Response Modulation ===
        # Wrap medical response with persona if conversational layer enabled
        if (self.enable_conversational and intent and memory_context and
            self.response_modulator and intent.requires_medical_knowledge):
            try:
                logger.debug("Wrapping medical response with persona")
                answer = await self.response_modulator.generate_response(
                    user_message=question,
                    intent=intent,
                    memory_context=memory_context,
                    medical_response=answer
                )
            except Exception as e:
                logger.error(f"Response modulation failed: {e}", exc_info=True)
                # Continue with original answer if modulation fails

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

                # Extract and store medical facts from user message
                await self._extract_and_store_medical_facts(question, patient_id)

                # Store assistant message with full metadata for later retrieval
                await self.patient_memory.store_message(
                    ConversationMessage(
                        role="assistant",
                        content=answer,
                        timestamp=end_time,
                        patient_id=patient_id,
                        session_id=session_id,
                        metadata={
                            "confidence": confidence,
                            "sources": sources,  # Full sources array
                            "reasoning_trail": reasoning_result.get("provenance", []),
                            "related_concepts": related_concepts,
                            "query_time": query_time,
                            "response_id": response_id,  # For feedback tracking after reload
                        }
                    )
                )
                logger.info(f"Conversation stored for patient {patient_id}, session {session_id}")
            except Exception as e:
                logger.error(f"Failed to store conversation: {e}")

        # Phase 6: Extract medical alerts from reasoning result
        medical_alerts = []
        reasoning_inferences = reasoning_result.get("inferences", [])
        for inference in reasoning_inferences:
            if inference.get("severity") in ("critical", "high", "medium"):
                medical_alerts.append({
                    "severity": inference.get("severity", "MODERATE").upper(),
                    "category": self._infer_alert_category(inference.get("type", "")),
                    "message": inference.get("reason") or inference.get("message", "Medical alert"),
                    "recommendation": inference.get("recommendation"),
                    "triggered_by": inference.get("triggered_by", []),
                    "rule_id": inference.get("rule_id"),
                })

        # Phase 6: Extract routing info if available
        routing_info = reasoning_result.get("routing")

        # Phase 6: Extract temporal context if available
        temporal_info = reasoning_result.get("temporal_context")

        # Phase 6: Extract entities with metadata
        entity_list = []
        for entity in medical_context.get("entities", []):
            if isinstance(entity, dict):
                entity_list.append({
                    "id": entity.get("id"),
                    "name": entity.get("name"),
                    "entity_type": entity.get("entity_type") or entity.get("type"),
                    "dikw_layer": entity.get("dikw_layer"),
                    "temporal_score": entity.get("temporal_score"),
                    "last_observed": entity.get("last_observed"),
                })

        return ChatResponse(
            answer=answer,
            confidence=confidence,
            sources=sources,
            related_concepts=related_concepts,
            reasoning_trail=reasoning_result.get("provenance", []),
            query_time_seconds=query_time,
            medical_alerts=medical_alerts,
            routing=routing_info,
            temporal_context=temporal_info,
            entities=entity_list,
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

    async def _extract_and_store_medical_facts(
        self,
        message: str,
        patient_id: str
    ) -> None:
        """
        Extract medical facts (diagnoses, medications, allergies) from user message
        and store them in the patient memory.

        This enables the system to remember patient-specific medical information
        across sessions.
        """
        if not self.patient_memory:
            return

        prompt = """Analyze this patient message and extract any medical facts they mention about themselves.

Return a JSON object with these arrays (empty if none found):
- diagnoses: [{condition: "disease name", details: "any additional info like when diagnosed"}]
- medications: [{name: "drug name", dosage: "if mentioned", frequency: "if mentioned"}]
- stopped_medications: [{name: "drug name", reason: "why stopped if mentioned"}]
- resolved_conditions: [{condition: "condition name", details: "any info about when/how resolved"}]
- allergies: [{substance: "allergen", reaction: "if mentioned", severity: "mild/moderate/severe if mentioned"}]
- procedures: [{name: "procedure name", type: "test/surgery/screening/imaging", scheduled_date: "if mentioned", status: "scheduled/completed/cancelled", notes: "any details"}]
- medical_devices: [{name: "device name", type: "stoma/implant/prosthetic/pump/monitor", status: "active/removed", location: "body location if mentioned", notes: "any details"}]

PROCEDURES & TESTS - Extract these:
- "I have a colonoscopy scheduled" → add to procedures with status="scheduled"
- "I had an MRI last week" → add to procedures with status="completed"
- "I need to get a blood test" → add to procedures with status="scheduled"
- "my colonoscopy is next month" → add to procedures with scheduled_date
- Examples: colonoscopy, endoscopy, MRI, CT scan, blood test, biopsy, EKG, ultrasound, X-ray, surgery

MEDICAL DEVICES & IMPLANTS - Extract these (VERY IMPORTANT for care planning):
- "I have a colostomy" / "I have a colostomy bag" → add to medical_devices with type="stoma"
- "I have an ileostomy" / "I have an ostomy" → add to medical_devices with type="stoma"
- "I have a pacemaker" → add to medical_devices with type="implant"
- "I use an insulin pump" → add to medical_devices with type="pump"
- "I have a feeding tube" / "I have a port" → add to medical_devices
- Examples: colostomy, ileostomy, urostomy, pacemaker, insulin pump, cochlear implant, feeding tube, port-a-cath

IMPORTANT: Distinguish between:
- "I take ibuprofen" → add to medications
- "I stopped taking ibuprofen" / "I no longer take ibuprofen" → add to stopped_medications

IMPORTANT: Detect RESOLVED conditions:
- "I no longer have knee pain" → add to resolved_conditions
- "my headache is gone" → add to resolved_conditions

Only extract facts the patient explicitly states about THEMSELVES (not general questions).
Be precise - "I have Crohn's disease" is a diagnosis, "what is Crohn's disease" is NOT.

Patient message: """ + message

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical entity extractor. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1  # Low temperature for accurate extraction
            )

            import json
            result = json.loads(response.choices[0].message.content)

            # Store extracted diagnoses
            for dx in result.get("diagnoses", []):
                if dx.get("condition"):
                    try:
                        await self.patient_memory.add_diagnosis(
                            patient_id=patient_id,
                            condition=dx["condition"],
                            metadata={"details": dx.get("details", "")}
                        )
                        logger.info(f"Extracted and stored diagnosis: {dx['condition']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store diagnosis {dx['condition']}: {e}")

            # Store extracted medications (with validation)
            from application.services.medication_validator import get_medication_validator
            validator = get_medication_validator()

            for med in result.get("medications", []):
                if med.get("name"):
                    try:
                        # Validate medication before storing
                        validation = validator.validate(med["name"])

                        if validation.is_valid:
                            # Use the validated/corrected name
                            await self.patient_memory.add_medication(
                                patient_id=patient_id,
                                name=validation.validated_name,
                                dosage=med.get("dosage", "unknown"),
                                frequency=med.get("frequency", "unknown")
                            )
                            if validation.confidence < 1.0:
                                logger.info(
                                    f"Extracted and stored medication (fuzzy match): "
                                    f"'{med['name']}' -> '{validation.validated_name}' "
                                    f"(confidence: {validation.confidence:.0%}) for {patient_id}"
                                )
                            else:
                                logger.info(f"Extracted and stored medication: {validation.validated_name} for {patient_id}")
                        else:
                            # Log unrecognized medications for review
                            logger.warning(
                                f"Unrecognized medication rejected: '{med['name']}' "
                                f"for {patient_id}. Suggestions: {validation.suggestions}. "
                                f"Message: {validation.message}"
                            )
                            # Store in pending state for review
                            await self.patient_memory.add_pending_medication(
                                patient_id=patient_id,
                                name=med["name"],
                                suggestions=validation.suggestions,
                                confidence=validation.confidence,
                                dosage=med.get("dosage", "unknown"),
                                frequency=med.get("frequency", "unknown")
                            )
                    except Exception as e:
                        logger.warning(f"Failed to store medication {med['name']}: {e}")

            # Handle stopped/discontinued medications
            for stopped_med in result.get("stopped_medications", []):
                if stopped_med.get("name"):
                    try:
                        await self.patient_memory.remove_medication(
                            patient_id=patient_id,
                            medication_name=stopped_med["name"],
                            reason=stopped_med.get("reason", "Patient reported discontinuation")
                        )
                        logger.info(f"Marked medication as discontinued: {stopped_med['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to discontinue medication {stopped_med['name']}: {e}")

            # Handle resolved conditions (diagnoses/symptoms that are no longer present)
            for resolved in result.get("resolved_conditions", []):
                if resolved.get("condition"):
                    try:
                        await self.patient_memory.resolve_diagnosis(
                            patient_id=patient_id,
                            diagnosis_name=resolved["condition"],
                            resolution_reason=resolved.get("details", "Patient reported condition resolved")
                        )
                        logger.info(f"Marked condition as resolved: {resolved['condition']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to resolve condition {resolved['condition']}: {e}")

            # Store extracted allergies
            for allergy in result.get("allergies", []):
                if allergy.get("substance"):
                    try:
                        await self.patient_memory.add_allergy(
                            patient_id=patient_id,
                            substance=allergy["substance"],
                            reaction=allergy.get("reaction", "unknown"),
                            severity=allergy.get("severity", "moderate")
                        )
                        logger.info(f"Extracted and stored allergy: {allergy['substance']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store allergy {allergy['substance']}: {e}")

            # Store extracted procedures and tests
            for procedure in result.get("procedures", []):
                if procedure.get("name"):
                    try:
                        await self.patient_memory.add_procedure(
                            patient_id=patient_id,
                            name=procedure["name"],
                            procedure_type=procedure.get("type", "test"),
                            scheduled_date=procedure.get("scheduled_date"),
                            status=procedure.get("status", "scheduled"),
                            notes=procedure.get("notes")
                        )
                        logger.info(f"Extracted and stored procedure: {procedure['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store procedure {procedure['name']}: {e}")

            # Store extracted medical devices (colostomy, ileostomy, pacemaker, etc.)
            for device in result.get("medical_devices", []):
                if device.get("name"):
                    try:
                        await self.patient_memory.add_medical_device(
                            patient_id=patient_id,
                            name=device["name"],
                            device_type=device.get("type", "device"),
                            status=device.get("status", "active"),
                            location=device.get("location"),
                            notes=device.get("notes")
                        )
                        logger.info(f"Extracted and stored medical device: {device['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store medical device {device['name']}: {e}")

        except Exception as e:
            logger.warning(f"Medical fact extraction failed: {e}")

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
        """Apply neurosymbolic reasoning using layer-aware query execution."""
        try:
            # Execute query across knowledge graph layers
            result, trace = await self.neurosymbolic_service.execute_query(
                query_text=question,
                patient_context=patient_context,
                force_strategy=None,  # Let service auto-detect strategy
                trace_execution=True
            )

            # Build provenance from execution trace
            formatted_provenance = []

            if trace:
                # Add strategy information
                formatted_provenance.append(
                    f"Query Strategy: {trace.strategy.value} (auto-detected)"
                )

                # Add layer traversal information
                layers_str = " → ".join([l.value for l in trace.layers_traversed])
                formatted_provenance.append(
                    f"Layers Traversed: {layers_str}"
                )

                # Add layer-specific results
                for i, layer_result in enumerate(trace.layer_results, 1):
                    entities_count = len(layer_result.entities)
                    rels_count = len(layer_result.relationships)
                    cache_status = " (cached)" if layer_result.cache_hit else ""
                    formatted_provenance.append(
                        f"{i}. {layer_result.layer.value} layer: {entities_count} entities, "
                        f"{rels_count} relationships (confidence: {layer_result.confidence.score:.2f}){cache_status}"
                    )

                # Add conflict detection
                if trace.conflicts_detected:
                    formatted_provenance.append(
                        f"Conflicts Detected: {len(trace.conflicts_detected)} "
                        f"(resolved using higher layer priority)"
                    )

                # Add final confidence
                formatted_provenance.append(
                    f"Final Confidence: {trace.final_confidence.score:.2f} "
                    f"(source: {trace.final_confidence.source.value})"
                )

            # Ensure result has all expected fields
            result["provenance"] = formatted_provenance
            result["applied_rules"] = result.get("applied_rules", [])
            result["inferences"] = result.get("inferences", [])
            result["assertions"] = result.get("assertions", [])

            logger.info(
                f"Neurosymbolic reasoning completed: strategy={result.get('strategy')}, "
                f"confidence={result.get('confidence'):.2f}, layers={result.get('layers_traversed')}"
            )

            return result

        except Exception as e:
            logger.warning(f"Neurosymbolic reasoning failed: {e}", exc_info=True)
            # Return reasonable defaults on failure
            return {
                "provenance": ["Neurosymbolic query execution unavailable - using fallback"],
                "confidence": 0.7,
                "applied_rules": [],
                "inferences": [],
                "assertions": []
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
            # Build messages array with conversation history for better context
            messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

            # Add conversation history as actual messages (last 8 to leave room for current)
            if conversation_history:
                for msg in conversation_history[-8:]:
                    # Map role correctly (user/assistant)
                    role = "user" if msg.role.lower() == "user" else "assistant"
                    # Include full content for conversation flow
                    content = msg.content[:800] if len(msg.content) > 800 else msg.content
                    messages.append({"role": role, "content": content})

            # Add current question with context
            messages.append({"role": "user", "content": prompt})

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
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
        """Format conversation history for prompt.

        Uses last 10 messages with up to 500 chars each for better context retention.
        """
        if not history:
            return "No previous conversation."

        lines = []
        # Use last 10 messages for better context continuity
        for msg in history[-10:]:
            role = msg.role.upper()
            # Use 500 chars to preserve more context per message
            content = msg.content[:500]
            if len(msg.content) > 500:
                content += "..."
            lines.append(f"{role}: {content}")

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

        # Medical sources - check both 'source' and 'source_document' fields
        for entity in medical_context.get("entities", []):
            source = entity.get("source") or entity.get("source_document")
            if source and source not in seen:
                # Determine source type based on extension or content
                source_type = "PDF" if source.lower().endswith(".pdf") else "KnowledgeGraph"
                sources.append({"type": source_type, "name": source})
                seen.add(source)

        # Document sources from chunks
        for chunk in document_chunks:
            source = chunk.get("source") or chunk.get("source_document") or chunk.get("document_id")
            if source and source not in seen:
                sources.append({"type": "Document", "name": source})
                seen.add(source)

        # Cross-link sources
        for link in cross_links:
            source = link.get("source_document") or link.get("source")
            if source and source not in seen:
                sources.append({"type": "KnowledgeGraph", "name": source})
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
        validation_result: Dict[str, Any],
        medical_context: Optional[Dict[str, Any]] = None,
        document_chunks: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Dict[str, str]]] = None
    ) -> float:
        """
        Calculate overall confidence score for the answer.

        Confidence is based on actual data availability:
        - Base: 0.4 (no data)
        - Medical entities found: +0.15-0.25
        - Document chunks found: +0.15-0.25
        - Source documents: +0.05-0.15
        - Answer quality: +0.05
        - Validation: -20% if failed
        """
        # Start with low base - we need actual data to boost confidence
        base_confidence = 0.4

        # === Data-based confidence boosts ===

        # Boost for medical context entities found
        if medical_context:
            entity_count = len(medical_context.get("entities", []))
            relationship_count = len(medical_context.get("relationships", []))

            if entity_count > 0:
                # Scale boost: 1 entity = +0.15, 3+ entities = +0.25
                entity_boost = min(0.25, 0.15 + (entity_count - 1) * 0.05)
                base_confidence += entity_boost
                logger.debug(f"Confidence boost from {entity_count} entities: +{entity_boost:.2f}")

            if relationship_count > 0:
                # Additional boost for relationships
                rel_boost = min(0.05, relationship_count * 0.02)
                base_confidence += rel_boost

        # Boost for document chunks retrieved (RAG)
        if document_chunks:
            chunk_count = len(document_chunks)
            if chunk_count > 0:
                # Scale boost: 1 chunk = +0.15, 3+ chunks = +0.25
                chunk_boost = min(0.25, 0.15 + (chunk_count - 1) * 0.05)
                base_confidence += chunk_boost
                logger.debug(f"Confidence boost from {chunk_count} document chunks: +{chunk_boost:.2f}")

        # Boost for verified sources
        if sources:
            source_count = len(sources)
            if source_count > 0:
                # PDF sources are more reliable
                pdf_sources = sum(1 for s in sources if s.get("type") == "PDF")
                source_boost = min(0.15, source_count * 0.03 + pdf_sources * 0.02)
                base_confidence += source_boost
                logger.debug(f"Confidence boost from {source_count} sources ({pdf_sources} PDFs): +{source_boost:.2f}")

        # === Legacy reasoning-based adjustments ===

        # Check for explicit confidence from reasoning engine
        inferences = reasoning_result.get("inferences", [])
        for inference in inferences:
            if inference.get("type") == "confidence_score":
                # Blend reasoning confidence with data-based confidence
                reasoning_conf = inference.get("score", 0.5)
                base_confidence = (base_confidence + reasoning_conf) / 2
                break

        # Start with computed base
        confidence = base_confidence

        # Boost if answer is detailed
        if len(answer) > 500:
            confidence += 0.05

        # Penalize if validation failed
        if not validation_result.get("valid"):
            confidence *= 0.8

        # Check provenance for additional adjustments
        provenance = reasoning_result.get("provenance", [])
        if provenance and len(provenance) > 0:
            if isinstance(provenance[0], str) and "unavailable" in provenance[0].lower():
                confidence *= 0.95  # Slight penalty for reasoning fallback
            elif isinstance(provenance[0], dict):
                prov_type = provenance[0].get("type")
                if prov_type == "neural":
                    confidence += 0.02
                elif prov_type == "symbolic":
                    confidence += 0.03

        # Clamp to [0.0, 1.0]
        final_confidence = max(0.0, min(1.0, confidence))
        logger.debug(f"Final confidence: {final_confidence:.2f} (base: 0.4)")

        return final_confidence

    def _infer_alert_category(self, inference_type: str) -> str:
        """
        Infer the alert category from the inference type.

        Maps inference types to alert categories for frontend display.
        """
        type_lower = inference_type.lower()

        if "drug" in type_lower or "interaction" in type_lower:
            return "drug_interaction"
        elif "contraindication" in type_lower:
            return "contraindication"
        elif "allergy" in type_lower or "allergic" in type_lower:
            return "allergy"
        elif "symptom" in type_lower or "pattern" in type_lower:
            return "symptom_pattern"
        else:
            return "contraindication"  # Default fallback
