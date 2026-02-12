"""
Conversation Nodes for LangGraph-based Conversation Engine.

Implements the nodes of the conversation state machine:
- Entry Node: Load patient context, increment turn count
- Classifier Node: Classify mode and extract topics
- Mode-Specific Nodes: Casual, Medical, Research, Goal-Driven, Closing
- Response Synthesizer: Apply persona and ensure natural flow
- Memory Persist: Persist state to memory layers
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json
import os

from openai import AsyncOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from domain.conversation_state import (
    ConversationState,
    ConversationMode,
    UrgencyLevel,
    EmotionalTone,
    AssistantAction,
    PatientContext,
    ActiveGoal,
    serialize_goal,
    deserialize_goal,
)
from domain.goal_templates import (
    GoalType,
    GOAL_TEMPLATES,
    create_goal_from_template,
    get_slot_question,
    get_completion_prompt,
    detect_goal_type,
)

logger = logging.getLogger(__name__)


class ConversationNodes:
    """
    Implementation of all conversation graph nodes.

    Each node transforms the ConversationState and returns
    the fields to update.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        patient_memory_service=None,
        neurosymbolic_service=None,
        episodic_memory_service=None,
        model: str = "gpt-4o",
    ):
        """
        Initialize conversation nodes with required services.

        Args:
            openai_api_key: OpenAI API key
            patient_memory_service: Service for patient memory operations
            neurosymbolic_service: Service for knowledge graph queries
            episodic_memory_service: Service for Graphiti-based episodic memory
            model: LLM model to use
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.patient_memory = patient_memory_service
        self.neurosymbolic = neurosymbolic_service
        self.episodic_memory = episodic_memory_service
        self.model = model

        # Persona configuration
        self.persona_name = "Matucha"
        self.persona_tone = "warm_professional"

        logger.info(f"ConversationNodes initialized with model={model}, episodic_memory={episodic_memory_service is not None}")

    # ============================================================
    # ENTRY NODE
    # ============================================================

    async def entry_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Entry point for conversation processing.

        - Loads patient context if not already loaded
        - Increments turn count
        - Updates last activity timestamp
        - Generates conversation summary for long threads (> 5 turns)

        Args:
            state: Current conversation state

        Returns:
            Updated state fields
        """
        previous_turn_count = state.get("turn_count", 0)
        turn_count = previous_turn_count + 1
        messages = state.get("messages", [])
        thread_id = state.get("thread_id", "unknown")

        # Debug logging for conversation tracking
        print(f"[ENTRY_NODE] thread_id={thread_id}")
        print(f"[ENTRY_NODE] Turn {previous_turn_count} -> {turn_count}, Messages in state: {len(messages)}")
        if previous_turn_count == 0:
            print(f"[ENTRY_NODE] *** NEW CONVERSATION (turn_count was 0) ***")
        else:
            print(f"[ENTRY_NODE] *** CONTINUING CONVERSATION (turn_count was {previous_turn_count}) ***")

        for i, msg in enumerate(messages[-6:]):  # Show last 6 messages
            role = "Human" if isinstance(msg, HumanMessage) else "AI"
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"[ENTRY_NODE] msg[{len(messages)-6+i if len(messages)>6 else i}]: {role}: {content_preview}")

        logger.debug(f"Entry node - thread_id={state.get('thread_id')}, turn={turn_count}")

        updates = {
            "turn_count": turn_count,
            "last_activity": datetime.now().isoformat(),
        }

        # Generate conversation summary for long threads
        existing_summary = state.get("conversation_summary")

        # Update summary every 5 turns after turn 5 (turns 5, 10, 15, etc.)
        if turn_count >= 5 and turn_count % 5 == 0 and len(messages) > 6:
            summary = await self._generate_conversation_summary(messages, existing_summary)
            if summary:
                updates["conversation_summary"] = summary
                logger.info(f"Updated conversation summary at turn {turn_count}")

        # Load patient context if needed and available
        patient_id = state.get("patient_id")
        session_id = state.get("session_id")
        if patient_id and self.patient_memory and not state.get("patient_context"):
            try:
                context = await self.patient_memory.get_patient_context(patient_id)

                # Use temporal-aware fields from PatientContext
                updates["patient_context"] = {
                    "patient_id": patient_id,
                    "patient_name": getattr(context, "patient_name", None),
                    # Only use recent conditions (mentioned in last 7 days)
                    "active_conditions": [d.get("condition", "") for d in getattr(context, "recent_conditions", context.diagnoses) if d],
                    # Keep historical conditions separate (for reference but not active use)
                    "historical_conditions": [d.get("condition", "") for d in getattr(context, "historical_conditions", []) if d],
                    "current_medications": [m.get("name", "") for m in context.medications if m],
                    "allergies": context.allergies,
                    "recently_resolved": getattr(context, "recently_resolved", []) or await self._get_resolved_conditions(patient_id),
                    # Temporal metadata
                    "context_timestamp": getattr(context, "context_timestamp", datetime.now().isoformat()),
                    # Memory context from Mem0 (for cross-session continuity)
                    "conversation_summary": getattr(context, "conversation_summary", ""),
                    "mem0_memories": getattr(context, "mem0_memories", []),
                }
                logger.info(f"Loaded patient context: {len(updates['patient_context']['active_conditions'])} recent conditions, "
                           f"{len(updates['patient_context'].get('historical_conditions', []))} historical")
            except Exception as e:
                logger.warning(f"Failed to load patient context: {e}")

        # Retrieve episodic context from Graphiti (if available)
        if patient_id and self.episodic_memory and messages:
            try:
                # Get the current user query (last human message)
                current_query = None
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        current_query = msg.content
                        break

                if current_query:
                    episodic_context = await self.episodic_memory.get_conversation_context(
                        patient_id=patient_id,
                        current_query=current_query,
                        session_id=session_id,
                        max_episodes=5,
                    )

                    # Store episodic context for use by other nodes
                    updates["episodic_context"] = episodic_context
                    logger.info(
                        f"Retrieved episodic context: {episodic_context.get('total_context_items', 0)} items "
                        f"({len(episodic_context.get('recent_episodes', []))} recent, "
                        f"{len(episodic_context.get('related_episodes', []))} related, "
                        f"{len(episodic_context.get('entities', []))} entities)"
                    )

            except Exception as e:
                logger.warning(f"Failed to retrieve episodic context: {e}")

        return updates

    async def _get_resolved_conditions(self, patient_id: str) -> List[str]:
        """Get recently resolved conditions for a patient."""
        try:
            if hasattr(self.patient_memory, "get_recently_resolved_conditions"):
                return await self.patient_memory.get_recently_resolved_conditions(patient_id, days=7)
        except Exception as e:
            logger.warning(f"Failed to get resolved conditions: {e}")
        return []

    async def _generate_conversation_summary(
        self,
        messages: List[Any],
        existing_summary: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a rolling summary of the conversation for context preservation.

        This helps maintain context in long conversations without overwhelming
        the context window with full message history.

        Args:
            messages: Full message history
            existing_summary: Previous summary to build upon

        Returns:
            Updated summary string or None if generation fails
        """
        if not self.openai_client:
            return None

        # Only summarize older messages (keep last 6 for immediate context)
        older_messages = messages[:-6] if len(messages) > 6 else []
        if not older_messages:
            return existing_summary

        # Format messages for summarization
        message_text = ""
        for msg in older_messages:
            role = "Patient" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            message_text += f"{role}: {content}\n"

        prompt = f"""Summarize the key points from this conversation so far.

Previous Summary (if any):
{existing_summary or "None - this is the first summary"}

Older Messages to Incorporate:
{message_text}

Create a brief summary (2-4 sentences) focusing on:
1. Medical facts discussed (symptoms, conditions, treatments)
2. Goals established or progress made
3. Important decisions or preferences expressed
4. Any action items or follow-ups mentioned

Keep it factual and concise. This summary helps maintain context across a long conversation."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical conversation summarizer. Be concise and factual."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Conversation summary generation failed: {e}")
            return existing_summary

    # ============================================================
    # CLASSIFIER NODE
    # ============================================================

    async def classifier_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Classify the conversation mode and extract topics.

        Uses LLM to analyze:
        - Current message in context of history
        - Whether mode should change
        - What topics are being discussed
        - Emotional tone and urgency

        Args:
            state: Current conversation state

        Returns:
            Updated mode, topics, emotional tone, urgency
        """
        messages = state.get("messages", [])
        if not messages:
            return {}

        # Get the last user message
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return {}

        user_text = last_message.content
        current_mode = state.get("mode", ConversationMode.CASUAL_CHAT.value)
        patient_context = state.get("patient_context", {})

        # Build classification prompt
        classification_prompt = self._build_classification_prompt(
            user_text=user_text,
            current_mode=current_mode,
            conversation_history=messages[:-1],
            patient_context=patient_context,
            active_goal=state.get("active_goal"),
            conversation_summary=state.get("conversation_summary"),
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a conversation analyzer. Return only valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)

            # Extract classification results
            new_mode = result.get("mode", current_mode)
            topics = result.get("topics", [])
            emotion = result.get("emotional_tone", EmotionalTone.NEUTRAL.value)
            urgency = result.get("urgency", UrgencyLevel.LOW.value)
            detected_goal = result.get("detected_goal")
            user_intent = result.get("user_intent", "unknown")
            is_clarification = result.get("is_clarification_request", False)
            is_request_refinement = result.get("is_request_refinement", False)
            refined_context = result.get("refined_context")

            # Track mode changes
            mode_changed = new_mode != current_mode
            updates = {
                "mode": new_mode,
                "current_topics": topics,
                "last_user_intent": user_intent,
                "urgency_level": urgency,
                "emotional_arc": state.get("emotional_arc", []) + [emotion],
                "is_clarification_request": is_clarification,
                "is_request_refinement": is_request_refinement,
                "refined_context": refined_context,
            }

            if mode_changed:
                updates["previous_mode"] = current_mode
                updates["mode_turns"] = 0
                logger.info(f"Mode transition: {current_mode} -> {new_mode}")
            else:
                updates["mode_turns"] = state.get("mode_turns", 0) + 1

            # Handle goal detection - only create a new goal if:
            # 1. A goal type was detected
            # 2. We're in goal_driven mode
            # 3. There's no existing active goal (don't overwrite)
            # 4. This is NOT a clarification request (preserve existing goal context)
            existing_goal = state.get("active_goal")
            if detected_goal and new_mode == ConversationMode.GOAL_DRIVEN.value:
                if not existing_goal and not is_clarification:
                    try:
                        goal_type = GoalType(detected_goal)
                        goal = create_goal_from_template(goal_type)
                        updates["active_goal"] = serialize_goal(goal)
                        logger.info(f"Created new goal: {goal_type.value}")
                    except ValueError:
                        logger.warning(f"Unknown goal type: {detected_goal}")
                else:
                    logger.debug(f"Skipping goal creation - existing_goal={existing_goal is not None}, is_clarification={is_clarification}")

            # Update explored topics
            explored = set(state.get("explored_topics", []))
            explored.update(topics)
            updates["explored_topics"] = list(explored)

            logger.debug(f"Classification: mode={new_mode}, topics={topics}, emotion={emotion}")
            return updates

        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            return {"mode_turns": state.get("mode_turns", 0) + 1}

    def _build_classification_prompt(
        self,
        user_text: str,
        current_mode: str,
        conversation_history: List[Any],
        patient_context: Dict[str, Any],
        active_goal: Optional[Dict[str, Any]],
        conversation_summary: Optional[str] = None,
    ) -> str:
        """Build the classification prompt for mode detection."""

        # Format recent history
        history_text = ""
        if conversation_history:
            recent = conversation_history[-6:]  # Last 6 messages
            for msg in recent:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                history_text += f"{role}: {content}\n"

        # Format patient context
        context_text = ""
        if patient_context:
            conditions = patient_context.get("active_conditions", [])
            meds = patient_context.get("current_medications", [])
            if conditions:
                context_text += f"Patient conditions: {', '.join(conditions[:5])}\n"
            if meds:
                context_text += f"Current medications: {', '.join(meds[:5])}\n"

        # Goal context
        goal_text = ""
        if active_goal:
            goal_text = f"Active goal: {active_goal.get('goal_type', 'unknown')}, progress: {active_goal.get('progress', 0):.0%}\n"

        # Conversation summary for longer threads
        summary_text = ""
        if conversation_summary:
            summary_text = f"\nConversation Summary (earlier context):\n{conversation_summary}\n"

        return f"""Analyze this conversation turn and classify it.
{summary_text}

Current Mode: {current_mode}
{goal_text}

Patient Context:
{context_text or "No patient context loaded"}

Recent Conversation:
{history_text or "No previous messages"}

Current User Message: "{user_text}"

Classify the conversation and return JSON with:
1. "mode": One of: casual_chat, medical_consult, research_explore, goal_driven, follow_up, closing
2. "topics": Array of 1-5 topics being discussed (medical terms, symptoms, concepts)
3. "emotional_tone": One of: neutral, concerned, anxious, frustrated, relieved, grateful, confused
4. "urgency": One of: low, medium, high, critical
5. "detected_goal": If mode is goal_driven, one of: diet_planning, exercise_planning, disease_education, medication_management, mental_health_support (or null)
6. "user_intent": Brief description of what the user wants
7. "is_clarification_request": true if the user is asking for clarification about something the assistant said or asked (e.g., "what do you mean?", "I don't understand", "what condition?", "explain that", "can you clarify?")
8. "is_request_refinement": true if the user is CORRECTING or REFINING their previous request because the assistant misunderstood. Look for phrases like: "I mean...", "No, I want...", "I was asking for...", "Not that, I need...", "Actually I wanted...", "I meant...", "What I'm looking for is...", "I'm asking about..."
9. "refined_context": If is_request_refinement is true, extract what the user actually wants (e.g., "desk exercises", "quick breaks at work", "5 minute stretches")

Mode Guidelines:
- CASUAL_CHAT: Greetings, small talk, general conversation
- MEDICAL_CONSULT: Reporting symptoms, asking for medical advice, discussing specific health issues
- RESEARCH_EXPLORE: Wanting to learn about a disease, treatment, or medical topic in depth
- GOAL_DRIVEN: Wanting help with a specific task (diet plan, exercise routine, etc.)
- FOLLOW_UP: Continuing or referencing a previous topic from earlier in the conversation
- CLOSING: Saying goodbye, thanking, ending conversation

Urgency Guidelines:
- LOW: General questions, no immediate concern
- MEDIUM: Symptoms present but not alarming
- HIGH: Symptoms require prompt attention
- CRITICAL: Emergency symptoms (chest pain, difficulty breathing, etc.)

Return only the JSON object."""

    # ============================================================
    # CASUAL CHAT NODE
    # ============================================================

    async def casual_chat_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Handle casual/greeting interactions naturally.

        Args:
            state: Current conversation state

        Returns:
            Response message and action taken
        """
        messages = state.get("messages", [])
        patient_context = state.get("patient_context", {})
        turn_count = state.get("turn_count", 0)
        has_greeted = state.get("has_greeted", False)  # Check if already greeted

        # Get last user message
        last_message = messages[-1] if messages else None
        user_text = last_message.content if last_message else ""

        # Build system prompt with persona
        system_prompt = self._build_persona_prompt(patient_context)

        # Build user prompt based on turn count and context
        # IMPORTANT: Only greet on first turn AND if we haven't greeted yet in this session
        # This prevents double greetings when mode transitions back to casual_chat
        should_greet = (turn_count <= 1) and not has_greeted

        # Determine if this is a returning user based on multiple signals
        # This is set regardless of whether we greet, so reflection_node can use it
        mem0_memories = patient_context.get("mem0_memories", [])
        returning_user = bool(
            patient_context.get("active_conditions") or
            patient_context.get("historical_conditions") or
            patient_context.get("recently_resolved") or
            patient_context.get("current_medications") or
            patient_context.get("patient_name") or
            # KEY: Mem0 memories indicate we've talked before!
            mem0_memories or
            # If user mentions Matucha by name, they likely know her
            "matucha" in user_text.lower()
        )

        # Debug logging
        print(f"[GREETING] returning_user={returning_user}, mem0_memories={len(mem0_memories)}, should_greet={should_greet}")
        if mem0_memories:
            print(f"[GREETING] Sample memories: {mem0_memories[:2]}")

        if should_greet:
            user_prompt = self._build_greeting_prompt(
                user_text=user_text,
                patient_context=patient_context,
                returning_user=returning_user,
            )
        else:
            # Ongoing casual conversation
            user_prompt = f"""Continue the casual conversation naturally.

User said: "{user_text}"

Respond in a friendly, conversational way. If they seem to want to discuss something medical or need help with a task, acknowledge it and offer to help. Keep the response brief (under 50 words)."""

        try:
            # Build conversation history for LLM context
            llm_messages = [{"role": "system", "content": system_prompt}]

            # Add recent conversation history (last 6 messages for casual chat)
            for msg in messages[-6:]:
                if isinstance(msg, HumanMessage):
                    llm_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    llm_messages.append({"role": "assistant", "content": msg.content})

            # Add the prompt as final user message
            llm_messages.append({"role": "user", "content": user_prompt})

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=0.7,
                max_tokens=200,
            )

            response_text = response.choices[0].message.content.strip()

            result = {
                "messages": [AIMessage(content=response_text)],
                "last_assistant_action": AssistantAction.GREETED.value if should_greet else AssistantAction.ACKNOWLEDGED.value,
                "returning_user": returning_user,  # Store for reflection_node to use
            }
            # Mark that we've greeted to prevent double greetings
            if should_greet:
                result["has_greeted"] = True
            return result

        except Exception as e:
            logger.error(f"Casual chat generation failed: {e}")
            result = {
                "messages": [AIMessage(content="Hello! How can I help you today?")],
                "last_assistant_action": AssistantAction.GREETED.value,
                "has_greeted": True,  # Even fallback greeting counts
                "returning_user": returning_user,  # Preserve for reflection_node
            }
            return result

    def _build_greeting_prompt(
        self,
        user_text: str,
        patient_context: Dict[str, Any],
        returning_user: bool,
    ) -> str:
        """Build a greeting prompt that's context-aware with natural variety."""
        import random

        # Time-based greeting variations
        from datetime import datetime
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_greeting = random.choice(["Good morning", "Morning", "Hello"])
        elif 12 <= hour < 17:
            time_greeting = random.choice(["Good afternoon", "Hello", "Hi there"])
        else:
            time_greeting = random.choice(["Good evening", "Hello", "Hi"])

        if returning_user:
            conditions = patient_context.get("active_conditions", [])
            historical = patient_context.get("historical_conditions", [])
            recently_resolved = patient_context.get("recently_resolved", [])
            patient_name = patient_context.get("patient_name")
            medications = patient_context.get("current_medications", [])
            conversation_summary = patient_context.get("conversation_summary", "")
            mem0_memories = patient_context.get("mem0_memories", [])

            # Check if user mentioned Matucha by name - they know her
            knows_name = "matucha" in user_text.lower()

            # Different opening styles for variety
            opening_styles = [
                "Start with a warm, personalized greeting",
                "Begin casually, like greeting an old friend",
                "Open with a friendly, caring tone",
                "Start naturally, acknowledging it's nice to chat again",
            ]
            selected_style = random.choice(opening_styles)

            # Format memories for context
            memories_text = ""
            if mem0_memories:
                memories_text = "\n".join([f"- {m}" for m in mem0_memories[:5]])

            # Determine if we have meaningful memories to reference
            has_meaningful_memories = bool(mem0_memories and any(
                m for m in mem0_memories if not m.lower().startswith("patient ") and len(m) > 20
            ))

            prompt = f"""Generate a warm, personalized greeting for a returning patient.

User said: "{user_text}"

Patient Context:
- Patient name: {patient_name or 'Not known'}
- Active conditions: {', '.join(conditions[:3]) if conditions else 'None currently'}
- Historical conditions: {', '.join(historical[:2]) if historical else 'None'}
- Recently resolved: {', '.join(recently_resolved[:2]) if recently_resolved else 'None'}
- Current medications: {', '.join(medications[:3]) if medications else 'None known'}
- User mentioned "Matucha" by name: {knows_name}
- Time-appropriate greeting suggestion: {time_greeting}

**IMPORTANT - Recent Memories (things I know about this patient):**
{memories_text or 'No recent memories available'}

Style direction: {selected_style}

Guidelines:
1. {"They called you by name! Respond naturally - they already know you." if knows_name else "Welcome them warmly but don't be formulaic."}
2. **CRUCIAL: If there are recent memories above, subtly show you remember them!**
   - If memories mention treatments/medications: "How are things going with your treatment?"
   - If memories mention symptoms: "How have you been feeling?"
   - If memories mention research interests: "Still curious about [topic]?"
   - Don't recite facts back, just show you remember the relationship
3. DON'T immediately dive into medical details unless they bring it up
4. {"Use their name naturally if it fits." if patient_name else ""}
5. Offer to help in a genuine way - but vary your phrasing
6. Keep it under 40 words
7. Mirror their energy - if they're casual ("hey!"), be casual back

{"**You have memories! Use them to show you remember this patient.**" if has_meaningful_memories else ""}

Bad examples (too generic):
- "Hello! I'm here to support you with any health-related questions."
- "Hi there! How can I help you today?"

Good examples (shows memory):
- "Hey! Good to see you again. How have things been going with your treatment?"
- "Hi! Last time we talked about [topic]. How's everything?"
- "[Time greeting]! How are you feeling lately?"
- "Nice to hear from you! What's on your mind today?" """
        else:
            # Different intro styles for new patients
            intro_styles = [
                f"{time_greeting}! I'm Matucha, and I'll be your medical assistant.",
                f"Hi there! My name's Matucha - I'm here to help with any health questions.",
                f"{time_greeting}! I'm Matucha, your friendly medical assistant.",
                f"Hello! I'm Matucha. I'm here to help you with health-related questions.",
            ]
            selected_intro = random.choice(intro_styles)

            prompt = f"""Generate a warm greeting for a new patient.

User said: "{user_text}"

Suggested intro style (you can adapt this): "{selected_intro}"

Guidelines:
1. Welcome them warmly - match their tone
2. Introduce yourself as Matucha naturally (don't be overly formal)
3. Offer to help in a genuine way
4. Keep it under 35 words
5. Be friendly, professional, and human
6. AVOID generic phrases like "How can I assist you today?"

Good variations:
- "Hi! I'm Matucha - think of me as your health companion. What's on your mind?"
- "Hello there! I'm Matucha, and I'm here to help with health questions. What brings you in?"
- "Hey! I'm Matucha. Feel free to ask me anything health-related - I'm here to help."
"""

        return prompt

    # ============================================================
    # MEDICAL CONSULT NODE
    # ============================================================

    async def medical_consult_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Handle medical consultation interactions.

        Uses the neurosymbolic service for knowledge retrieval
        and generates empathetic, informative responses.

        Args:
            state: Current conversation state

        Returns:
            Medical response with sources
        """
        messages = state.get("messages", [])
        patient_context = state.get("patient_context", {})
        current_topics = state.get("current_topics", [])
        emotional_tone = state.get("emotional_arc", [EmotionalTone.NEUTRAL.value])[-1]
        urgency = state.get("urgency_level", UrgencyLevel.LOW.value)

        last_message = messages[-1] if messages else None
        user_text = last_message.content if last_message else ""

        # Query knowledge graph if available
        knowledge_context = ""
        if self.neurosymbolic:
            try:
                result, trace = await self.neurosymbolic.execute_query(
                    query_text=user_text,
                    patient_context=patient_context,
                    trace_execution=True,
                )
                knowledge_context = self._format_knowledge_result(result, trace)
            except Exception as e:
                logger.warning(f"Knowledge retrieval failed: {e}")

        # Build medical response prompt
        system_prompt = self._build_persona_prompt(patient_context)

        # Get memory context for cross-session continuity
        conversation_summary = patient_context.get("conversation_summary", "")
        mem0_memories = patient_context.get("mem0_memories", [])
        patient_name = patient_context.get("patient_name")
        memories_text = "\n".join([f"- {m}" for m in mem0_memories[:5]]) if mem0_memories else ""

        user_prompt = f"""The patient is discussing a medical topic.

