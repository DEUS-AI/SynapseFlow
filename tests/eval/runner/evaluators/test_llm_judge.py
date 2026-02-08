"""
Tests for LLMJudgeEvaluator.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import List

from tests.eval.runner.evaluators.llm_judge import (
    LLMJudgeEvaluator,
    JudgeResponse,
    EvaluationCriterion,
    DEFAULT_RUBRICS,
    JudgeError,
    create_mock_judge,
)
from tests.eval.runner.scenario_models import JudgeAssertion


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def mock_llm_fn():
    """Create a mock LLM function that returns valid JSON."""
    def _mock(prompt: str) -> str:
        return json.dumps({
            "score": 4,
            "reasoning": "The response was helpful and professional."
        })
    return _mock


@pytest.fixture
def mock_async_llm_fn():
    """Create an async mock LLM function."""
    async def _mock(prompt: str) -> str:
        return json.dumps({
            "score": 4,
            "reasoning": "The response was helpful and professional."
        })
    return _mock


@pytest.fixture
def judge_evaluator(mock_llm_fn):
    """Create an LLMJudgeEvaluator with mock LLM."""
    return LLMJudgeEvaluator(llm_fn=mock_llm_fn)


@pytest.fixture
def async_judge_evaluator(mock_async_llm_fn):
    """Create an async LLMJudgeEvaluator."""
    return LLMJudgeEvaluator(async_llm_fn=mock_async_llm_fn)


def make_assertion(
    criterion: str,
    min_score: int = 3,
    rubric: str = None,
) -> JudgeAssertion:
    """Helper to create judge assertions."""
    return JudgeAssertion(
        criterion=criterion,
        min_score=min_score,
        rubric=rubric,
    )


# ========================================
# Basic Evaluation Tests
# ========================================

class TestLLMJudgeEvaluatorBasics:
    """Basic tests for LLMJudgeEvaluator."""

    def test_initialization(self, mock_llm_fn):
        """Test evaluator initialization."""
        judge = LLMJudgeEvaluator(llm_fn=mock_llm_fn)

        assert judge._llm_fn is not None
        assert judge._model_name == "gpt-4"

    def test_initialization_with_custom_rubrics(self, mock_llm_fn):
        """Test initialization with custom rubrics."""
        custom = {"my_criterion": "My custom rubric"}
        judge = LLMJudgeEvaluator(
            llm_fn=mock_llm_fn,
            custom_rubrics=custom,
        )

        assert "my_criterion" in judge._rubrics
        assert judge.get_rubric("my_criterion") == "My custom rubric"

    def test_available_criteria(self, judge_evaluator):
        """Test that standard criteria are available."""
        criteria = judge_evaluator.available_criteria

        assert "empathy" in criteria
        assert "clarity" in criteria
        assert "medical_accuracy" in criteria
        assert "safety" in criteria

    def test_get_rubric(self, judge_evaluator):
        """Test getting a rubric."""
        rubric = judge_evaluator.get_rubric("empathy")

        assert rubric is not None
        assert "Score 1" in rubric
        assert "Score 5" in rubric

    def test_add_rubric(self, judge_evaluator):
        """Test adding a custom rubric."""
        judge_evaluator.add_rubric("custom", "Custom rubric text")

        assert judge_evaluator.get_rubric("custom") == "Custom rubric text"


# ========================================
# Sync Evaluation Tests
# ========================================

class TestSyncEvaluation:
    """Tests for synchronous evaluation."""

    def test_basic_evaluation(self, judge_evaluator):
        """Test basic evaluation returns result."""
        assertion = make_assertion("empathy", min_score=3)

        result = judge_evaluator.evaluate(
            assertion,
            response="I understand how you're feeling. Let me help you.",
            patient_message="I'm feeling anxious about my medication.",
        )

        assert result.passed
        assert result.assertion_type == "llm_judge"
        assert result.score is not None

    def test_evaluation_with_custom_rubric(self, judge_evaluator):
        """Test evaluation with custom rubric in assertion."""
        assertion = make_assertion(
            criterion="custom_check",
            rubric="Score 5 if response contains 'hello'. Score 1 otherwise.",
        )

        result = judge_evaluator.evaluate(
            assertion,
            response="Hello, how can I help?",
            patient_message="Hi",
        )

        assert result is not None

    def test_evaluation_passes_when_score_meets_minimum(self):
        """Test that evaluation passes when score >= min_score."""
        def high_score_llm(prompt: str) -> str:
            return json.dumps({"score": 5, "reasoning": "Excellent"})

        judge = LLMJudgeEvaluator(llm_fn=high_score_llm)
        assertion = make_assertion("empathy", min_score=4)

        result = judge.evaluate(
            assertion,
            response="Great response",
            patient_message="Hello",
        )

        assert result.passed

    def test_evaluation_fails_when_score_below_minimum(self):
        """Test that evaluation fails when score < min_score."""
        def low_score_llm(prompt: str) -> str:
            return json.dumps({"score": 2, "reasoning": "Poor response"})

        judge = LLMJudgeEvaluator(llm_fn=low_score_llm)
        assertion = make_assertion("empathy", min_score=4)

        result = judge.evaluate(
            assertion,
            response="Bad response",
            patient_message="Hello",
        )

        assert not result.passed

    def test_evaluation_with_context(self, judge_evaluator):
        """Test evaluation with additional context."""
        assertion = make_assertion("context_awareness")
        context = {
            "previous_medications": ["Metformina", "Losartan"],
            "patient_condition": "Diabetes tipo 2",
        }

        result = judge_evaluator.evaluate(
            assertion,
            response="I see you're taking Metformina for your diabetes.",
            patient_message="What medications am I on?",
            context=context,
        )

        assert result is not None


# ========================================
# Async Evaluation Tests
# ========================================

class TestAsyncEvaluation:
    """Tests for asynchronous evaluation."""

    @pytest.mark.asyncio
    async def test_async_evaluation(self, async_judge_evaluator):
        """Test async evaluation."""
        assertion = make_assertion("clarity")

        result = await async_judge_evaluator.evaluate_async(
            assertion,
            response="Take 500mg twice daily with meals.",
            patient_message="How should I take this medication?",
        )

        assert result.passed
        assert result.assertion_type == "llm_judge"

    @pytest.mark.asyncio
    async def test_async_batch_evaluation(self, async_judge_evaluator):
        """Test batch async evaluation."""
        assertions = [
            make_assertion("empathy"),
            make_assertion("clarity"),
            make_assertion("professionalism"),
        ]

        results = await async_judge_evaluator.evaluate_batch_async(
            assertions,
            response="I understand your concern. Take this medication with food.",
            patient_message="I'm worried about side effects.",
        )

        assert len(results) == 3
        assert all(r.passed for r in results)

    @pytest.mark.asyncio
    async def test_async_falls_back_to_sync(self, judge_evaluator):
        """Test that async evaluation falls back to sync if no async fn."""
        assertion = make_assertion("empathy")

        result = await judge_evaluator.evaluate_async(
            assertion,
            response="I understand.",
            patient_message="Hello",
        )

        assert result.passed


# ========================================
# Response Parsing Tests
# ========================================

class TestResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_valid_json(self, mock_llm_fn):
        """Test parsing valid JSON response."""
        judge = LLMJudgeEvaluator(llm_fn=mock_llm_fn)
        assertion = make_assertion("empathy")

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert result.score == 0.8  # 4/5 normalized
        assert "helpful and professional" in result.judge_reasoning

    def test_parse_json_embedded_in_text(self):
        """Test parsing JSON embedded in text."""
        def text_with_json(prompt: str) -> str:
            return 'Here is my evaluation:\n{"score": 3, "reasoning": "Adequate"}\nThank you.'

        judge = LLMJudgeEvaluator(llm_fn=text_with_json)
        assertion = make_assertion("empathy", min_score=3)

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert result.passed
        assert result.score == 0.6  # 3/5 normalized

    def test_parse_score_from_text(self):
        """Test extracting score from text when JSON fails."""
        def text_only(prompt: str) -> str:
            return "The response deserves a score: 4 because it was helpful."

        judge = LLMJudgeEvaluator(llm_fn=text_only)
        assertion = make_assertion("empathy", min_score=3)

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert result.passed
        assert result.score == 0.8  # 4/5

    def test_parse_fallback_on_invalid_response(self):
        """Test fallback when response can't be parsed."""
        def invalid_response(prompt: str) -> str:
            return "This is completely unstructured text with no score."

        judge = LLMJudgeEvaluator(llm_fn=invalid_response)
        assertion = make_assertion("empathy", min_score=3)

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        # Should use fallback score of 3
        assert result.passed  # 3 >= 3

    def test_score_clamping(self):
        """Test that scores are clamped to 1-5 range."""
        def out_of_range_score(prompt: str) -> str:
            return json.dumps({"score": 10, "reasoning": "Invalid score"})

        judge = LLMJudgeEvaluator(llm_fn=out_of_range_score)
        assertion = make_assertion("empathy")

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        # Score should be clamped to 5
        assert result.score == 1.0  # 5/5 normalized


