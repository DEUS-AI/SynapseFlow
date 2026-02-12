"""
Tests for DeterministicEvaluator and individual evaluators.
"""

import pytest
from typing import List

from tests.eval.runner.evaluators.deterministic import (
    DeterministicEvaluator,
    MustContainEvaluator,
    MustNotContainEvaluator,
    MustContainOneOfEvaluator,
    RegexMatchEvaluator,
    RegexNotMatchEvaluator,
    NotEmptyEvaluator,
    MaxLengthEvaluator,
    MinLengthEvaluator,
    SimilarityEvaluator,
    SemanticSimilarityEvaluator,
    JsonSchemaEvaluator,
    IntentMatchEvaluator,
    StartsWithEvaluator,
    EndsWithEvaluator,
    ContainsQuestionEvaluator,
    WordCountEvaluator,
    create_evaluator,
    evaluate_assertion,
)
from tests.eval.runner.scenario_models import DeterministicAssertion


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def evaluator():
    """Create a DeterministicEvaluator instance."""
    return DeterministicEvaluator()


def make_assertion(
    type: str,
    reason: str = "Test reason",
    **kwargs,
) -> DeterministicAssertion:
    """Helper to create assertions."""
    return DeterministicAssertion(type=type, reason=reason, **kwargs)


# ========================================
# MustContain Tests
# ========================================

class TestMustContainEvaluator:
    """Tests for must_contain assertions."""

    def test_passes_when_all_values_present(self, evaluator):
        assertion = make_assertion(
            type="must_contain",
            values=["hello", "world"],
        )
        result = evaluator.evaluate(assertion, "Hello, World!")

        assert result.passed
        assert result.assertion_type == "must_contain"

    def test_fails_when_value_missing(self, evaluator):
        assertion = make_assertion(
            type="must_contain",
            values=["hello", "missing"],
        )
        result = evaluator.evaluate(assertion, "Hello, World!")

        assert not result.passed
        assert "missing" in result.details.lower()

    def test_case_insensitive(self, evaluator):
        assertion = make_assertion(
            type="must_contain",
            values=["HELLO"],
        )
        result = evaluator.evaluate(assertion, "hello world")

        assert result.passed

    def test_fails_with_no_values(self, evaluator):
        assertion = make_assertion(type="must_contain")
        result = evaluator.evaluate(assertion, "Hello")

        assert not result.passed
        assert "no values" in result.details.lower()

    def test_partial_match(self, evaluator):
        """Values can be substrings."""
        assertion = make_assertion(
            type="must_contain",
            values=["form"],
        )
        result = evaluator.evaluate(assertion, "Metformina 500mg")

        assert result.passed


# ========================================
# MustNotContain Tests
# ========================================

class TestMustNotContainEvaluator:
    """Tests for must_not_contain assertions."""

    def test_passes_when_values_absent(self, evaluator):
        assertion = make_assertion(
            type="must_not_contain",
            values=["error", "invalid"],
        )
        result = evaluator.evaluate(assertion, "Everything is fine!")

        assert result.passed

    def test_fails_when_value_present(self, evaluator):
        assertion = make_assertion(
            type="must_not_contain",
            values=["error"],
        )
        result = evaluator.evaluate(assertion, "There was an error")

        assert not result.passed
        assert "error" in result.details.lower()

    def test_case_insensitive(self, evaluator):
        assertion = make_assertion(
            type="must_not_contain",
            values=["ERROR"],
        )
        result = evaluator.evaluate(assertion, "error occurred")

        assert not result.passed

    def test_muriel_bug_scenario(self, evaluator):
        """The Muriel bug: agent should not confirm typo as medication."""
        assertion = make_assertion(
            type="must_not_contain",
            values=["Muriel está registrada", "He registrado Muriel"],
        )
        # Bad response - confirms the typo
        bad_response = "He registrado Muriel como tu medicación."
        result = evaluator.evaluate(assertion, bad_response)
        assert not result.passed

        # Good response - asks for clarification
        good_response = "No reconozco 'Muriel' como medicamento. ¿Podrías verificar el nombre?"
        result = evaluator.evaluate(assertion, good_response)
        assert result.passed


# ========================================
# MustContainOneOf Tests
# ========================================

class TestMustContainOneOfEvaluator:
    """Tests for must_contain_one_of assertions."""

    def test_passes_when_one_value_present(self, evaluator):
        assertion = make_assertion(
            type="must_contain_one_of",
            values=["apple", "banana", "orange"],
        )
        result = evaluator.evaluate(assertion, "I like bananas")

        assert result.passed

    def test_fails_when_no_values_present(self, evaluator):
        assertion = make_assertion(
            type="must_contain_one_of",
            values=["apple", "banana"],
        )
        result = evaluator.evaluate(assertion, "I like grapes")

        assert not result.passed