User said: "{user_text}"

Topics being discussed: {', '.join(current_topics) if current_topics else 'general medical'}
Emotional tone: {emotional_tone}
Urgency level: {urgency}

Patient Context:
- Patient name: {patient_name or 'Not known'}
- Conditions: {', '.join(patient_context.get('active_conditions', [])) or 'None known'}
- Medications: {', '.join(patient_context.get('current_medications', [])) or 'None known'}
- Allergies: {', '.join(patient_context.get('allergies', [])) or 'None known'}

Previous Conversations Summary:
{conversation_summary or 'No previous conversation history'}

Recent Memories (from past sessions - USE these to recall previous interactions):
{memories_text or 'No recent memories available'}

{f"Knowledge from medical database:{chr(10)}{knowledge_context}" if knowledge_context else ""}

Generate a response that:
1. MATCHES THEIR TONE: If they're asking a practical question, answer directly without emotional preambles
   - AVOID: "I know living with [condition] can be challenging..." (they already know this!)
   - AVOID: "Managing a chronic condition is difficult..." (condescending)
   - GOOD: Just answer their question directly and practically
2. Only show empathy if they express distress, frustration, or emotional content
3. Provides accurate, helpful medical information
4. Asks clarifying questions if needed to better understand their situation
5. Considers their existing conditions and medications
6. Flags any safety concerns (allergies, drug interactions)
7. Recommends consulting a healthcare provider for serious concerns
8. Keeps the response focused and under 150 words
9. If they reference past conversations (e.g., "the exercise plan you made"), use the memories above to respond appropriately

