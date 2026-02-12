"""
Deterministic Evaluator - Evaluates deterministic assertions on agent responses.

This module provides evaluation logic for assertions that can be evaluated
without LLM inference, using string matching, regex, similarity metrics, etc.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from ..models import AssertionResult, AssertionSeverity
from ..scenario_models import DeterministicAssertion

logger = logging.getLogger(__name__)


class EvaluatorError(Exception):
    """Base error for evaluator failures."""
    pass


class InvalidAssertionError(EvaluatorError):
    """Error when an assertion is malformed or has invalid parameters."""
    pass


# ========================================
# Base Evaluator Protocol
# ========================================

class AssertionEvaluator(ABC):
    """Base class for assertion evaluators."""

    @property
    @abstractmethod
    def assertion_type(self) -> str:
        """The assertion type this evaluator handles."""
        pass

    @abstractmethod
    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        """
        Evaluate an assertion against a response.

        Args:
            assertion: The assertion to evaluate
            response: The agent's response text
            context: Optional context (patient_message, etc.)

        Returns:
            AssertionResult with pass/fail status and details
        """
        pass


# ========================================
# String Matching Evaluators
# ========================================

class MustContainEvaluator(AssertionEvaluator):
    """Evaluator for must_contain assertions."""

    @property
    def assertion_type(self) -> str:
        return "must_contain"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.values:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No values specified for must_contain assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        response_lower = response.lower()
        missing = [v for v in assertion.values if v.lower() not in response_lower]

        passed = len(missing) == 0
        details = ""
        if not passed:
            details = f"Missing required values: {missing}"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )


class MustNotContainEvaluator(AssertionEvaluator):
    """Evaluator for must_not_contain assertions."""

    @property
    def assertion_type(self) -> str:
        return "must_not_contain"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.values:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No values specified for must_not_contain assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        response_lower = response.lower()
        found = [v for v in assertion.values if v.lower() in response_lower]

        passed = len(found) == 0
        details = ""
        if not passed:
            details = f"Found forbidden values: {found}"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.HIGH,  # Finding forbidden content is more serious
        )


class MustContainOneOfEvaluator(AssertionEvaluator):
    """Evaluator for must_contain_one_of assertions (at least one value must be present)."""

    @property
    def assertion_type(self) -> str:
        return "must_contain_one_of"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.values:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No values specified for must_contain_one_of assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        response_lower = response.lower()
        found = [v for v in assertion.values if v.lower() in response_lower]

        passed = len(found) > 0
        details = ""
        if not passed:
            details = f"None of the expected values found. Expected one of: {assertion.values}"
        else:
            details = f"Found: {found}"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )


# ========================================
# Pattern Matching Evaluators
# ========================================

class RegexMatchEvaluator(AssertionEvaluator):
    """Evaluator for regex_match assertions."""

    @property
    def assertion_type(self) -> str:
        return "regex_match"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.pattern:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No pattern specified for regex_match assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        try:
            match = re.search(assertion.pattern, response, re.IGNORECASE | re.MULTILINE)
            passed = match is not None

            details = ""
            if passed:
                details = f"Pattern matched: '{match.group()}'"
            else:
                details = f"Pattern not found: {assertion.pattern}"

            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=passed,
                reason=assertion.reason,
                details=details,
                severity=AssertionSeverity.MEDIUM,
            )

        except re.error as e:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details=f"Invalid regex pattern: {e}",
                severity=AssertionSeverity.HIGH,
            )


class RegexNotMatchEvaluator(AssertionEvaluator):
    """Evaluator for regex_not_match assertions (pattern should NOT be found)."""

    @property
    def assertion_type(self) -> str:
        return "regex_not_match"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.pattern:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No pattern specified for regex_not_match assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        try:
            match = re.search(assertion.pattern, response, re.IGNORECASE | re.MULTILINE)
            passed = match is None

            details = ""
            if not passed:
                details = f"Forbidden pattern found: '{match.group()}'"

            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=passed,
                reason=assertion.reason,
                details=details,
                severity=AssertionSeverity.HIGH,
            )

        except re.error as e:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details=f"Invalid regex pattern: {e}",
                severity=AssertionSeverity.HIGH,
            )


# ========================================
# Length Evaluators
# ========================================

class NotEmptyEvaluator(AssertionEvaluator):
    """Evaluator for not_empty assertions."""

    @property
    def assertion_type(self) -> str:
        return "not_empty"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        passed = bool(response.strip())

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details="" if passed else "Response is empty or contains only whitespace",
            severity=AssertionSeverity.HIGH,
        )


class MaxLengthEvaluator(AssertionEvaluator):
    """Evaluator for max_length assertions."""

    @property
    def assertion_type(self) -> str:
        return "max_length"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if assertion.chars is None:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No chars limit specified for max_length assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        actual_length = len(response)
        passed = actual_length <= assertion.chars

        details = ""
        if not passed:
            details = f"Response too long: {actual_length} chars (max: {assertion.chars})"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.LOW,
        )


class MinLengthEvaluator(AssertionEvaluator):
    """Evaluator for min_length assertions."""

    @property
    def assertion_type(self) -> str:
        return "min_length"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if assertion.chars is None:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No chars limit specified for min_length assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        actual_length = len(response)
        passed = actual_length >= assertion.chars

        details = ""
        if not passed:
            details = f"Response too short: {actual_length} chars (min: {assertion.chars})"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.LOW,
        )


# ========================================
# Similarity Evaluators
# ========================================

class SimilarityEvaluator(AssertionEvaluator):
    """Evaluator for similarity assertions using SequenceMatcher."""

    @property
    def assertion_type(self) -> str:
        return "similarity"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.reference:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No reference text specified for similarity assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        threshold = assertion.threshold if assertion.threshold is not None else 0.7

        # Calculate similarity using SequenceMatcher (basic but no external deps)
        similarity = SequenceMatcher(
            None,
            response.lower(),
            assertion.reference.lower(),
        ).ratio()

        passed = similarity >= threshold

        details = f"Similarity: {similarity:.2%} (threshold: {threshold:.0%})"
        if not passed:
            details += f" - Below threshold"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            score=similarity,
            severity=AssertionSeverity.MEDIUM,
        )


class SemanticSimilarityEvaluator(AssertionEvaluator):
    """
    Evaluator for semantic_similarity assertions using embeddings.

    Requires an embedding function to be provided during initialization.
    Falls back to text similarity if no embedding function is available.
    """

    def __init__(self, embedding_fn: Optional[Callable[[str], List[float]]] = None):
        """
        Initialize with optional embedding function.

        Args:
            embedding_fn: Function that takes text and returns embedding vector
        """
        self._embedding_fn = embedding_fn

    @property
    def assertion_type(self) -> str:
        return "semantic_similarity"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.reference:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No reference text specified for semantic_similarity assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        threshold = assertion.threshold if assertion.threshold is not None else 0.8

        if self._embedding_fn is None:
            # Fallback to text similarity
            similarity = SequenceMatcher(
                None,
                response.lower(),
                assertion.reference.lower(),
            ).ratio()
            method = "text (fallback)"
        else:
            try:
                # Compute embeddings and cosine similarity
                response_emb = self._embedding_fn(response)
                reference_emb = self._embedding_fn(assertion.reference)
                similarity = self._cosine_similarity(response_emb, reference_emb)
                method = "embedding"
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to text similarity: {e}")
                similarity = SequenceMatcher(
                    None,
                    response.lower(),
                    assertion.reference.lower(),
                ).ratio()
                method = "text (fallback)"

        passed = similarity >= threshold

        details = f"Semantic similarity ({method}): {similarity:.2%} (threshold: {threshold:.0%})"
        if not passed:
            details += f" - Below threshold"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            score=similarity,
            severity=AssertionSeverity.MEDIUM,
        )

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# ========================================
# Format Evaluators
# ========================================

class JsonSchemaEvaluator(AssertionEvaluator):
    """Evaluator for json_schema assertions (validates JSON structure)."""

    @property
    def assertion_type(self) -> str:
        return "json_schema"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        # Try to parse response as JSON
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as e:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details=f"Response is not valid JSON: {e}",
                severity=AssertionSeverity.HIGH,
            )

        # If expected value is provided, validate structure
        if assertion.expected:
            try:
                expected_structure = json.loads(assertion.expected)
                passed = self._validate_structure(parsed, expected_structure)
                details = "JSON structure matches" if passed else "JSON structure mismatch"
            except json.JSONDecodeError:
                # Expected is not JSON, just check that response is valid JSON
                passed = True
                details = "Response is valid JSON"
        else:
            passed = True
            details = "Response is valid JSON"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )

    def _validate_structure(self, actual: Any, expected: Any) -> bool:
        """Recursively validate JSON structure matches expected."""
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            for key in expected:
                if key not in actual:
                    return False
                if not self._validate_structure(actual[key], expected[key]):
                    return False
            return True
        elif isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            if len(expected) > 0 and len(actual) > 0:
                # Check that all items match the first expected item's structure
                return all(self._validate_structure(item, expected[0]) for item in actual)
            return True
        else:
            # For primitives, just check type matches
            return type(actual) == type(expected)


class IntentMatchEvaluator(AssertionEvaluator):
    """Evaluator for intent_match assertions (validates detected intent)."""

    @property
    def assertion_type(self) -> str:
        return "intent_match"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.expected:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No expected intent specified for intent_match assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        # Get detected intent from context (set by orchestrator from chat response)
        detected_intent = context.get("detected_intent", "") if context else ""

        # Compare intents (case-insensitive, underscore/dash normalized)
        expected_normalized = assertion.expected.lower().replace("-", "_")
        detected_normalized = detected_intent.lower().replace("-", "_")

        passed = expected_normalized == detected_normalized

        details = ""
        if passed:
            details = f"Intent matched: {detected_intent}"
        else:
            details = f"Intent mismatch: expected '{assertion.expected}', got '{detected_intent or 'none'}'"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )


class StartsWithEvaluator(AssertionEvaluator):
    """Evaluator for starts_with assertions."""

    @property
    def assertion_type(self) -> str:
        return "starts_with"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.expected:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No expected prefix specified for starts_with assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        passed = response.lower().startswith(assertion.expected.lower())

        details = ""
        if not passed:
            preview = response[:50] + "..." if len(response) > 50 else response
            details = f"Response does not start with '{assertion.expected}'. Starts with: '{preview}'"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.LOW,
        )


class EndsWithEvaluator(AssertionEvaluator):
    """Evaluator for ends_with assertions."""

    @property
    def assertion_type(self) -> str:
        return "ends_with"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if not assertion.expected:
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No expected suffix specified for ends_with assertion",
                severity=AssertionSeverity.MEDIUM,
            )

        passed = response.lower().rstrip().endswith(assertion.expected.lower())

        details = ""
        if not passed:
            preview = "..." + response[-50:] if len(response) > 50 else response
            details = f"Response does not end with '{assertion.expected}'. Ends with: '{preview}'"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.LOW,
        )


class ContainsQuestionEvaluator(AssertionEvaluator):
    """Evaluator that checks if response contains a question (ends with ?)."""

    @property
    def assertion_type(self) -> str:
        return "contains_question"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        # Check for question marks in the response
        contains_question = "?" in response

        # Also check for common question patterns in Spanish
        question_patterns = [
            r"\b(qué|cómo|cuándo|dónde|por qué|cuál|quién)\b",
            r"\bpodría\s+(decirme|indicarme|explicarme)\b",
            r"\bes\s+correcto\b",
        ]

        has_question_pattern = any(
            re.search(pattern, response, re.IGNORECASE)
            for pattern in question_patterns
        )

        passed = contains_question or has_question_pattern

        details = ""
        if passed:
            details = "Response contains a question"
        else:
            details = "Response does not contain a question"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.MEDIUM,
        )


class WordCountEvaluator(AssertionEvaluator):
    """Evaluator for word count constraints."""

    @property
    def assertion_type(self) -> str:
        return "word_count"

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        if assertion.chars is None:  # Reusing chars field for word count
            return AssertionResult(
                assertion_type=self.assertion_type,
                passed=False,
                reason=assertion.reason,
                details="No word count limit specified",
                severity=AssertionSeverity.MEDIUM,
            )

        word_count = len(response.split())

        # Determine if this is min or max based on the type subfield (if any)
        # For now, treat as max word count
        passed = word_count <= assertion.chars

        details = f"Word count: {word_count} (limit: {assertion.chars})"
        if not passed:
            details += " - Exceeds limit"

        return AssertionResult(
            assertion_type=self.assertion_type,
            passed=passed,
            reason=assertion.reason,
            details=details,
            severity=AssertionSeverity.LOW,
        )


# ========================================
# Main Evaluator Registry
# ========================================

class DeterministicEvaluator:
    """
    Main deterministic evaluator that dispatches to specific evaluators.

    Usage:
        evaluator = DeterministicEvaluator()
        result = evaluator.evaluate(assertion, response)
    """

    def __init__(
        self,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        """
        Initialize the evaluator with optional embedding function.

        Args:
            embedding_fn: Optional function for semantic similarity
        """
        self._evaluators: Dict[str, AssertionEvaluator] = {}
        self._register_default_evaluators(embedding_fn)

    def _register_default_evaluators(
        self,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ) -> None:
        """Register all default evaluators."""
        evaluators = [
            MustContainEvaluator(),
            MustNotContainEvaluator(),
            MustContainOneOfEvaluator(),
            RegexMatchEvaluator(),
            RegexNotMatchEvaluator(),
            NotEmptyEvaluator(),
            MaxLengthEvaluator(),
            MinLengthEvaluator(),
            SimilarityEvaluator(),
            SemanticSimilarityEvaluator(embedding_fn),
            JsonSchemaEvaluator(),
            IntentMatchEvaluator(),
            StartsWithEvaluator(),
            EndsWithEvaluator(),
            ContainsQuestionEvaluator(),
            WordCountEvaluator(),
        ]

        for evaluator in evaluators:
            self.register_evaluator(evaluator)

    def register_evaluator(self, evaluator: AssertionEvaluator) -> None:
        """
        Register a custom evaluator.

        Args:
            evaluator: The evaluator to register
        """
        self._evaluators[evaluator.assertion_type] = evaluator
        logger.debug(f"Registered evaluator: {evaluator.assertion_type}")

    def evaluate(
        self,
        assertion: DeterministicAssertion,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AssertionResult:
        """
        Evaluate an assertion against a response.

        Args:
            assertion: The assertion to evaluate
            response: The agent's response text
            context: Optional context (patient_message, detected_intent, etc.)

        Returns:
            AssertionResult with pass/fail status and details
        """
        assertion_type = assertion.type.lower()

        if assertion_type not in self._evaluators:
            logger.warning(f"Unknown assertion type: {assertion_type}")
            return AssertionResult(
                assertion_type=assertion_type,
                passed=False,
                reason=assertion.reason,
                details=f"Unknown assertion type: {assertion_type}. "
                        f"Available types: {list(self._evaluators.keys())}",
                severity=AssertionSeverity.MEDIUM,
            )

        try:
            return self._evaluators[assertion_type].evaluate(assertion, response, context)
        except Exception as e:
            logger.error(f"Evaluator error for {assertion_type}: {e}")
            return AssertionResult(
                assertion_type=assertion_type,
                passed=False,
                reason=assertion.reason,
                details=f"Evaluator error: {e}",
                severity=AssertionSeverity.HIGH,
            )

    def evaluate_all(
        self,
        assertions: List[DeterministicAssertion],
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[AssertionResult]:
        """
        Evaluate multiple assertions against a response.

        Args:
            assertions: List of assertions to evaluate
            response: The agent's response text
            context: Optional context

        Returns:
            List of AssertionResult for each assertion
        """
        return [
            self.evaluate(assertion, response, context)
            for assertion in assertions
        ]

    @property
    def available_types(self) -> List[str]:
        """Return list of available assertion types."""
        return list(self._evaluators.keys())


# ========================================
# Convenience Functions
# ========================================

def create_evaluator(
    embedding_fn: Optional[Callable[[str], List[float]]] = None,
) -> DeterministicEvaluator:
    """
    Create a DeterministicEvaluator with optional embedding support.

    Args:
        embedding_fn: Optional embedding function for semantic similarity

    Returns:
        Configured DeterministicEvaluator
    """
    return DeterministicEvaluator(embedding_fn=embedding_fn)


def evaluate_assertion(
    assertion: DeterministicAssertion,
    response: str,
    context: Optional[Dict[str, Any]] = None,
) -> AssertionResult:
    """
    Convenience function to evaluate a single assertion.

    Args:
        assertion: The assertion to evaluate
        response: The agent's response text
        context: Optional context

    Returns:
        AssertionResult
    """
    evaluator = DeterministicEvaluator()
    return evaluator.evaluate(assertion, response, context)