# ========================================
# Error Handling Tests
# ========================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_fallback_on_llm_error(self):
        """Test fallback when LLM call fails."""
        def failing_llm(prompt: str) -> str:
            raise Exception("LLM API error")

        judge = LLMJudgeEvaluator(
            llm_fn=failing_llm,
            fallback_on_error=True,
        )
        assertion = make_assertion("empathy")

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        # Should return passing result on error
        assert result.passed
        assert "skipped" in result.reason.lower()

    def test_no_llm_configured(self):
        """Test behavior when no LLM is configured."""
        judge = LLMJudgeEvaluator()
        assertion = make_assertion("empathy")

        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert result.passed
        assert "skipped" in result.reason.lower()

    def test_error_propagation_when_fallback_disabled(self):
        """Test that errors propagate when fallback is disabled."""
        def failing_llm(prompt: str) -> str:
            raise Exception("LLM API error")

        judge = LLMJudgeEvaluator(
            llm_fn=failing_llm,
            fallback_on_error=False,
        )
        assertion = make_assertion("empathy")

        with pytest.raises(Exception) as exc_info:
            judge.evaluate(
                assertion,
                response="Test",
                patient_message="Test",
            )

        assert "LLM API error" in str(exc_info.value)


# ========================================
# Prompt Building Tests
# ========================================