TONE CALIBRATION based on emotional_tone={emotional_tone}:
- neutral/curious → Direct, informational response. No emotional preambles.
- concerned/anxious → Brief acknowledgment, then practical help
- frustrated/distressed → Show understanding, then help
- positive → Match their energy, be encouraging

{"IMPORTANT: This is marked as high/critical urgency. Ensure safety guidance is prominent." if urgency in [UrgencyLevel.HIGH.value, UrgencyLevel.CRITICAL.value] else ""}"""

        try:
            # Build conversation history for LLM context
            # Include recent messages so LLM remembers what was discussed
            llm_messages = [{"role": "system", "content": system_prompt}]

            # Add recent conversation history (last 10 messages for context)
            # This allows the LLM to remember what it said and what user asked before
            for msg in messages[-10:]:
                if isinstance(msg, HumanMessage):
                    llm_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    llm_messages.append({"role": "assistant", "content": msg.content})

            # Add the contextual prompt as a final user message
            llm_messages.append({"role": "user", "content": user_prompt})

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=0.5,
                max_tokens=400,
            )

            response_text = response.choices[0].message.content.strip()

            return {
                "messages": [AIMessage(content=response_text)],
                "last_assistant_action": AssistantAction.PROVIDED_MEDICAL_INFO.value,
            }

        except Exception as e:
            logger.error(f"Medical consult generation failed: {e}")
            return {
                "messages": [AIMessage(content="I understand you have a health concern. Could you tell me more about what you're experiencing so I can help?")],
                "last_assistant_action": AssistantAction.ASKED_CLARIFICATION.value,
            }

    def _format_knowledge_result(self, result: Dict[str, Any], trace: Any) -> str:
        """Format knowledge graph results for the prompt."""
        lines = []

        if result.get("entities"):
            lines.append("Relevant medical entities:")
            for entity in result["entities"][:5]:
                name = entity.get("name", "Unknown")
                etype = entity.get("type", "")
                lines.append(f"  - {name} ({etype})")

        if result.get("relationships"):
            lines.append("Key relationships:")
            for rel in result["relationships"][:5]:
                lines.append(f"  - {rel.get('source')} -> {rel.get('relationship')} -> {rel.get('target')}")

        if trace and hasattr(trace, "final_confidence"):
            lines.append(f"Confidence: {trace.final_confidence.score:.0%}")

        return "\n".join(lines) if lines else ""

    # ============================================================
    # RESEARCH EXPLORER NODE
    # ============================================================

    async def research_explorer_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Handle knowledge exploration conversations.

        Provides in-depth explanations about medical topics,
        diseases, treatments, and research.

        Args:
            state: Current conversation state

        Returns:
            Educational response with follow-up suggestions
        """
        messages = state.get("messages", [])
        patient_context = state.get("patient_context", {})
        current_topics = state.get("current_topics", [])
        explored_topics = state.get("explored_topics", [])

        last_message = messages[-1] if messages else None
        user_text = last_message.content if last_message else ""

        # Determine depth based on whether this is follow-up exploration
        is_follow_up = any(topic in explored_topics for topic in current_topics)
        depth = "deep" if is_follow_up else "overview"

        # Query knowledge graph
        knowledge_context = ""
        if self.neurosymbolic:
            try:
                result, trace = await self.neurosymbolic.execute_query(
                    query_text=user_text,
                    patient_context=patient_context,
                    trace_execution=True,
                )
                knowledge_context = self._format_knowledge_result(result, trace)
            except Exception as e:
                logger.warning(f"Knowledge retrieval failed: {e}")

        system_prompt = self._build_persona_prompt(patient_context)

        user_prompt = f"""The patient wants to learn about a medical topic.

User said: "{user_text}"

Topics: {', '.join(current_topics) if current_topics else 'general'}
Already explored: {', '.join(explored_topics[:5]) if explored_topics else 'none'}
Depth level: {depth}

{f"Knowledge from database:{chr(10)}{knowledge_context}" if knowledge_context else ""}

Generate an educational response that:
1. Explains the topic at the appropriate depth level
2. Uses clear, accessible language (avoid excessive jargon)
3. Relates information to the patient's conditions if relevant
4. {"Builds on what was already discussed" if is_follow_up else "Provides a good overview/introduction"}
5. Offers 2-3 follow-up directions they might be interested in
6. Keep it informative but conversational (150-250 words)"""

        try:
            # Build conversation history for context
            llm_messages = [{"role": "system", "content": system_prompt}]

            # Add recent conversation history (last 8 messages)
            for msg in messages[-8:]:
                if isinstance(msg, HumanMessage):
                    llm_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    llm_messages.append({"role": "assistant", "content": msg.content})

            llm_messages.append({"role": "user", "content": user_prompt})

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=0.6,
                max_tokens=600,
            )

            response_text = response.choices[0].message.content.strip()

            return {
                "messages": [AIMessage(content=response_text)],
                "last_assistant_action": AssistantAction.EXPLAINED_TOPIC.value,
            }

        except Exception as e:
            logger.error(f"Research explorer generation failed: {e}")
            return {
                "messages": [AIMessage(content="That's an interesting topic. Let me share what I know about it...")],
                "last_assistant_action": AssistantAction.EXPLAINED_TOPIC.value,
            }

    # ============================================================
    # GOAL-DRIVEN NODE
    # ============================================================

    async def goal_driven_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Handle goal-oriented dialogues with slot filling.

        Works toward completing a specific goal (diet plan,
        exercise routine, etc.) by collecting required information.

        Args:
            state: Current conversation state

        Returns:
            Slot collection or goal completion response
        """
        messages = state.get("messages", [])
        patient_context = state.get("patient_context", {})
        active_goal_data = state.get("active_goal")
        is_clarification = state.get("is_clarification_request", False)
        is_request_refinement = state.get("is_request_refinement", False)
        refined_context = state.get("refined_context")
        last_asked_slot = state.get("last_asked_slot")

        last_message = messages[-1] if messages else None
        user_text = last_message.content if last_message else ""

        # Debug logging for state tracking (using print for visibility)
        print(f"[GOAL_DRIVEN] Turn started - user: '{user_text}'")
        print(f"[GOAL_DRIVEN] active_goal_data exists: {active_goal_data is not None}")
        if active_goal_data:
            print(f"[GOAL_DRIVEN] Goal type: {active_goal_data.get('goal_type')}")
            print(f"[GOAL_DRIVEN] Goal progress: {active_goal_data.get('progress')}")
            slots = active_goal_data.get('slots', {})
            for slot_name, slot_info in slots.items():
                print(f"[GOAL_DRIVEN] Slot '{slot_name}': filled={slot_info.get('filled')}, value={slot_info.get('value')}")
        print(f"[GOAL_DRIVEN] is_clarification: {is_clarification}, last_asked_slot: {last_asked_slot}")

        # If no active goal, try to create one from detected topics
        if not active_goal_data:
            detected = detect_goal_type(user_text)
            if detected:
                goal = create_goal_from_template(detected)
                active_goal_data = serialize_goal(goal)
                logger.info(f"Created goal from detection: {detected.value}")
            else:
                # Can't proceed without a goal
                return {
                    "messages": [AIMessage(content="I'd be happy to help you with a specific task. What would you like to work on? I can help with diet planning, exercise routines, learning about conditions, medication management, or mental health support.")],
                    "last_assistant_action": AssistantAction.ASKED_CLARIFICATION.value,
                }

        # Deserialize the goal
        goal = deserialize_goal(active_goal_data)

        # Handle request refinement - user is correcting/refining their request
        # This is different from clarification - they're telling us what they ACTUALLY want
        if is_request_refinement and refined_context:
            print(f"[GOAL_DRIVEN] Request refinement detected: '{refined_context}'")
            # Update the exercise_context slot if this is an exercise planning goal
            if goal.goal_type == GoalType.EXERCISE_PLANNING and "exercise_context" in goal.slots:
                # Map the refined context to an appropriate exercise_context value
                context_lower = refined_context.lower()
                if any(kw in context_lower for kw in ["desk", "work", "office", "sitting", "computer", "while working"]):
                    goal.fill_slot("exercise_context", "desk_exercises")
                    print(f"[GOAL_DRIVEN] Updated exercise_context to 'desk_exercises' based on refinement")
                elif any(kw in context_lower for kw in ["quick", "short", "5 minute", "10 minute", "brief", "break"]):
                    goal.fill_slot("exercise_context", "quick_breaks")
                    print(f"[GOAL_DRIVEN] Updated exercise_context to 'quick_breaks' based on refinement")
                elif any(kw in context_lower for kw in ["travel", "hotel", "trip", "on the go"]):
                    goal.fill_slot("exercise_context", "travel")
                    print(f"[GOAL_DRIVEN] Updated exercise_context to 'travel' based on refinement")

            # Acknowledge the refinement and continue with updated context
            acknowledgment = await self._generate_refinement_acknowledgment(
                refined_context=refined_context,
                goal=goal,
                patient_context=patient_context,
            )
            return {
                "messages": [AIMessage(content=acknowledgment)],
                "last_assistant_action": AssistantAction.ACKNOWLEDGED.value,
                "active_goal": serialize_goal(goal),
                "is_request_refinement": False,  # Reset the flag
                "refined_context": None,
            }

        # Handle clarification requests - explain the slot instead of repeating
        if is_clarification and last_asked_slot:
            explanation = await self._explain_slot(
                slot_name=last_asked_slot,
                goal=goal,
                patient_context=patient_context,
                user_text=user_text,
            )
            return {
                "messages": [AIMessage(content=explanation)],
                "last_assistant_action": AssistantAction.EXPLAINED_SLOT.value,
                "active_goal": serialize_goal(goal),
                "is_clarification_request": False,  # Reset the flag
            }

        # Try to extract slot values from user message
        extracted_slots = await self._extract_slot_values(
            user_text=user_text,
            goal=goal,
            patient_context=patient_context,
            messages=messages,  # Pass conversation history for context
        )

        # Fill extracted slots
        print(f"[GOAL_DRIVEN] Extracted slots from LLM: {extracted_slots}")
        for slot_name, slot_value in extracted_slots.items():
            goal.fill_slot(slot_name, slot_value)
            print(f"[GOAL_DRIVEN] Filled slot {slot_name} = {slot_value}")

        # Log current slot state after extraction
        print(f"[GOAL_DRIVEN] After extraction - missing required slots: {goal.get_missing_required_slots()}")
        print(f"[GOAL_DRIVEN] After extraction - filled slots: {goal.get_filled_slots()}")

        # Check if goal is complete
        if goal.is_complete():
            # Generate goal completion output
            response_text = await self._generate_goal_completion(goal, patient_context)
            goal.completed_at = datetime.now()

            return {
                "messages": [AIMessage(content=response_text)],
                "last_assistant_action": AssistantAction.COMPLETED_GOAL.value,
                "active_goal": serialize_goal(goal),
                "goal_history": state.get("goal_history", []) + [serialize_goal(goal)],
                "last_asked_slot": None,  # Clear the slot tracking
            }
        else:
            # Ask for next missing slot - using CONVERSATIONAL approach
            missing = goal.get_missing_required_slots()
            if missing:
                next_slot = missing[0]
                filled_slots = goal.get_filled_slots()

                # Generate a conversational question that builds on context
                response_text = await self._generate_conversational_slot_question(
                    goal=goal,
                    next_slot=next_slot,
                    filled_slots=filled_slots,
                    patient_context=patient_context,
                    user_text=user_text,
                )

                serialized = serialize_goal(goal)
                print(f"[GOAL_DRIVEN] Returning - asking for slot '{next_slot}'")
                print(f"[GOAL_DRIVEN] Serialized goal progress: {serialized['progress']}")
                for sn, si in serialized['slots'].items():
                    print(f"[GOAL_DRIVEN] Serialized slot '{sn}': filled={si['filled']}, value={si['value']}")
                return {
                    "messages": [AIMessage(content=response_text)],
                    "last_assistant_action": AssistantAction.ASKED_FOR_SLOT.value,
                    "active_goal": serialized,
                    "last_asked_slot": next_slot,  # Track which slot we're asking for
                }
            else:
                # All required slots filled, offer to proceed with understanding confirmation
                filled_summary = self._format_filled_slots_summary(goal)
                response_text = f"Let me make sure I have this right: {filled_summary}\n\nDoes that sound correct? If so, I'll create your personalized plan."

            return {
                "messages": [AIMessage(content=response_text)],
                "last_assistant_action": AssistantAction.COLLECTED_SLOT.value if extracted_slots else AssistantAction.ASKED_CLARIFICATION.value,
                "active_goal": serialize_goal(goal),
                "last_asked_slot": None,
            }

    async def _explain_slot(
        self,
        slot_name: str,
        goal: ActiveGoal,
        patient_context: Dict[str, Any],
        user_text: str,
    ) -> str:
        """
        Generate an explanation of what a slot means when user asks for clarification.

        Args:
            slot_name: Name of the slot to explain
            goal: The active goal
            patient_context: Patient context
            user_text: What the user said

        Returns:
            Explanation text
        """
        slot = goal.slots.get(slot_name)
        if not slot:
            return "I'm sorry, I'm not sure what you're asking about. Could you tell me more?"

        # Build a context-aware explanation
        slot_explanations = {
            "condition": (
                "I'm asking about your medical condition - for example, if you have Crohn's disease, "
                "rheumatoid arthritis, lupus, or another condition. This helps me tailor the diet plan "
                "to your specific needs, as different conditions benefit from different nutritional approaches."
            ),
            "dietary_restrictions": (
                "I'm asking about any foods you can't or don't want to eat - this could include allergies "
                "(like gluten, dairy, nuts), intolerances, or personal preferences (vegetarian, vegan, etc.). "
                "This ensures I don't suggest foods that could harm you or that you don't want."
            ),
            "goals": (
                "I'm asking what you'd like to achieve with this diet plan - for example, reducing inflammation, "
                "managing symptoms like bloating or gas, losing weight, gaining energy, or improving gut health. "
                "Your goals help me prioritize the right foods and meal patterns for you."
            ),
            "fitness_level": (
                "I'm asking about your current activity level - are you a beginner who hasn't exercised much, "
                "intermediate with some regular activity, or advanced/athletic? This helps me suggest "
                "appropriate exercises that won't be too easy or too challenging."
            ),
            "limitations": (
                "I'm asking about any physical limitations that might affect exercise - joint pain, "
                "mobility issues, injuries, or activities you need to avoid due to your condition. "
                "This ensures the exercises are safe for you."
            ),
            "disease": (
                "I'm asking which disease or condition you'd like to learn more about. For example, "
                "you might want to understand Crohn's disease, lupus, rheumatoid arthritis, or another condition."
            ),
            "medications": (
                "I'm asking about the medications you're currently taking. This helps me provide "
                "relevant information about managing them, potential interactions, and timing."
            ),
            "primary_concern": (
                "I'm asking about what's been on your mind or causing you stress - it could be anxiety "
                "about your condition, feeling overwhelmed, relationship challenges, or anything else "
                "you'd like support with."
            ),
            "exercise_context": (
                "I'm asking what type of exercises you're looking for. For example:\n"
                "- **Desk exercises** - stretches and movements you can do at your desk during work\n"
                "- **Quick breaks** - short 5-10 minute routines for energy boosts\n"
                "- **Full routine** - a complete weekly workout plan\n"
                "- **Travel exercises** - movements you can do in a hotel or while on the go\n\n"
                "This helps me tailor the exercises to fit your lifestyle and available time."
            ),
        }

        # Get specific explanation or generate one
        explanation = slot_explanations.get(slot_name)

        if not explanation:
            # Generate explanation using LLM for unknown slots
            try:
                prompt = f"""The user asked for clarification about a question I asked.

