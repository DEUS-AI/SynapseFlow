"""
Goal Templates for GOAL_DRIVEN Conversation Mode.

Defines the slot templates for each goal type, specifying what
information needs to be collected before the goal can be completed.
"""

from typing import Dict, List, Callable, Any
from dataclasses import dataclass

from domain.conversation_state import GoalType, GoalSlot, ActiveGoal


@dataclass
class GoalTemplate:
    """Template for creating goals with predefined slots."""
    goal_type: GoalType
    description: str
    required_slots: List[Dict[str, str]]  # [{"name": ..., "description": ...}]
    optional_slots: List[Dict[str, str]]
    completion_action: str  # What to do when goal is complete


# === Goal Template Definitions ===

GOAL_TEMPLATES: Dict[GoalType, GoalTemplate] = {
    GoalType.DIET_PLANNING: GoalTemplate(
        goal_type=GoalType.DIET_PLANNING,
        description="Create a personalized diet plan considering medical conditions",
        required_slots=[
            {
                "name": "condition",
                "description": "Primary condition to plan diet for (e.g., Crohn's, lupus, RA)"
            },
            {
                "name": "dietary_restrictions",
                "description": "Any dietary restrictions or allergies"
            },
            {
                "name": "goals",
                "description": "Diet goals (e.g., anti-inflammatory, weight management, symptom reduction)"
            },
        ],
        optional_slots=[
            {
                "name": "calorie_target",
                "description": "Daily calorie target if known"
            },
            {
                "name": "meal_frequency",
                "description": "Preferred number of meals per day"
            },
            {
                "name": "budget",
                "description": "Budget considerations for meal planning"
            },
            {
                "name": "cooking_ability",
                "description": "Cooking skill level and time available"
            },
        ],
        completion_action="generate_meal_plan"
    ),

    GoalType.EXERCISE_PLANNING: GoalTemplate(
        goal_type=GoalType.EXERCISE_PLANNING,
        description="Design a safe exercise routine considering medical limitations",
        required_slots=[
            {
                "name": "condition",
                "description": "Medical condition(s) to consider"
            },
            {
                "name": "fitness_level",
                "description": "Current fitness level (sedentary, moderate, active)"
            },
            {
                "name": "limitations",
                "description": "Physical limitations or areas to avoid"
            },
            {
                "name": "exercise_context",
                "description": "Exercise context/type: 'full_routine' for weekly workout plan, 'desk_exercises' for office/work breaks, 'quick_breaks' for short 5-10 min sessions, 'travel' for on-the-go exercises"
            },
        ],
        optional_slots=[
            {
                "name": "available_equipment",
                "description": "Exercise equipment available (home, gym, none)"
            },
            {
                "name": "time_per_session",
                "description": "Time available per exercise session"
            },
            {
                "name": "frequency",
                "description": "Desired exercise frequency per week"
            },
            {
                "name": "goals",
                "description": "Exercise goals (strength, flexibility, endurance)"
            },
        ],
        completion_action="generate_exercise_routine"
    ),

    GoalType.DISEASE_EDUCATION: GoalTemplate(
        goal_type=GoalType.DISEASE_EDUCATION,
        description="Provide comprehensive education about a disease or condition",
        required_slots=[
            {
                "name": "disease",
                "description": "Disease or condition to learn about"
            },
            {
                "name": "depth_level",
                "description": "Desired depth (overview, detailed, comprehensive)"
            },
        ],
        optional_slots=[
            {
                "name": "specific_aspects",
                "description": "Specific aspects to focus on (causes, symptoms, treatments, prognosis)"
            },
            {
                "name": "personal_relevance",
                "description": "How this relates to the patient personally"
            },
            {
                "name": "prior_knowledge",
                "description": "What the patient already knows"
            },
        ],
        completion_action="generate_educational_content"
    ),

    GoalType.MEDICATION_MANAGEMENT: GoalTemplate(
        goal_type=GoalType.MEDICATION_MANAGEMENT,
        description="Help manage medications, understand interactions, and track adherence",
        required_slots=[
            {
                "name": "medications",
                "description": "Current medications to manage"
            },
        ],
        optional_slots=[
            {
                "name": "schedule",
                "description": "Current medication schedule"
            },
            {
                "name": "concerns",
                "description": "Specific concerns about medications"
            },
            {
                "name": "side_effects",
                "description": "Any side effects being experienced"
            },
            {
                "name": "adherence_issues",
                "description": "Challenges with taking medications as prescribed"
            },
        ],
        completion_action="generate_medication_guide"
    ),

    GoalType.MENTAL_HEALTH_SUPPORT: GoalTemplate(
        goal_type=GoalType.MENTAL_HEALTH_SUPPORT,
        description="Provide emotional support and coping strategies for chronic illness",
        required_slots=[
            {
                "name": "primary_concern",
                "description": "Main emotional/mental health concern"
            },
        ],
        optional_slots=[
            {
                "name": "triggers",
                "description": "Known triggers for distress"
            },
            {
                "name": "coping_strategies",
                "description": "Current coping strategies being used"
            },
            {
                "name": "support_network",
                "description": "Available support network (family, friends, professionals)"
            },
            {
                "name": "condition_context",
                "description": "How chronic illness relates to mental health"
            },
        ],
        completion_action="provide_support_resources"
    ),
}