# ========================================
# RegexMatch Tests
# ========================================

class TestRegexMatchEvaluator:
    """Tests for regex_match assertions."""

    def test_simple_pattern_match(self, evaluator):
        assertion = make_assertion(
            type="regex_match",
            pattern=r"\d+mg",
        )
        result = evaluator.evaluate(assertion, "Take 500mg daily")

        assert result.passed
        assert "500mg" in result.details

    def test_pattern_not_found(self, evaluator):
        assertion = make_assertion(
            type="regex_match",
            pattern=r"\d+mg",
        )
        result = evaluator.evaluate(assertion, "Take the medication daily")

        assert not result.passed

    def test_complex_pattern(self, evaluator):
        assertion = make_assertion(
            type="regex_match",
            pattern=r"(cada|every)\s+\d+\s+(horas|hours)",
        )
        result = evaluator.evaluate(assertion, "Tomar cada 8 horas")

        assert result.passed

    def test_invalid_regex_fails_gracefully(self, evaluator):
        assertion = make_assertion(
            type="regex_match",
            pattern=r"[invalid(regex",
        )
        result = evaluator.evaluate(assertion, "test")

        assert not result.passed
        assert "invalid regex" in result.details.lower()


# ========================================
# RegexNotMatch Tests
# ========================================

class TestRegexNotMatchEvaluator:
    """Tests for regex_not_match assertions."""

    def test_passes_when_pattern_not_found(self, evaluator):
        assertion = make_assertion(
            type="regex_not_match",
            pattern=r"error|fail|invalid",
        )
        result = evaluator.evaluate(assertion, "Everything is working correctly")

        assert result.passed

    def test_fails_when_pattern_found(self, evaluator):
        assertion = make_assertion(
            type="regex_not_match",
            pattern=r"error|fail",
        )
        result = evaluator.evaluate(assertion, "An error occurred")

        assert not result.passed


# ========================================
# NotEmpty Tests
# ========================================

class TestNotEmptyEvaluator:
    """Tests for not_empty assertions."""

    def test_passes_with_content(self, evaluator):
        assertion = make_assertion(type="not_empty")
        result = evaluator.evaluate(assertion, "Hello!")

        assert result.passed

    def test_fails_with_empty_string(self, evaluator):
        assertion = make_assertion(type="not_empty")
        result = evaluator.evaluate(assertion, "")

        assert not result.passed

    def test_fails_with_whitespace_only(self, evaluator):
        assertion = make_assertion(type="not_empty")
        result = evaluator.evaluate(assertion, "   \n\t  ")

        assert not result.passed


# ========================================
# Length Tests
# ========================================

class TestMaxLengthEvaluator:
    """Tests for max_length assertions."""

    def test_passes_under_limit(self, evaluator):
        assertion = make_assertion(type="max_length", chars=100)
        result = evaluator.evaluate(assertion, "Short response")

        assert result.passed

    def test_fails_over_limit(self, evaluator):
        assertion = make_assertion(type="max_length", chars=10)
        result = evaluator.evaluate(assertion, "This is a very long response")

        assert not result.passed
        assert "28" in result.details  # Actual length
        assert "10" in result.details  # Limit


class TestMinLengthEvaluator:
    """Tests for min_length assertions."""

    def test_passes_over_minimum(self, evaluator):
        assertion = make_assertion(type="min_length", chars=5)
        result = evaluator.evaluate(assertion, "Hello World")

        assert result.passed

    def test_fails_under_minimum(self, evaluator):
        assertion = make_assertion(type="min_length", chars=50)
        result = evaluator.evaluate(assertion, "Short")

        assert not result.passed


# ========================================
# Similarity Tests
# ========================================

class TestSimilarityEvaluator:
    """Tests for similarity assertions."""

    def test_exact_match_passes(self, evaluator):
        assertion = make_assertion(
            type="similarity",
            reference="Hello World",
            threshold=0.9,
        )
        result = evaluator.evaluate(assertion, "Hello World")

        assert result.passed
        assert result.score == 1.0

    def test_similar_text_passes(self, evaluator):
        assertion = make_assertion(
            type="similarity",
            reference="Hello World",
            threshold=0.7,
        )
        result = evaluator.evaluate(assertion, "Hello World!")

        assert result.passed
        assert result.score > 0.7

    def test_different_text_fails(self, evaluator):
        assertion = make_assertion(
            type="similarity",
            reference="Hello World",
            threshold=0.9,
        )
        result = evaluator.evaluate(assertion, "Goodbye Universe")

        assert not result.passed
        assert result.score < 0.5