The slot I was asking about: "{slot_name}"
Slot description: "{slot.description}"
Goal type: {goal.goal_type.value}
User said: "{user_text}"

Generate a helpful, friendly explanation (2-3 sentences) of what information I need and why it's helpful.
Be specific and give examples if relevant."""

                response = await self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful medical assistant explaining what information you need."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=150,
                )
                explanation = response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Failed to generate slot explanation: {e}")
                explanation = f"I'm asking about {slot.description.lower()}. This information helps me create a better personalized plan for you."

        # Check if patient has known conditions and mention them
        conditions = patient_context.get("active_conditions", [])
        if slot_name == "condition" and conditions:
            condition_list = ", ".join(conditions[:3])
            explanation += f"\n\nBased on your records, I can see you have: {condition_list}. Would you like me to use this information, or is there a different condition you'd like to focus on?"

        return explanation

    async def _generate_refinement_acknowledgment(
        self,
        refined_context: str,
        goal: ActiveGoal,
        patient_context: Dict[str, Any],
    ) -> str:
        """
        Generate an acknowledgment when user refines their request.

        This is called when the classifier detects is_request_refinement=true,
        meaning the user is correcting or clarifying what they actually want.

        Args:
            refined_context: What the user actually wants
            goal: The active goal (may have been updated with new context)
            patient_context: Patient context

        Returns:
            Acknowledgment message that shows understanding and continues appropriately
        """
        system_prompt = self._build_persona_prompt(patient_context)

        # Get filled slots and missing slots
        filled_slots = goal.get_filled_slots()
        missing_slots = goal.get_missing_required_slots()

        prompt = f"""The user has clarified/refined their request. They were asking for something different than what I provided.