# === Goal Detection Keywords ===
# Used to detect when a user might be initiating a goal

GOAL_DETECTION_PATTERNS: Dict[GoalType, List[str]] = {
    GoalType.DIET_PLANNING: [
        "diet", "meal plan", "eating", "food", "nutrition",
        "anti-inflammatory", "what to eat", "what should i eat",
        "foods to avoid", "healthy eating", "recipe",
    ],
    GoalType.EXERCISE_PLANNING: [
        "exercise", "workout", "fitness", "physical activity",
        "stretching", "strength training", "yoga", "movement",
        "staying active", "exercise routine", "safe exercises",
    ],
    GoalType.DISEASE_EDUCATION: [
        "tell me about", "explain", "what is", "how does",
        "learn about", "understand", "causes of", "symptoms of",
        "treatment for", "prognosis", "research on",
    ],
    GoalType.MEDICATION_MANAGEMENT: [
        "medication", "medicine", "drug", "prescription",
        "side effects", "interactions", "dosage", "taking my",
        "should i take", "missed dose", "refill",
    ],
    GoalType.MENTAL_HEALTH_SUPPORT: [
        "anxious", "depressed", "stressed", "overwhelmed",
        "coping", "mental health", "emotional", "feeling down",
        "support", "struggling", "worried", "scared",
    ],
}


def create_goal_from_template(goal_type: GoalType) -> ActiveGoal:
    """
    Create an ActiveGoal instance from a template.

    Args:
        goal_type: Type of goal to create

    Returns:
        New ActiveGoal with empty slots
    """
    template = GOAL_TEMPLATES[goal_type]

    goal = ActiveGoal(
        goal_type=goal_type,
        description=template.description,
    )

    # Add required slots
    for slot_def in template.required_slots:
        goal.slots[slot_def["name"]] = GoalSlot(
            name=slot_def["name"],
            description=slot_def["description"],
            required=True,
        )

    # Add optional slots
    for slot_def in template.optional_slots:
        goal.slots[slot_def["name"]] = GoalSlot(
            name=slot_def["name"],
            description=slot_def["description"],
            required=False,
        )

    return goal


def detect_goal_type(message: str) -> GoalType | None:
    """
    Detect if a message suggests a specific goal type.

    This is a simple keyword-based detection. The classifier node
    will use LLM for more sophisticated detection.

    Args:
        message: User message to analyze

    Returns:
        Detected GoalType or None
    """
    message_lower = message.lower()

    # Score each goal type by keyword matches
    scores: Dict[GoalType, int] = {}

    for goal_type, patterns in GOAL_DETECTION_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern in message_lower)
        if score > 0:
            scores[goal_type] = score

    if not scores:
        return None

    # Return the goal type with highest score
    return max(scores, key=scores.get)