class TestSemanticSimilarityEvaluator:
    """Tests for semantic_similarity assertions."""

    def test_fallback_to_text_similarity(self, evaluator):
        """Without embedding function, falls back to text similarity."""
        assertion = make_assertion(
            type="semantic_similarity",
            reference="Hello World",
            threshold=0.5,
        )
        result = evaluator.evaluate(assertion, "Hello World!")

        assert result.passed
        assert "fallback" in result.details.lower()

    def test_with_embedding_function(self):
        """Test with a mock embedding function."""
        def mock_embed(text: str) -> List[float]:
            # Simple mock: return same vector for similar texts
            if "hello" in text.lower():
                return [1.0, 0.0, 0.0]
            return [0.0, 1.0, 0.0]

        evaluator = DeterministicEvaluator(embedding_fn=mock_embed)
        assertion = make_assertion(
            type="semantic_similarity",
            reference="Hello World",
            threshold=0.9,
        )
        result = evaluator.evaluate(assertion, "Hello there!")

        assert result.passed
        assert "embedding" in result.details.lower()


# ========================================
# JSON Schema Tests
# ========================================

class TestJsonSchemaEvaluator:
    """Tests for json_schema assertions."""

    def test_valid_json_passes(self, evaluator):
        assertion = make_assertion(type="json_schema")
        result = evaluator.evaluate(assertion, '{"key": "value"}')

        assert result.passed

    def test_invalid_json_fails(self, evaluator):
        assertion = make_assertion(type="json_schema")
        result = evaluator.evaluate(assertion, "not json {broken")

        assert not result.passed
        assert "not valid json" in result.details.lower()

    def test_structure_validation(self, evaluator):
        assertion = make_assertion(
            type="json_schema",
            expected='{"name": "", "age": 0}',
        )
        result = evaluator.evaluate(
            assertion,
            '{"name": "John", "age": 30}',
        )

        assert result.passed


# ========================================
# Intent Match Tests
# ========================================

class TestIntentMatchEvaluator:
    """Tests for intent_match assertions."""

    def test_matching_intent(self, evaluator):
        assertion = make_assertion(
            type="intent_match",
            expected="medication_report",
        )
        context = {"detected_intent": "medication_report"}
        result = evaluator.evaluate(assertion, "response", context)

        assert result.passed

    def test_mismatched_intent(self, evaluator):
        assertion = make_assertion(
            type="intent_match",
            expected="medication_report",
        )
        context = {"detected_intent": "greeting"}
        result = evaluator.evaluate(assertion, "response", context)

        assert not result.passed

    def test_normalized_comparison(self, evaluator):
        """Underscores and dashes should be treated the same."""
        assertion = make_assertion(
            type="intent_match",
            expected="medication-report",
        )
        context = {"detected_intent": "medication_report"}
        result = evaluator.evaluate(assertion, "response", context)

        assert result.passed


# ========================================
# StartsWithWith Tests
# ========================================

class TestStartsWithEvaluator:
    """Tests for starts_with assertions."""

    def test_correct_prefix(self, evaluator):
        assertion = make_assertion(
            type="starts_with",
            expected="Hola",
        )
        result = evaluator.evaluate(assertion, "Hola, ¿cómo estás?")

        assert result.passed

    def test_wrong_prefix(self, evaluator):
        assertion = make_assertion(
            type="starts_with",
            expected="Hello",
        )
        result = evaluator.evaluate(assertion, "Goodbye!")

        assert not result.passed


class TestEndsWithEvaluator:
    """Tests for ends_with assertions."""

    def test_correct_suffix(self, evaluator):
        assertion = make_assertion(
            type="ends_with",
            expected="?",
        )
        result = evaluator.evaluate(assertion, "¿Cómo te sientes hoy?")

        assert result.passed

    def test_wrong_suffix(self, evaluator):
        assertion = make_assertion(
            type="ends_with",
            expected="!",
        )
        result = evaluator.evaluate(assertion, "Hello there.")

        assert not result.passed


# ========================================
# ContainsQuestion Tests
# ========================================

class TestContainsQuestionEvaluator:
    """Tests for contains_question assertions."""

    def test_question_mark_detected(self, evaluator):
        assertion = make_assertion(type="contains_question")
        result = evaluator.evaluate(assertion, "How are you?")

        assert result.passed

    def test_spanish_question_pattern(self, evaluator):
        assertion = make_assertion(type="contains_question")
        result = evaluator.evaluate(assertion, "Podría decirme más sobre eso")

        assert result.passed

    def test_no_question(self, evaluator):
        assertion = make_assertion(type="contains_question")
        result = evaluator.evaluate(assertion, "I understand.")

        assert not result.passed


# ========================================
# WordCount Tests
# ========================================