What they actually want: "{refined_context}"

Current goal: {goal.goal_type.value}
Information I already have: {self._format_filled_slots_for_prompt(filled_slots) or "Just starting"}
Still need to ask about: {', '.join(missing_slots) if missing_slots else "Nothing - ready to generate"}

Generate a brief (2-3 sentences max) response that:
1. Acknowledges you understand what they're REALLY asking for (show you "got it")
2. Don't apologize excessively - just pivot smoothly
3. Either ask for the next needed piece of info, OR if all info is gathered, confirm you'll provide what they want

Examples:
- "Ah, you're looking for quick exercises you can do right at your desk during work breaks - that makes much more sense! Let me put together some practical desk stretches for you."
- "Got it - you want something you can do without leaving your chair during the workday. With your Crohn's in mind, I'll focus on gentle stretches that won't cause any discomfort."
- "I understand now - you need exercises for between meetings, not a full workout routine. Given that you mentioned yoga, should I include some quick yoga-inspired stretches?

Be natural and conversational. Show that you listened."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Failed to generate refinement acknowledgment: {e}")
            # Fallback response
            return f"Got it - you're looking for {refined_context}. Let me adjust what I provide for you."

    async def _extract_slot_values(
        self,
        user_text: str,
        goal: ActiveGoal,
        patient_context: Dict[str, Any],
        messages: List[Any] = None,
    ) -> Dict[str, Any]:
        """Extract slot values from user message using LLM.

        Args:
            user_text: The current user message
            goal: The active goal being worked on
            patient_context: Patient medical context
            messages: Full conversation history for context
        """

        missing_slots = goal.get_missing_required_slots()
        if not missing_slots:
            return {}

        # Build extraction prompt
        slots_info = []
        for slot_name in missing_slots:
            if slot_name in goal.slots:
                slot = goal.slots[slot_name]
                slots_info.append(f"- {slot_name}: {slot.description}")

        # Determine which slot we're currently asking for (first missing slot)
        current_slot = missing_slots[0] if missing_slots else None

        # Build conversation history context (last 10 messages for context)
        conversation_context = ""
        if messages and len(messages) > 1:
            recent_messages = messages[-10:]  # Last 10 messages max
            history_lines = []
            for msg in recent_messages[:-1]:  # Exclude current message
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                history_lines.append(f"{role}: {content}")
            if history_lines:
                conversation_context = f"""
CONVERSATION HISTORY (for context - user may reference earlier statements):
{chr(10).join(history_lines)}
---
"""

        prompt = f"""Extract information from this user message for a {goal.goal_type.value} goal.
{conversation_context}
Current user message: "{user_text}"

We are currently asking about: {current_slot}

Slots we need (extract ANY that are mentioned or implied):
{chr(10).join(slots_info)}

Patient context:
- Known conditions: {', '.join(patient_context.get('active_conditions', [])) or 'None known'}
- Known medications: {', '.join(patient_context.get('current_medications', [])) or 'None known'}

EXTRACTION RULES:

1. **CONDITION slot** - Extract ANY of these:
   - Explicit conditions: "Crohn's", "lupus", "diabetes" → extract the condition name
   - NO condition: "I don't have any condition", "no conditions", "healthy" → extract as "none"
   - IMPLIED conditions from context: "ostomy bag" → "ostomy/colostomy", "insulin" → "diabetes"
   - If user says they can eat anything/no restrictions → this might mean no condition, extract "none"
   - **REFERENCES TO EARLIER**: "my conditions mentioned before", "as I said", "same as before" → look at CONVERSATION HISTORY above to find what they mentioned

2. **DIETARY_RESTRICTIONS slot** - Extract ANY of these:
   - Specific restrictions: "vegetarian", "gluten-free", "no dairy" → extract as stated
   - NO restrictions: "I can eat anything", "no restrictions", "none" → extract as "none"
   - **REFERENCES**: "same restrictions as before", "what I mentioned" → look at CONVERSATION HISTORY

3. **GOALS slot** - Extract health/diet objectives:
   - "reduce gas", "lose weight", "more energy", "less bloating" → extract the goal
   - Multiple goals are OK: "reduce gas and boost energy" → extract all

4. **EXERCISE_CONTEXT slot** (for exercise planning) - Extract the TYPE/CONTEXT of exercise:
   - DESK/OFFICE: "while working", "at my desk", "during work", "office exercises", "between meetings", "at the computer" → extract as "desk_exercises"
   - QUICK/SHORT: "quick exercises", "5 minutes", "short routine", "brief stretch", "micro-breaks" → extract as "quick_breaks"
   - TRAVEL: "while traveling", "in a hotel", "on trips", "on the go" → extract as "travel"
   - FULL ROUTINE: "weekly plan", "full workout", "exercise routine", "regular exercise" → extract as "full_routine"
   - IMPLIED from context: User mentions "work schedule", "software engineer", "sitting all day" → likely wants "desk_exercises"

5. **FITNESS_LEVEL slot** - Extract activity level:
   - "sedentary", "not very active", "don't exercise much" → extract as "sedentary"
   - "moderate", "somewhat active", "exercise sometimes" → extract as "moderate"
   - "active", "athletic", "exercise regularly", "do yoga" → extract as "active"

6. **LIMITATIONS slot** - Extract physical limitations:
   - "joint pain", "bad knees", "back problems" → extract the specific limitation
   - "no limitations", "healthy", "nothing specific" → extract as "none"

CRITICAL:
- If the user is answering the current question ({current_slot}) in ANY way - even negatively - extract that answer!
- If user REFERENCES earlier conversation ("mentioned before", "as I said", "my diseases"), find that info in CONVERSATION HISTORY

Examples:
- "I don't have any condition that stops me eating" → {{"condition": "none"}}
- "No dietary restrictions" → {{"dietary_restrictions": "none"}}
- "I have Crohn's" → {{"condition": "Crohn's disease"}}
- "Boost energy and reduce gas for my ostomy bag" → {{"goals": "boost energy and reduce gas", "condition": "ostomy"}}
- "I want to lose weight" → {{"goals": "weight loss"}}
- "apart from my diseases mentioned before, nothing" → Look in history, find the disease, extract it
- "I work as a software engineer" → {{"exercise_context": "desk_exercises"}} (implied from sedentary job)
- "something I can do at my desk" → {{"exercise_context": "desk_exercises"}}
- "while I'm working" → {{"exercise_context": "desk_exercises"}}
- "quick stretches during the day" → {{"exercise_context": "quick_breaks"}}
- "a full weekly workout" → {{"exercise_context": "full_routine"}}
- "I do yoga and stretching" → {{"fitness_level": "active"}}

Return JSON with extracted values. Only return {{}} if the message is completely off-topic (like "what time is it?")."""

        # Debug logging for conversation context
        history_count = len(messages) - 1 if messages else 0
        print(f"[SLOT_EXTRACT] Extracting from: '{user_text}'")
        print(f"[SLOT_EXTRACT] Conversation history available: {history_count} prior messages")
        if conversation_context:
            print(f"[SLOT_EXTRACT] History included in prompt (chars): {len(conversation_context)}")

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an information extractor. Extract slot values from user messages. Return only valid JSON with the extracted values. IMPORTANT: When user references earlier conversation, look in the CONVERSATION HISTORY provided to find that information."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            raw_response = response.choices[0].message.content
            print(f"[SLOT_EXTRACT] Raw LLM response: {raw_response}")
            extracted = json.loads(raw_response)
            print(f"[SLOT_EXTRACT] Parsed extraction: {extracted}")
            return extracted

        except Exception as e:
            logger.warning(f"Slot extraction failed: {e}")
            print(f"[SLOT_EXTRACT] Exception: {e}")
            return {}

    async def _generate_conversational_slot_question(
        self,
        goal: ActiveGoal,
        next_slot: str,
        filled_slots: Dict[str, Any],
        patient_context: Dict[str, Any],
        user_text: str,
    ) -> str:
        """
        Generate a conversational question for collecting slot information.

        Instead of form-like "Great, noted. What about X?", generates natural
        dialogue that acknowledges context and explains why we need the information.

        Args:
            goal: The active goal
            next_slot: Name of the slot to ask for
            filled_slots: Already collected slot values
            patient_context: Patient context
            user_text: What the user just said

        Returns:
            Natural conversational question
        """
        slot = goal.slots.get(next_slot)
        if not slot:
            return get_slot_question(goal.goal_type, next_slot)

        # Build context-aware prompt for generating natural question
        goal_type_friendly = goal.goal_type.value.replace("_", " ")
        progress_info = f"{len(filled_slots)}/{len([s for s in goal.slots.values() if s.required])}"

        prompt = f"""You are Matucha, helping a patient with {goal_type_friendly}.

What the patient just told you: "{user_text}"

Information gathered so far:
{self._format_filled_slots_for_prompt(filled_slots) or "- Just starting the conversation"}

Next information needed: {next_slot}
What this means: {slot.description}

Patient context:
- Known conditions: {', '.join(patient_context.get('active_conditions', [])) or 'Not specified'}
- Known allergies: {', '.join(patient_context.get('allergies', [])) or 'None known'}

Generate a NATURAL follow-up that:
1. If we just collected information, briefly acknowledge what you learned (but don't just say "Great, noted")
2. Explain briefly WHY you need this next piece of information (how it helps their plan)
3. Ask the question in a warm, conversational way
4. Optionally give a helpful example or two

Keep it to 2-3 sentences max. Be conversational, not form-like.

Examples of GOOD responses:
- "I understand you have Crohn's - that really helps me tailor the diet to avoid trigger foods. Now, are there specific foods you already know don't agree with you, or any dietary preferences I should keep in mind?"
- "So you're looking to reduce inflammation and improve energy - great goals! To make this work for your lifestyle, are you already following any eating patterns like vegetarian, low-carb, or anything else?"

Examples of BAD responses (too form-like):
- "Great, I've noted that. Do you have any dietary restrictions?"
- "Okay. What are your goals for this diet plan?"

Generate only the response, nothing else."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are Matucha, a warm and professional medical assistant having a natural conversation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Failed to generate conversational question: {e}")
            # Fallback to template question with a nicer intro
            base_question = get_slot_question(goal.goal_type, next_slot)
            if filled_slots:
                return f"Thanks for sharing that - it really helps. {base_question}"
            else:
                return f"Let me help you with {goal.description.lower()}. {base_question}"

    def _format_filled_slots_for_prompt(self, filled_slots: Dict[str, Any]) -> str:
        """Format filled slots for inclusion in prompts."""
        if not filled_slots:
            return ""

        lines = []
        for name, value in filled_slots.items():
            friendly_name = name.replace("_", " ").title()
            lines.append(f"- {friendly_name}: {value}")
        return "\n".join(lines)

    def _format_filled_slots_summary(self, goal: ActiveGoal) -> str:
        """Format a human-readable summary of filled slots for confirmation."""
        filled = goal.get_filled_slots()
        if not filled:
            return "I haven't gathered any information yet."

        # Build natural summary based on goal type
        if goal.goal_type == GoalType.DIET_PLANNING:
            parts = []
            if "condition" in filled:
                parts.append(f"you have {filled['condition']}")
            if "dietary_restrictions" in filled:
                restrictions = filled["dietary_restrictions"]
                if restrictions.lower() in ["none", "no", "no restrictions"]:
                    parts.append("you don't have specific dietary restrictions")
                else:
                    parts.append(f"you follow a {restrictions} diet")
            if "goals" in filled:
                parts.append(f"you're looking to {filled['goals'].lower()}")
            return ", ".join(parts) if parts else str(filled)

        elif goal.goal_type == GoalType.EXERCISE_PLANNING:
            parts = []
            if "condition" in filled:
                parts.append(f"you have {filled['condition']}")
            if "fitness_level" in filled:
                parts.append(f"you're at a {filled['fitness_level']} fitness level")
            if "limitations" in filled:
                limitations = filled["limitations"]
                if limitations.lower() in ["none", "no", "no limitations"]:
                    parts.append("you don't have physical limitations")
                else:
                    parts.append(f"you need to be careful with {limitations}")
            return ", ".join(parts) if parts else str(filled)

        else:
            # Generic formatting for other goal types
            parts = []
            for name, value in filled.items():
                friendly_name = name.replace("_", " ")
                parts.append(f"{friendly_name}: {value}")
            return "; ".join(parts)

    async def _generate_goal_completion(
        self,
        goal: ActiveGoal,
        patient_context: Dict[str, Any],
    ) -> str:
        """Generate the goal completion output (meal plan, exercise routine, etc.)."""

        completion_prompt = get_completion_prompt(goal)
        system_prompt = self._build_persona_prompt(patient_context)

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": completion_prompt}
                ],
                temperature=0.6,
                max_tokens=1500,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Goal completion generation failed: {e}")
            return "I've gathered all the information. Let me prepare your personalized plan..."

    # ============================================================
    # CLOSING NODE
    # ============================================================

    async def closing_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Handle conversation closing gracefully.

        Summarizes what was discussed and offers follow-up.

        Args:
            state: Current conversation state

        Returns:
            Farewell message
        """
        messages = state.get("messages", [])
        explored_topics = state.get("explored_topics", [])
        patient_context = state.get("patient_context", {})

        last_message = messages[-1] if messages else None
        user_text = last_message.content if last_message else ""

        # Build closing message based on conversation content
        if explored_topics:
            topics_summary = ", ".join(explored_topics[:3])
            closing = f"It was great discussing {topics_summary} with you today. "
        else:
            closing = "Thank you for chatting with me today. "

        closing += "Take care, and don't hesitate to reach out if you have any more questions!"

        return {
            "messages": [AIMessage(content=closing)],
            "last_assistant_action": AssistantAction.SAID_FAREWELL.value,
        }

    # ============================================================
    # RESPONSE SYNTHESIZER NODE
    # ============================================================

    async def response_synthesizer_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Apply reflection pattern to improve response quality.

        Uses Generate → Reflect → Regenerate pattern to:
        - Check for stale information references
        - Ensure natural/empathetic tone
        - Ensure persona (Matucha) is present
        - Add confirmation in goal-driven mode

        Args:
            state: Current conversation state

        Returns:
            Polished response if changes needed, empty dict otherwise
        """
        messages = state.get("messages", [])
        if not messages:
            return {}

        # Get the last assistant message (just generated)
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return {}

        draft_response = last_message.content
        patient_context = state.get("patient_context", {})
        turn_count = state.get("turn_count", 0)
        mode = state.get("mode", "casual_chat")

        # Build reflection prompt
        # Check if this is a returning user - they already know Matucha!
        returning_user = state.get("returning_user", False)
        reflection_prompt = self._build_reflection_prompt(
            draft_response=draft_response,
            patient_context=patient_context,
            turn_count=turn_count,
            mode=mode,
            recently_resolved=patient_context.get("recently_resolved", []),
            historical_conditions=patient_context.get("historical_conditions", []),
            returning_user=returning_user,
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a response quality reviewer. Analyze the draft and improve it if needed."},
                    {"role": "user", "content": reflection_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)

            needs_revision = result.get("needs_revision", False)
            revised_response = result.get("revised_response", "")
            issues_found = result.get("issues_found", [])

            if issues_found:
                logger.debug(f"Reflection found issues: {issues_found}")

            if needs_revision and revised_response:
                logger.info(f"Response refined by reflection: {', '.join(issues_found)}")
                # Replace the last message with the refined version
                # We need to return the updated message list
                updated_messages = messages[:-1] + [AIMessage(content=revised_response)]
                return {"messages": updated_messages[-1:]}  # Only return the new message to add

            return {}  # No changes needed

        except Exception as e:
            logger.warning(f"Reflection failed, keeping original response: {e}")
            return {}

    def _build_reflection_prompt(
        self,
        draft_response: str,
        patient_context: Dict[str, Any],
        turn_count: int,
        mode: str,
        recently_resolved: List[str],
        historical_conditions: List[str],
        returning_user: bool = False,
    ) -> str:
        """Build the reflection prompt for response quality checking."""

        # Format context for reflection
        active_conditions = patient_context.get("active_conditions", [])
        context_timestamp = patient_context.get("context_timestamp", "")

        return f"""Review this draft response before sending to the patient.

