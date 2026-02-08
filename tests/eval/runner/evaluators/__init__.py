"""
Evaluators for the evaluation framework.

This package provides evaluators for different types of assertions:
- Deterministic: String matching, regex, similarity, etc.
- LLM-as-Judge: LLM-based evaluation for subjective criteria
"""

from .deterministic import (
    # Main evaluator
    DeterministicEvaluator,
    # Base classes
    AssertionEvaluator,
    EvaluatorError,
    InvalidAssertionError,
    # Individual evaluators
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
    # Convenience functions
    create_evaluator,
    evaluate_assertion,
)

from .llm_judge import (
    # Main evaluator
    LLMJudgeEvaluator,
    # Errors
    JudgeError,
    LLMCallError,
    ParseError,
    # Types
    JudgeResponse,
    EvaluationCriterion,
    DEFAULT_RUBRICS,
    # Convenience functions
    create_openai_judge,
    create_anthropic_judge,
    create_mock_judge,
)

__all__ = [
    # Deterministic evaluator
    "DeterministicEvaluator",
    # Deterministic base classes
    "AssertionEvaluator",
    "EvaluatorError",
    "InvalidAssertionError",
    # Deterministic evaluators
    "MustContainEvaluator",
    "MustNotContainEvaluator",
    "MustContainOneOfEvaluator",
    "RegexMatchEvaluator",
    "RegexNotMatchEvaluator",
    "NotEmptyEvaluator",
    "MaxLengthEvaluator",
    "MinLengthEvaluator",
    "SimilarityEvaluator",
    "SemanticSimilarityEvaluator",
    "JsonSchemaEvaluator",
    "IntentMatchEvaluator",
    "StartsWithEvaluator",
    "EndsWithEvaluator",
    "ContainsQuestionEvaluator",
    "WordCountEvaluator",
    # Deterministic functions
    "create_evaluator",
    "evaluate_assertion",
    # LLM Judge evaluator
    "LLMJudgeEvaluator",
    "JudgeError",
    "LLMCallError",
    "ParseError",
    "JudgeResponse",
    "EvaluationCriterion",
    "DEFAULT_RUBRICS",
    # LLM Judge functions
    "create_openai_judge",
    "create_anthropic_judge",
    "create_mock_judge",
]