class TestWordCountEvaluator:
    """Tests for word_count assertions."""

    def test_under_limit(self, evaluator):
        assertion = make_assertion(type="word_count", chars=10)
        result = evaluator.evaluate(assertion, "This is a short response")

        assert result.passed

    def test_over_limit(self, evaluator):
        assertion = make_assertion(type="word_count", chars=3)
        result = evaluator.evaluate(assertion, "This is a longer response with many words")

        assert not result.passed


# ========================================
# DeterministicEvaluator Tests
# ========================================

class TestDeterministicEvaluatorMain:
    """Tests for the main DeterministicEvaluator class."""

    def test_unknown_type_fails(self, evaluator):
        assertion = make_assertion(type="unknown_type")
        result = evaluator.evaluate(assertion, "test")

        assert not result.passed
        assert "unknown" in result.details.lower()

    def test_available_types(self, evaluator):
        types = evaluator.available_types

        assert "must_contain" in types
        assert "must_not_contain" in types
        assert "regex_match" in types
        assert "not_empty" in types
        assert len(types) >= 15

    def test_evaluate_all(self, evaluator):
        assertions = [
            make_assertion(type="not_empty"),
            make_assertion(type="must_contain", values=["hello"]),
            make_assertion(type="max_length", chars=100),
        ]
        results = evaluator.evaluate_all(assertions, "Hello world!")

        assert len(results) == 3
        assert all(r.passed for r in results)

    def test_custom_evaluator_registration(self, evaluator):
        """Test registering a custom evaluator."""
        from tests.eval.runner.evaluators.deterministic import AssertionEvaluator

        class CustomEvaluator(AssertionEvaluator):
            @property
            def assertion_type(self) -> str:
                return "custom_type"

            def evaluate(self, assertion, response, context=None):
                from tests.eval.runner.models import AssertionResult, AssertionSeverity
                return AssertionResult(
                    assertion_type=self.assertion_type,
                    passed=True,
                    reason="Custom check",
                    severity=AssertionSeverity.LOW,
                )

        evaluator.register_evaluator(CustomEvaluator())

        assertion = make_assertion(type="custom_type")
        result = evaluator.evaluate(assertion, "test")

        assert result.passed


# ========================================
# Convenience Functions Tests
# ========================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_evaluator(self):
        evaluator = create_evaluator()
        assert isinstance(evaluator, DeterministicEvaluator)

    def test_create_evaluator_with_embedding(self):
        def mock_embed(text: str) -> List[float]:
            return [1.0, 0.0, 0.0]

        evaluator = create_evaluator(embedding_fn=mock_embed)
        assert isinstance(evaluator, DeterministicEvaluator)

    def test_evaluate_assertion_function(self):
        assertion = make_assertion(type="not_empty")
        result = evaluate_assertion(assertion, "Hello!")

        assert result.passed


# ========================================
# Integration Tests
# ========================================

class TestRealWorldScenarios:
    """Integration tests with real-world scenario patterns."""

    def test_muriel_bug_full_check(self, evaluator):
        """Full test for the Muriel bug scenario."""
        # Bad response that accepts the typo
        bad_response = "He registrado Muriel como tu nuevo medicamento. ¿Hay algo más?"

        assertions = [
            make_assertion(
                type="must_not_contain",
                values=["He registrado Muriel", "Muriel está registrada"],
            ),
            make_assertion(
                type="contains_question",
            ),
        ]

        results = evaluator.evaluate_all(assertions, bad_response)

        # First assertion should fail (bad response confirms Muriel)
        assert not results[0].passed
        # Second assertion should pass (contains question)
        assert results[1].passed

    def test_medication_extraction_validation(self, evaluator):
        """Test for medication extraction scenario."""
        response = "Entendido, has mencionado que tomas Ibuprofeno de 400mg cada 8 horas."

        assertions = [
            make_assertion(type="not_empty"),
            make_assertion(type="must_contain", values=["Ibuprofeno"]),
            make_assertion(type="regex_match", pattern=r"\d+mg"),
            make_assertion(type="regex_match", pattern=r"cada\s+\d+\s+horas"),
        ]

        results = evaluator.evaluate_all(assertions, response)

        assert all(r.passed for r in results)

    def test_gibberish_rejection(self, evaluator):
        """Test for gibberish input rejection."""
        # Good response - rejects gibberish
        good_response = "No reconozco ese medicamento. ¿Podrías verificar el nombre?"

        assertions = [
            make_assertion(
                type="must_not_contain",
                values=["asdfghjk", "registrado asdf"],
            ),
            make_assertion(
                type="contains_question",
            ),
            make_assertion(
                type="regex_match",
                pattern=r"(no\s+reconozco|verificar|repetir)",
            ),
        ]

        results = evaluator.evaluate_all(assertions, good_response)

        assert all(r.passed for r in results)