DRAFT RESPONSE:
"{draft_response}"

CONTEXT:
- Turn number: {turn_count}
- Conversation mode: {mode}
- Active conditions (recent): {', '.join(active_conditions) if active_conditions else 'None'}
- Historical conditions (stale, do NOT mention): {', '.join(historical_conditions) if historical_conditions else 'None'}
- Recently resolved (can congratulate): {', '.join(recently_resolved) if recently_resolved else 'None'}
- Context timestamp: {context_timestamp}

CHECK FOR THESE ISSUES:

1. **Stale Information** (CRITICAL):
   - Does the response mention any condition from the "historical conditions" list?
   - Does it reference symptoms/issues that may be outdated?
   - If YES → Remove or add "Based on your recent history..." qualifier

2. **Persona Presence**:
   - Is this a RETURNING user? {returning_user}
   - If RETURNING user: DO NOT add self-introduction - they already know Matucha!
   - If NEW user (not returning) and turn 1 with no intro → Add a brief intro
   - CRITICAL: For returning users, NEVER add "I'm Matucha" or "your medical assistant"

3. **Natural Tone**:
   - Does it sound mechanical or scripted? (e.g., "Great, I've noted that. Next question?")
   - If mechanical → Rewrite to sound more natural and conversational

4. **Goal-Driven Confirmation**:
   - If mode is "goal_driven" and asking for information, does it confirm understanding first?
   - Good: "So you have Crohn's disease - that helps me understand your needs. Now..."
   - Bad: "Great, noted. What about dietary restrictions?"