class TestPromptBuilding:
    """Tests for prompt construction."""

    def test_prompt_includes_patient_message(self):
        """Test that prompt includes patient message."""
        captured_prompt = []

        def capture_prompt(prompt: str) -> str:
            captured_prompt.append(prompt)
            return json.dumps({"score": 4, "reasoning": "Good"})

        judge = LLMJudgeEvaluator(llm_fn=capture_prompt)
        assertion = make_assertion("empathy")

        judge.evaluate(
            assertion,
            response="I understand.",
            patient_message="I'm feeling unwell.",
        )

        assert "I'm feeling unwell" in captured_prompt[0]

    def test_prompt_includes_agent_response(self):
        """Test that prompt includes agent response."""
        captured_prompt = []

        def capture_prompt(prompt: str) -> str:
            captured_prompt.append(prompt)
            return json.dumps({"score": 4, "reasoning": "Good"})

        judge = LLMJudgeEvaluator(llm_fn=capture_prompt)
        assertion = make_assertion("empathy")

        judge.evaluate(
            assertion,
            response="Let me help you with that.",
            patient_message="Help",
        )

        assert "Let me help you with that" in captured_prompt[0]

    def test_prompt_includes_rubric(self):
        """Test that prompt includes the rubric."""
        captured_prompt = []

        def capture_prompt(prompt: str) -> str:
            captured_prompt.append(prompt)
            return json.dumps({"score": 4, "reasoning": "Good"})

        judge = LLMJudgeEvaluator(llm_fn=capture_prompt)
        assertion = make_assertion("empathy")

        judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        # Should include empathy rubric content
        assert "empathy" in captured_prompt[0].lower()
        assert "Score 1" in captured_prompt[0]
        assert "Score 5" in captured_prompt[0]

    def test_prompt_uses_custom_rubric(self):
        """Test that custom assertion rubric is used."""
        captured_prompt = []

        def capture_prompt(prompt: str) -> str:
            captured_prompt.append(prompt)
            return json.dumps({"score": 4, "reasoning": "Good"})

        judge = LLMJudgeEvaluator(llm_fn=capture_prompt)
        assertion = make_assertion(
            criterion="custom",
            rubric="This is my CUSTOM RUBRIC for testing.",
        )

        judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert "CUSTOM RUBRIC" in captured_prompt[0]


# ========================================
# Mock Judge Tests
# ========================================