def get_slot_question(goal_type: GoalType, slot_name: str) -> str:
    """
    Get a natural question to ask for filling a specific slot.

    Args:
        goal_type: Type of goal
        slot_name: Name of slot to fill

    Returns:
        Question string to ask user
    """
    questions = {
        GoalType.DIET_PLANNING: {
            "condition": "What condition would you like me to consider when planning your diet?",
            "dietary_restrictions": "Do you have any dietary restrictions or food allergies I should know about?",
            "goals": "What are your main goals for this diet plan? For example, reducing inflammation, managing weight, or improving energy?",
            "calorie_target": "Do you have a specific daily calorie target in mind?",
            "meal_frequency": "How many meals do you prefer to eat per day?",
            "budget": "Are there any budget considerations I should keep in mind for meal planning?",
            "cooking_ability": "How comfortable are you with cooking, and how much time do you typically have for meal preparation?",
        },
        GoalType.EXERCISE_PLANNING: {
            "condition": "What medical conditions should I consider when designing your exercise routine?",
            "fitness_level": "How would you describe your current fitness level - sedentary, moderately active, or very active?",
            "limitations": "Are there any physical limitations or areas of your body that we should be careful with?",
            "exercise_context": "What type of exercises are you looking for? A full weekly workout routine, quick desk exercises for work breaks, short 5-10 minute sessions, or exercises for traveling?",
            "available_equipment": "What exercise equipment do you have access to?",
            "time_per_session": "How much time can you dedicate to each exercise session?",
            "frequency": "How many times per week would you like to exercise?",
            "goals": "What are your main fitness goals - building strength, improving flexibility, or increasing endurance?",
        },
        GoalType.DISEASE_EDUCATION: {
            "disease": "Which disease or condition would you like to learn more about?",
            "depth_level": "How detailed would you like this explanation - a brief overview, moderate detail, or comprehensive deep-dive?",
            "specific_aspects": "Are there specific aspects you'd like to focus on, such as causes, symptoms, treatments, or prognosis?",
            "personal_relevance": "How does this relate to you personally? This helps me tailor the information.",
            "prior_knowledge": "What do you already know about this condition?",
        },
        GoalType.MEDICATION_MANAGEMENT: {
            "medications": "Which medications would you like help managing?",
            "schedule": "What is your current medication schedule?",
            "concerns": "Do you have any specific concerns about your medications?",
            "side_effects": "Are you experiencing any side effects?",
            "adherence_issues": "Are you having any challenges taking your medications as prescribed?",
        },
        GoalType.MENTAL_HEALTH_SUPPORT: {
            "primary_concern": "What's the main thing on your mind that's affecting your emotional well-being?",
            "triggers": "Have you noticed any specific triggers that make these feelings worse?",
            "coping_strategies": "What coping strategies have you tried so far?",
            "support_network": "Who do you have in your life that you can turn to for support?",
            "condition_context": "How do you feel your chronic illness affects your mental health?",
        },
    }

    goal_questions = questions.get(goal_type, {})
    return goal_questions.get(
        slot_name,
        f"Could you tell me about {slot_name.replace('_', ' ')}?"
    )


def _get_exercise_routine_prompt(filled_slots: Dict[str, Any]) -> str:
    """
    Generate context-appropriate exercise routine prompt based on exercise_context.

    Supports different types:
    - full_routine: Weekly workout plan with warm-up, cool-down
    - desk_exercises: Office-friendly exercises for work breaks
    - quick_breaks: Short 5-10 minute sessions
    - travel: Exercises that can be done while traveling
    """
    exercise_context = filled_slots.get('exercise_context', 'full_routine').lower()
    condition = filled_slots.get('condition', 'Not specified')
    fitness_level = filled_slots.get('fitness_level', 'Moderate')
    limitations = filled_slots.get('limitations', 'None specified')
    goals = filled_slots.get('goals', 'General fitness')

    base_context = f"""Patient Information:
- Condition: {condition}
- Fitness Level: {fitness_level}
- Limitations: {limitations}
- Goals: {goals}"""

    if 'desk' in exercise_context or 'work' in exercise_context or 'office' in exercise_context:
        return f"""{base_context}

Create a set of DESK EXERCISES and WORK BREAK stretches that can be done:
- While sitting at a desk or standing briefly
- Without any equipment
- In an office environment (discreet, professional)
- In 2-5 minute micro-breaks throughout the workday

Include:
1. 3-4 seated stretches (neck, shoulders, wrists, back)
2. 2-3 standing stretches (can be done next to the desk)
3. 2-3 exercises to reduce eye strain and improve posture
4. A suggested schedule (e.g., every 1-2 hours)

Keep each exercise description brief and practical. Focus on relieving tension from computer work."""

    elif 'quick' in exercise_context or 'short' in exercise_context or '5' in exercise_context or '10' in exercise_context:
        return f"""{base_context}
- Time Available: {filled_slots.get('time_per_session', '5-10 minutes')}

Create a QUICK EXERCISE ROUTINE (5-10 minutes) that:
- Can be done with minimal or no equipment
- Provides a burst of energy and stress relief
- Is suitable for doing at home or in a small space

Include:
1. 1-minute warm-up
2. 5-6 simple exercises (30-60 seconds each)
3. 1-minute cool-down stretches

Keep it energizing but manageable. Perfect for a morning boost or afternoon pick-me-up."""

    elif 'travel' in exercise_context or 'hotel' in exercise_context:
        return f"""{base_context}

Create a TRAVEL-FRIENDLY exercise routine that:
- Requires no equipment (bodyweight only)
- Can be done in a hotel room or small space
- Addresses stiffness from sitting during travel

Include:
1. Stretches to counteract travel stiffness
2. 5-6 bodyweight exercises suitable for hotel rooms
3. Tips for staying active during travel days"""

    else:
        # Default: full routine
        return f"""Design a safe exercise routine based on:
- Condition: {condition}
- Fitness Level: {fitness_level}
- Limitations: {limitations}
- Equipment: {filled_slots.get('available_equipment', 'Bodyweight only')}
- Time per Session: {filled_slots.get('time_per_session', '30 minutes')}
- Frequency: {filled_slots.get('frequency', '3 times per week')}
- Goals: {goals}

Create a weekly exercise plan with specific exercises, sets, reps, and modifications.
Include warm-up and cool-down. Emphasize safety and gradual progression."""