5. **Tone Appropriateness**:
   - Is the response MATCHING the patient's tone?
   - If they asked a practical question, does it answer directly WITHOUT emotional preambles?
   - REMOVE phrases like "I know [condition] can be challenging" - this is condescending
   - Only add empathy if the patient expressed distress/frustration

Return JSON with:
{{
    "needs_revision": true/false,
    "issues_found": ["list of issues found"],
    "revised_response": "the improved response if needed, or empty string if no changes"
}}

If no issues found, return {{"needs_revision": false, "issues_found": [], "revised_response": ""}}"""

    # ============================================================
    # MEMORY PERSIST NODE
    # ============================================================

    async def memory_persist_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Persist conversation state to memory layers.

        - Updates Redis with session state
        - Stores facts in Mem0
        - Updates Neo4j patient records if new medical facts

        Args:
            state: Current conversation state

        Returns:
            Empty dict (side effects only)
        """
        if not self.patient_memory:
            return {}

        patient_id = state.get("patient_id")
        session_id = state.get("session_id")
        messages = state.get("messages", [])

        if not patient_id or len(messages) < 2:
            return {}

        try:
            # Get last user and assistant messages
            recent_messages = messages[-2:]
            user_msg = None
            assistant_msg = None

            for msg in recent_messages:
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                elif isinstance(msg, AIMessage):
                    assistant_msg = msg.content

            if user_msg and assistant_msg:
                # Store conversation in memory service (Mem0 + Redis + Neo4j)
                from application.services.patient_memory_service import ConversationMessage

                await self.patient_memory.store_message(
                    ConversationMessage(
                        role="user",
                        content=user_msg,
                        timestamp=datetime.now(),
                        patient_id=patient_id,
                        session_id=session_id,
                    )
                )

                await self.patient_memory.store_message(
                    ConversationMessage(
                        role="assistant",
                        content=assistant_msg,
                        timestamp=datetime.now(),
                        patient_id=patient_id,
                        session_id=session_id,
                        metadata={
                            "mode": state.get("mode"),
                            "topics": state.get("current_topics", []),
                        }
                    )
                )

                logger.debug(f"Persisted conversation for patient {patient_id}")

                # Extract and store medical facts (diagnoses, medications, allergies) to Neo4j
                await self._extract_and_store_medical_facts(user_msg, patient_id)

                # Also store as episodic memory in Graphiti (if available)
                if self.episodic_memory and session_id:
                    try:
                        turn_count = state.get("turn_count", 1)
                        mode = state.get("mode")
                        topics = state.get("current_topics", [])

                        episode_result = await self.episodic_memory.store_turn_episode(
                            patient_id=patient_id,
                            session_id=session_id,
                            user_message=user_msg,
                            assistant_message=assistant_msg,
                            turn_number=turn_count,
                            mode=mode.value if hasattr(mode, 'value') else str(mode) if mode else None,
                            topics=topics,
                        )

                        logger.debug(
                            f"Stored episodic memory: episode={episode_result.episode_id}, "
                            f"entities={len(episode_result.entities_extracted)}, "
                            f"relationships={episode_result.relationships_created}, "
                            f"time={episode_result.processing_time_ms:.1f}ms"
                        )

                    except Exception as ep_error:
                        # Don't fail the whole operation if episodic storage fails
                        logger.warning(f"Episodic memory storage failed (non-critical): {ep_error}")

        except Exception as e:
            logger.error(f"Memory persistence failed: {e}")

        return {}

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _build_persona_prompt(self, patient_context: Dict[str, Any]) -> str:
        """Build the system prompt with persona characteristics."""

        prompt = f"""You are {self.persona_name}, a warm and professional medical assistant.

Your personality:
- Practical and helpful - answer questions directly
- Knowledgeable and precise with medical information
- Patient and thorough in explanations
- Safety-conscious - recommend professional consultation for serious concerns
- Natural conversational style - not scripted or robotic

CRITICAL TONE GUIDELINES:
- DO NOT be condescending. Patients with chronic conditions KNOW their condition is difficult.
- AVOID phrases like "I know [condition] can be challenging" or "Living with [condition] is hard"
- For practical questions (diet, exercise, medication), just answer directly
- Only show emotional support when they EXPRESS emotional distress
- Treat them as a capable adult who wants information, not pity

General guidelines:
- Use clear, accessible language (avoid excessive jargon)
- Remember context from the conversation
- Be helpful but honest about limitations
- Include safety warnings when appropriate"""

        if patient_context:
            conditions = patient_context.get("active_conditions", [])
            allergies = patient_context.get("allergies", [])

            if conditions or allergies:
                prompt += f"""

Patient-specific considerations:
- Always consider their conditions: {', '.join(conditions) if conditions else 'None known'}
- Watch for allergies: {', '.join(allergies) if allergies else 'None known'}
- Personalize advice to their situation"""

        return prompt

    async def _extract_and_store_medical_facts(
        self,
        message: str,
        patient_id: str
    ) -> None:
        """
        Extract medical facts (diagnoses, medications, allergies) from user message
        and store them in Neo4j via patient_memory service.

        This enables the patient's medical graph to be built from conversations.
        """
        if not self.patient_memory:
            return

        prompt = """Analyze this patient message and extract any medical facts they mention about themselves.

Return a JSON object with these arrays (empty if none found):
- diagnoses: [{condition: "disease name", details: "any additional info"}]
- medications: [{name: "drug name", dosage: "if mentioned", frequency: "if mentioned"}]
- stopped_medications: [{name: "drug name", reason: "why stopped if mentioned"}]
- resolved_conditions: [{condition: "condition name", details: "any info about resolution"}]
- allergies: [{substance: "allergen", reaction: "if mentioned", severity: "mild/moderate/severe if mentioned"}]
- procedures: [{name: "procedure name", type: "test/surgery/screening/imaging", scheduled_date: "if mentioned", status: "scheduled/completed/cancelled", notes: "any details"}]
- medical_devices: [{name: "device name", type: "stoma/implant/prosthetic/pump/monitor", status: "active/removed", location: "body location if mentioned", notes: "any details"}]
- corrected_medications: [{wrong_name: "the incorrect name", correct_name: "the correct name if given", reason: "explanation"}]
- denied_medications: [{name: "drug name", reason: "why denied"}]
- denied_diagnoses: [{condition: "condition name", reason: "why denied"}]
- denied_allergies: [{substance: "allergen", reason: "why denied"}]

PROCEDURES & TESTS - Extract these:
- "I have a colonoscopy scheduled" → add to procedures with status="scheduled"
- "I had an MRI last week" → add to procedures with status="completed"
- "my colonoscopy is next month" → add to procedures with scheduled_date
- Examples: colonoscopy, endoscopy, MRI, CT scan, blood test, biopsy, EKG, ultrasound, X-ray, surgery

MEDICAL DEVICES & IMPLANTS - Extract these (VERY IMPORTANT for care planning):
- "I have a colostomy" / "I have a colostomy bag" → add to medical_devices with type="stoma"
- "I have an ileostomy" / "I have an ostomy" → add to medical_devices with type="stoma"
- "I have a pacemaker" → add to medical_devices with type="implant"
- "I use an insulin pump" → add to medical_devices with type="pump"
- Examples: colostomy, ileostomy, urostomy, pacemaker, insulin pump, cochlear implant, feeding tube, port-a-cath

IMPORTANT: Distinguish between:
- "I take ibuprofen" → add to medications
- "I stopped taking ibuprofen" / "I no longer take ibuprofen" → add to stopped_medications

IMPORTANT: Detect RESOLVED conditions:
- "I no longer have knee pain" → add to resolved_conditions
- "my headache is gone" → add to resolved_conditions

IMPORTANT: Detect CORRECTIONS and DENIALS:
- "Moudel was a typo" → add to corrected_medications with wrong_name="Moudel"
- "I don't take Moudel" → add to denied_medications
- "I don't have diabetes" → add to denied_diagnoses
- "I'm not allergic to X" → add to denied_allergies

Only extract facts the patient explicitly states about THEMSELVES (not general questions).
"I have Crohn's disease" is a diagnosis. "What is Crohn's disease?" is NOT.

Patient message: """ + message

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical entity extractor. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)

            # Store extracted diagnoses
            for dx in result.get("diagnoses", []):
                if dx.get("condition"):
                    try:
                        await self.patient_memory.add_diagnosis(
                            patient_id=patient_id,
                            condition=dx["condition"],
                            metadata={"details": dx.get("details", ""), "source": "conversation"}
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Stored diagnosis: {dx['condition']} for {patient_id}")
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
                                    f"[MEDICAL_EXTRACTION] Stored medication (fuzzy match): "
                                    f"'{med['name']}' -> '{validation.validated_name}' "
                                    f"(confidence: {validation.confidence:.0%}) for {patient_id}"
                                )
                            else:
                                logger.info(f"[MEDICAL_EXTRACTION] Stored medication: {validation.validated_name} for {patient_id}")
                        else:
                            # Log unrecognized medications for review
                            logger.warning(
                                f"[MEDICAL_EXTRACTION] Unrecognized medication rejected: '{med['name']}' "
                                f"for {patient_id}. Suggestions: {validation.suggestions}. "
                                f"Message: {validation.message}"
                            )
                            # Store in a pending/unverified state for manual review
                            # This prevents typos like "Moudel" from being stored as valid medications
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

            # Handle stopped medications
            for stopped_med in result.get("stopped_medications", []):
                if stopped_med.get("name"):
                    try:
                        await self.patient_memory.remove_medication(
                            patient_id=patient_id,
                            medication_name=stopped_med["name"],
                            reason=stopped_med.get("reason", "Patient reported discontinuation")
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Discontinued medication: {stopped_med['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to discontinue medication: {e}")

            # Handle resolved conditions
            for resolved in result.get("resolved_conditions", []):
                if resolved.get("condition"):
                    try:
                        await self.patient_memory.resolve_diagnosis(
                            patient_id=patient_id,
                            diagnosis_name=resolved["condition"],
                            resolution_reason=resolved.get("details", "Patient reported condition resolved")
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Resolved condition: {resolved['condition']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to resolve condition: {e}")

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
                        logger.info(f"[MEDICAL_EXTRACTION] Stored allergy: {allergy['substance']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store allergy: {e}")

            # Store extracted procedures and tests (colonoscopy, MRI, blood test, etc.)
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
                        logger.info(f"[MEDICAL_EXTRACTION] Stored procedure: {procedure['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store procedure: {e}")

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
                        logger.info(f"[MEDICAL_EXTRACTION] Stored medical device: {device['name']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store medical device: {e}")

            # Handle CORRECTED medications (e.g., "Moudel was a typo, I meant Imurel")
            for correction in result.get("corrected_medications", []):
                wrong_name = correction.get("wrong_name")
                correct_name = correction.get("correct_name")
                if wrong_name:
                    try:
                        # Remove the wrong medication
                        await self.patient_memory.remove_medication(
                            patient_id=patient_id,
                            medication_name=wrong_name,
                            reason=f"Correction: {correction.get('reason', 'Patient corrected a mistake')}"
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Removed incorrect medication: {wrong_name} for {patient_id}")

                        # Also remove from pending if it was stored there
                        await self.patient_memory.remove_pending_medication(
                            patient_id=patient_id,
                            medication_name=wrong_name
                        )

                        # If they provided a correct name, validate and add it
                        if correct_name:
                            validation = validator.validate(correct_name)
                            if validation.is_valid:
                                await self.patient_memory.add_medication(
                                    patient_id=patient_id,
                                    name=validation.validated_name,
                                    dosage="unknown",
                                    frequency="unknown"
                                )
                                logger.info(f"[MEDICAL_EXTRACTION] Added corrected medication: {validation.validated_name} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to process medication correction: {e}")

            # Handle DENIED medications (e.g., "I don't take Moudel")
            for denied in result.get("denied_medications", []):
                if denied.get("name"):
                    try:
                        await self.patient_memory.remove_medication(
                            patient_id=patient_id,
                            medication_name=denied["name"],
                            reason=f"Patient denial: {denied.get('reason', 'Patient stated they do not take this medication')}"
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Removed denied medication: {denied['name']} for {patient_id}")

                        # Also remove from pending
                        await self.patient_memory.remove_pending_medication(
                            patient_id=patient_id,
                            medication_name=denied["name"]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to remove denied medication: {e}")

            # Handle DENIED diagnoses (e.g., "I don't have diabetes")
            for denied in result.get("denied_diagnoses", []):
                if denied.get("condition"):
                    try:
                        await self.patient_memory.remove_diagnosis(
                            patient_id=patient_id,
                            diagnosis_name=denied["condition"],
                            reason=f"Patient denial: {denied.get('reason', 'Patient stated they do not have this condition')}"
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Removed denied diagnosis: {denied['condition']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to remove denied diagnosis: {e}")

            # Handle DENIED allergies (e.g., "I'm not allergic to penicillin")
            for denied in result.get("denied_allergies", []):
                if denied.get("substance"):
                    try:
                        await self.patient_memory.remove_allergy(
                            patient_id=patient_id,
                            substance=denied["substance"],
                            reason=f"Patient denial: {denied.get('reason', 'Patient stated they do not have this allergy')}"
                        )
                        logger.info(f"[MEDICAL_EXTRACTION] Removed denied allergy: {denied['substance']} for {patient_id}")
                    except Exception as e:
                        logger.warning(f"Failed to remove denied allergy: {e}")

        except Exception as e:
            logger.warning(f"Medical fact extraction failed: {e}")