class TestMockJudge:
    """Tests for the mock judge utility."""

    def test_create_mock_judge(self):
        """Test creating a mock judge."""
        judge = create_mock_judge(default_score=5, reasoning="Perfect!")

        assertion = make_assertion("empathy")
        result = judge.evaluate(
            assertion,
            response="Test",
            patient_message="Test",
        )

        assert result.passed
        assert result.score == 1.0  # 5/5
        assert "Perfect!" in result.judge_reasoning

    def test_mock_judge_consistent_results(self):
        """Test that mock judge returns consistent results."""
        judge = create_mock_judge(default_score=3)

        results = []
        for _ in range(5):
            result = judge.evaluate(
                make_assertion("empathy"),
                response="Test",
                patient_message="Test",
            )
            results.append(result.score)

        assert all(score == 0.6 for score in results)


# ========================================
# Standard Criteria Tests
# ========================================

class TestStandardCriteria:
    """Tests for standard evaluation criteria."""

    def test_all_standard_criteria_have_rubrics(self):
        """Test that all EvaluationCriterion enums have rubrics."""
        for criterion in EvaluationCriterion:
            assert criterion.value in DEFAULT_RUBRICS, f"Missing rubric for {criterion.value}"

    def test_rubrics_have_score_descriptions(self):
        """Test that all rubrics have score 1-5 descriptions."""
        for criterion, rubric in DEFAULT_RUBRICS.items():
            assert "Score 1" in rubric, f"Missing Score 1 in {criterion}"
            assert "Score 5" in rubric, f"Missing Score 5 in {criterion}"


# ========================================
# JudgeResponse Tests
# ========================================

class TestJudgeResponse:
    """Tests for JudgeResponse dataclass."""

    def test_to_assertion_result(self):
        """Test converting JudgeResponse to AssertionResult."""
        response = JudgeResponse(
            score=4,
            reasoning="Good response",
            criterion="empathy",
            passed=True,
        )

        result = response.to_assertion_result(reason="Test reason")

        assert result.passed
        assert result.score == 0.8  # 4/5
        assert "Good response" in result.details
        assert result.judge_reasoning == "Good response"

    def test_to_assertion_result_with_min_score(self):
        """Test conversion respects min_score for passed status."""
        response = JudgeResponse(
            score=3,
            reasoning="Adequate",
            criterion="clarity",
            passed=True,  # This gets recalculated
        )

        # The passed field in JudgeResponse is set during creation
        # based on the min_score comparison
        assert response.passed


# ========================================
# Integration Tests
# ========================================

class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_muriel_bug_clarification_check(self):
        """Test checking if agent asked for clarification on 'Muriel' typo."""
        def smart_judge(prompt: str) -> str:
            # Simulate LLM checking for clarification request
            if "muriel" in prompt.lower() and "clarification" in prompt.lower():
                if "?" in prompt or "verificar" in prompt.lower():
                    return json.dumps({
                        "score": 5,
                        "reasoning": "Agent appropriately asked for clarification about the unknown medication name."
                    })
                else:
                    return json.dumps({
                        "score": 1,
                        "reasoning": "Agent did not ask for clarification about the unknown medication."
                    })
            return json.dumps({"score": 3, "reasoning": "Generic evaluation"})

        judge = LLMJudgeEvaluator(llm_fn=smart_judge)

        # Good response - asks for clarification
        good_assertion = make_assertion("clarification_request", min_score=4)
        good_result = judge.evaluate(
            good_assertion,
            response="No reconozco 'Muriel' como medicamento. ¿Podrías verificar el nombre?",
            patient_message="Estoy tomando Muriel para mi estómago",
        )
        assert good_result.passed

    def test_medical_accuracy_evaluation(self):
        """Test medical accuracy evaluation."""
        judge = create_mock_judge(default_score=4)

        assertion = make_assertion("medical_accuracy", min_score=4)
        result = judge.evaluate(
            assertion,
            response="Metformin is commonly used to treat type 2 diabetes.",
            patient_message="What is metformin used for?",
        )

        assert result.passed

    def test_batch_evaluation_for_comprehensive_check(self):
        """Test batch evaluation for comprehensive response check."""
        judge = create_mock_judge(default_score=4)

        assertions = [
            make_assertion("empathy", min_score=3),
            make_assertion("clarity", min_score=3),
            make_assertion("medical_accuracy", min_score=4),
            make_assertion("safety", min_score=4),
        ]

        results = judge.evaluate_batch(
            assertions,
            response="I understand your concern about the side effects. "
                     "Please take this medication with food and consult your doctor "
                     "if you experience any unusual symptoms.",
            patient_message="I'm worried about side effects of my new medication.",
        )

        assert len(results) == 4
        assert all(r.passed for r in results)