def get_completion_prompt(goal: ActiveGoal) -> str:
    """
    Get the prompt for generating goal completion output.

    Args:
        goal: Completed goal with filled slots

    Returns:
        Prompt string for LLM to generate completion output
    """
    template = GOAL_TEMPLATES[goal.goal_type]
    filled_slots = goal.get_filled_slots()

    prompts = {
        "generate_meal_plan": f"""Create a personalized meal plan based on:
- Condition: {filled_slots.get('condition', 'Not specified')}
- Dietary Restrictions: {filled_slots.get('dietary_restrictions', 'None specified')}
- Goals: {filled_slots.get('goals', 'General health')}
- Calorie Target: {filled_slots.get('calorie_target', 'Flexible')}
- Meals per Day: {filled_slots.get('meal_frequency', '3 main meals')}
- Budget: {filled_slots.get('budget', 'Flexible')}
- Cooking Ability: {filled_slots.get('cooking_ability', 'Moderate')}

Provide a 7-day meal plan with breakfast, lunch, dinner, and snacks.
Include foods that are beneficial for the condition and avoid trigger foods.
Make the recipes practical and accessible.""",

        "generate_exercise_routine": _get_exercise_routine_prompt(filled_slots),

        "generate_educational_content": f"""Provide education about:
- Disease/Condition: {filled_slots.get('disease', 'Not specified')}
- Depth Level: {filled_slots.get('depth_level', 'Moderate')}
- Focus Areas: {filled_slots.get('specific_aspects', 'All aspects')}
- Personal Context: {filled_slots.get('personal_relevance', 'General interest')}
- Prior Knowledge: {filled_slots.get('prior_knowledge', 'Basic understanding')}

Cover the pathophysiology, symptoms, diagnosis, treatment options, and prognosis.
Use clear language appropriate for the requested depth level.
Include recent research findings and practical implications.""",

        "generate_medication_guide": f"""Create a medication management guide for:
- Medications: {filled_slots.get('medications', 'Not specified')}
- Current Schedule: {filled_slots.get('schedule', 'Not specified')}
- Concerns: {filled_slots.get('concerns', 'None specified')}
- Side Effects: {filled_slots.get('side_effects', 'None reported')}
- Adherence Issues: {filled_slots.get('adherence_issues', 'None specified')}

Provide information about each medication, potential interactions, best times to take,
food interactions, and tips for maintaining adherence.
Include a suggested medication schedule.""",

        "provide_support_resources": f"""Provide mental health support for:
- Primary Concern: {filled_slots.get('primary_concern', 'Not specified')}
- Known Triggers: {filled_slots.get('triggers', 'Not specified')}
- Current Coping Strategies: {filled_slots.get('coping_strategies', 'None specified')}
- Support Network: {filled_slots.get('support_network', 'Not specified')}
- Chronic Illness Context: {filled_slots.get('condition_context', 'Not specified')}

Provide empathetic support, validate their feelings, and offer practical coping strategies.
Suggest resources for additional help (support groups, professional help, apps).
Emphasize that seeking help is a sign of strength.""",
    }

    return prompts.get(
        template.completion_action,
        f"Generate helpful content for {goal.goal_type.value}"
    )
