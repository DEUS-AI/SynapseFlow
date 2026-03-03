"""Generate a Markdown comparison report from benchmark JSON results.

Reads a benchmark comparison JSON file (produced by benchmark_extraction.py)
and fills the report template with computed scores, gap analysis, and a
final ADOPT / STAY / HYBRID recommendation.

Usage:
    uv run python tests/benchmarks/generate_report.py <results_json>
    uv run python tests/benchmarks/generate_report.py tests/benchmarks/results/20260303_120000_comparison.json
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATE_PATH = Path(__file__).parent / "report_template.md"

ENTITY_TYPES = [
    "Disease", "Treatment", "Symptom", "Test", "Drug",
    "Gene", "Pathway", "Organization", "Study",
]

# Scoring rubric weights (sum = 1.0)
SCORE_WEIGHTS = {
    "entity_recall": 0.20,
    "entity_precision": 0.20,
    "relationship_accuracy": 0.15,
    "source_grounding": 0.15,
    "processing_speed": 0.10,
    "cost_efficiency": 0.10,
    "integration_effort": 0.10,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Score:
    """A single rubric score on the 1-5 scale."""
    name: str
    value: int  # 1-5
    justification: str
    comparison_note: str


@dataclass
class IntegrationGap:
    """A gap identified in the integration assessment."""
    description: str
    severity: str  # low, medium, high
    effort: str    # e.g. "1-2 days", "1 week"
    mitigation: str


# ---------------------------------------------------------------------------
# Scoring rubric  (Task 5.3)
# ---------------------------------------------------------------------------

def compute_entity_recall_score(data: Dict[str, Any]) -> Score:
    """Score LangExtract entity recall relative to MarkItDown."""
    mk_count = data["markitdown_results"]["metrics"]["entity_count"]
    lx_count = data["langextract_results"]["metrics"]["entity_count"]
    overlap_pct = data["overlap_analysis"]["overlap_percentage"]

    if lx_count == 0 and mk_count == 0:
        score, justification = 3, "No entities from either pipeline"
    elif lx_count >= mk_count * 1.2:
        score = 5
        justification = f"LangExtract found {lx_count} entities vs {mk_count} for MarkItDown ({overlap_pct:.0f}% overlap)"
    elif lx_count >= mk_count:
        score = 4
        justification = f"LangExtract matched or exceeded MarkItDown ({lx_count} vs {mk_count})"
    elif lx_count >= mk_count * 0.8:
        score = 3
        justification = f"LangExtract found slightly fewer entities ({lx_count} vs {mk_count})"
    elif lx_count >= mk_count * 0.5:
        score = 2
        justification = f"LangExtract found significantly fewer entities ({lx_count} vs {mk_count})"
    else:
        score = 1
        justification = f"LangExtract found far fewer entities ({lx_count} vs {mk_count})"

    comparison = f"LangExtract: {lx_count}, MarkItDown: {mk_count}"
    return Score("entity_recall", score, justification, comparison)


def compute_entity_precision_score(data: Dict[str, Any]) -> Score:
    """Score entity precision based on type coverage and overlap."""
    lx_types = data["langextract_results"]["metrics"].get("entities_by_type", {})
    mk_types = data["markitdown_results"]["metrics"].get("entities_by_type", {})
    overlap_pct = data["overlap_analysis"]["overlap_percentage"]

    lx_type_count = len(lx_types)
    mk_type_count = len(mk_types)

    if overlap_pct >= 70:
        score = 5
        justification = f"High overlap ({overlap_pct:.0f}%) suggests strong precision"
    elif overlap_pct >= 50:
        score = 4
        justification = f"Moderate overlap ({overlap_pct:.0f}%) with {lx_type_count} entity types"
    elif overlap_pct >= 30:
        score = 3
        justification = f"Some overlap ({overlap_pct:.0f}%) between pipelines"
    elif overlap_pct >= 10:
        score = 2
        justification = f"Low overlap ({overlap_pct:.0f}%) raises precision concerns"
    else:
        score = 1
        justification = f"Very low overlap ({overlap_pct:.0f}%) suggests poor precision"

    comparison = f"Overlap: {overlap_pct:.0f}%, LX types: {lx_type_count}, MK types: {mk_type_count}"
    return Score("entity_precision", score, justification, comparison)


def compute_relationship_accuracy_score(data: Dict[str, Any]) -> Score:
    """Score relationship extraction quality."""
    mk_rels = data["markitdown_results"]["metrics"]["relationship_count"]
    lx_rels = data["langextract_results"]["metrics"]["relationship_count"]

    if lx_rels == 0 and mk_rels == 0:
        score = 3
        justification = "Neither pipeline extracted relationships"
    elif lx_rels > mk_rels:
        score = 4
        justification = f"LangExtract extracted more relationships ({lx_rels} vs {mk_rels})"
    elif lx_rels == mk_rels:
        score = 3
        justification = f"Equal relationship counts ({lx_rels})"
    elif lx_rels >= mk_rels * 0.5:
        score = 2
        justification = f"LangExtract extracted fewer relationships ({lx_rels} vs {mk_rels})"
    else:
        score = 1
        justification = f"LangExtract extracted far fewer relationships ({lx_rels} vs {mk_rels})"

    comparison = f"LangExtract: {lx_rels}, MarkItDown: {mk_rels}"
    return Score("relationship_accuracy", score, justification, comparison)


def compute_source_grounding_score(data: Dict[str, Any]) -> Score:
    """Score source grounding capability."""
    lx_metrics = data["langextract_results"]["metrics"]
    coverage = lx_metrics.get("source_grounding_coverage")

    if coverage is None:
        score = 1
        justification = "No source grounding data available"
    elif coverage >= 0.9:
        score = 5
        justification = f"Excellent grounding coverage ({coverage:.0%})"
    elif coverage >= 0.7:
        score = 4
        justification = f"Good grounding coverage ({coverage:.0%})"
    elif coverage >= 0.4:
        score = 3
        justification = f"Moderate grounding coverage ({coverage:.0%})"
    elif coverage > 0:
        score = 2
        justification = f"Limited grounding coverage ({coverage:.0%})"
    else:
        score = 1
        justification = "No entities have source grounding"

    comparison = f"LangExtract: {coverage:.0%}" if coverage is not None else "MarkItDown: N/A, LangExtract: N/A"
    return Score("source_grounding", score, justification, comparison)


def compute_processing_speed_score(data: Dict[str, Any]) -> Score:
    """Score processing speed comparison."""
    mk_time = data["markitdown_results"]["metrics"]["extraction_time_seconds"]
    lx_time = data["langextract_results"]["metrics"]["extraction_time_seconds"]

    if mk_time == 0 and lx_time == 0:
        score = 3
        justification = "Both pipelines completed instantly"
    elif lx_time <= mk_time * 0.5:
        score = 5
        justification = f"LangExtract 2x+ faster ({lx_time:.1f}s vs {mk_time:.1f}s)"
    elif lx_time <= mk_time:
        score = 4
        justification = f"LangExtract faster ({lx_time:.1f}s vs {mk_time:.1f}s)"
    elif lx_time <= mk_time * 1.5:
        score = 3
        justification = f"Comparable speed ({lx_time:.1f}s vs {mk_time:.1f}s)"
    elif lx_time <= mk_time * 3:
        score = 2
        justification = f"LangExtract slower ({lx_time:.1f}s vs {mk_time:.1f}s)"
    else:
        score = 1
        justification = f"LangExtract much slower ({lx_time:.1f}s vs {mk_time:.1f}s)"

    comparison = f"LangExtract: {lx_time:.1f}s, MarkItDown: {mk_time:.1f}s"
    return Score("processing_speed", score, justification, comparison)


def compute_cost_efficiency_score(data: Dict[str, Any]) -> Score:
    """Score cost efficiency (heuristic based on model and time)."""
    lx_model = data.get("config", {}).get("model_ids", {}).get("langextract", "")
    mk_model = data.get("config", {}).get("model_ids", {}).get("markitdown_llm", "")

    # Simple cost heuristic: Gemini models are generally cheaper than OpenAI
    lx_is_gemini = "gemini" in lx_model.lower()
    mk_is_openai = "gpt" in mk_model.lower() or mk_model.startswith(("o1-", "o3-"))

    if lx_is_gemini and mk_is_openai:
        score = 4
        justification = f"Gemini ({lx_model}) generally cheaper than OpenAI ({mk_model})"
    elif lx_is_gemini:
        score = 4
        justification = f"Gemini model ({lx_model}) is cost-effective"
    elif mk_is_openai:
        score = 3
        justification = "Both using premium models"
    else:
        score = 3
        justification = "Cost comparison depends on actual usage patterns"

    comparison = f"LangExtract: {lx_model}, MarkItDown: {mk_model}"
    return Score("cost_efficiency", score, justification, comparison)


def compute_integration_effort_score(data: Dict[str, Any]) -> Score:
    """Score integration effort into SynapseFlow."""
    # The adapter has already been built, so the effort is relatively low
    lx_available = data.get("config", {}).get("environment", {}).get("langextract_available", False)

    if lx_available:
        score = 4
        justification = "LangExtract adapter already implemented; minimal remaining integration"
    else:
        score = 2
        justification = "LangExtract not installed; requires dependency setup and adapter work"

    comparison = "Adapter exists, optional dependency configured"
    return Score("integration_effort", score, justification, comparison)


def compute_all_scores(data: Dict[str, Any]) -> Dict[str, Score]:
    """Compute all rubric scores from benchmark data."""
    return {
        "entity_recall": compute_entity_recall_score(data),
        "entity_precision": compute_entity_precision_score(data),
        "relationship_accuracy": compute_relationship_accuracy_score(data),
        "source_grounding": compute_source_grounding_score(data),
        "processing_speed": compute_processing_speed_score(data),
        "cost_efficiency": compute_cost_efficiency_score(data),
        "integration_effort": compute_integration_effort_score(data),
    }


def compute_weighted_average(scores: Dict[str, Score]) -> float:
    """Compute weighted average of all scores."""
    total = sum(
        scores[name].value * weight
        for name, weight in SCORE_WEIGHTS.items()
        if name in scores
    )
    return round(total, 2)


# ---------------------------------------------------------------------------
# Integration gap analysis  (Task 5.4)
# ---------------------------------------------------------------------------

def analyze_integration_gaps(data: Dict[str, Any]) -> List[IntegrationGap]:
    """Identify integration gaps between LangExtract and SynapseFlow."""
    gaps: List[IntegrationGap] = []

    # Check relationship extraction
    lx_rels = data["langextract_results"]["metrics"]["relationship_count"]
    mk_rels = data["markitdown_results"]["metrics"]["relationship_count"]
    if lx_rels < mk_rels:
        gaps.append(IntegrationGap(
            description="LangExtract extracts fewer relationships than MarkItDown+LLM pipeline",
            severity="medium",
            effort="1-2 weeks",
            mitigation="Add relationship extraction post-processing or use LLM for relationship inference",
        ))

    if lx_rels == 0 and mk_rels > 0:
        gaps.append(IntegrationGap(
            description="LangExtract does not extract relationships natively",
            severity="high",
            effort="2-3 weeks",
            mitigation="Build a separate relationship extraction step using LLM or rule-based approach",
        ))

    # Check source grounding coverage
    coverage = data["langextract_results"]["metrics"].get("source_grounding_coverage")
    if coverage is not None and coverage < 0.5:
        gaps.append(IntegrationGap(
            description=f"Source grounding coverage is low ({coverage:.0%})",
            severity="medium",
            effort="1 week",
            mitigation="Investigate LangExtract grounding configuration or add post-hoc text matching",
        ))

    # Check entity type coverage
    lx_types = set(data["langextract_results"]["metrics"].get("entities_by_type", {}).keys())
    missing_types = set(ENTITY_TYPES) - lx_types
    if missing_types:
        gaps.append(IntegrationGap(
            description=f"Missing entity types: {', '.join(sorted(missing_types))}",
            severity="low" if len(missing_types) <= 2 else "medium",
            effort="2-3 days",
            mitigation="Add few-shot examples for missing types or adjust extraction prompts",
        ))

    # Check overlap is reasonable
    overlap_pct = data["overlap_analysis"]["overlap_percentage"]
    if overlap_pct < 30:
        gaps.append(IntegrationGap(
            description=f"Low entity overlap ({overlap_pct:.0f}%) suggests different extraction strategies",
            severity="medium",
            effort="1-2 weeks",
            mitigation="Consider ensemble approach combining both pipeline outputs",
        ))

    # DIKW layer integration is handled by the adapter
    # Check if adapter assigns PERCEPTION layer
    lx_entities = data["langextract_results"].get("entities", [])
    has_layer = any(e.get("layer") for e in lx_entities)
    if not has_layer and lx_entities:
        gaps.append(IntegrationGap(
            description="LangExtract entities missing DIKW layer assignment",
            severity="low",
            effort="1 day",
            mitigation="Verify LangExtractIngestionService._assign_dikw_layer() is called",
        ))

    # If no gaps found, add a positive note
    if not gaps:
        gaps.append(IntegrationGap(
            description="No significant integration gaps identified",
            severity="low",
            effort="Minimal",
            mitigation="Proceed with integration as planned",
        ))

    return gaps


# ---------------------------------------------------------------------------
# Recommendation logic  (Task 5.5)
# ---------------------------------------------------------------------------

def compute_recommendation(
    scores: Dict[str, Score],
    weighted_avg: float,
    gaps: List[IntegrationGap],
) -> tuple:
    """Determine recommendation: ADOPT, STAY, or HYBRID.

    Returns:
        Tuple of (recommendation, justification, bullet_points).
    """
    high_severity_gaps = sum(1 for g in gaps if g.severity == "high")
    medium_severity_gaps = sum(1 for g in gaps if g.severity == "medium")

    quality_score = (
        scores["entity_recall"].value * 0.4
        + scores["entity_precision"].value * 0.4
        + scores["relationship_accuracy"].value * 0.2
    )

    points: List[str] = []

    if weighted_avg >= 4.0 and high_severity_gaps == 0:
        recommendation = "ADOPT"
        justification = (
            f"LangExtract scores well across all criteria (weighted avg: {weighted_avg}/5) "
            f"with no high-severity integration gaps."
        )
        points.append(
            f"Strong extraction quality (recall: {scores['entity_recall'].value}/5, "
            f"precision: {scores['entity_precision'].value}/5)"
        )
        points.append("Source grounding provides traceability not available in current pipeline")
        if scores["cost_efficiency"].value >= 4:
            points.append("Cost-effective model choice reduces operational expenses")

    elif weighted_avg >= 3.0 or (quality_score >= 3.5 and high_severity_gaps == 0):
        recommendation = "HYBRID"
        justification = (
            f"LangExtract shows promise (weighted avg: {weighted_avg}/5) but has gaps "
            f"that warrant a hybrid approach combining both pipelines."
        )
        if scores["source_grounding"].value >= 3:
            points.append("Use LangExtract for source grounding and entity extraction")
        points.append("Keep MarkItDown+LLM pipeline for relationship extraction")
        if medium_severity_gaps > 0:
            points.append(
                f"Address {medium_severity_gaps} medium-severity integration gap(s) before full adoption"
            )

    else:
        recommendation = "STAY"
        justification = (
            f"LangExtract does not yet meet the threshold for adoption (weighted avg: {weighted_avg}/5). "
            f"The current MarkItDown+LLM pipeline remains the better choice."
        )
        if high_severity_gaps > 0:
            points.append(
                f"{high_severity_gaps} high-severity gap(s) make integration costly"
            )
        if scores["entity_recall"].value <= 2:
            points.append("Entity recall is insufficient for production use")
        points.append("Re-evaluate when LangExtract improves extraction coverage")

    return recommendation, justification, points


# ---------------------------------------------------------------------------
# Report generation  (Task 5.2)
# ---------------------------------------------------------------------------

def generate_report(data: Dict[str, Any], template: Optional[str] = None) -> str:
    """Generate a filled Markdown report from benchmark JSON data.

    Args:
        data: Parsed benchmark JSON dict.
        template: Optional template string. Uses default template if None.

    Returns:
        Filled Markdown report string.
    """
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Compute scores
    scores = compute_all_scores(data)
    weighted_avg = compute_weighted_average(scores)

    # Integration gaps
    gaps = analyze_integration_gaps(data)

    # Recommendation
    recommendation, rec_justification, rec_points = compute_recommendation(
        scores, weighted_avg, gaps
    )

    # Extract metrics
    mk_metrics = data["markitdown_results"]["metrics"]
    lx_metrics = data["langextract_results"]["metrics"]
    overlap = data["overlap_analysis"]
    metadata = data["metadata"]
    config = data.get("config", {})
    model_ids = config.get("model_ids", {})

    # Build entity type rows
    mk_types = mk_metrics.get("entities_by_type", {})
    lx_types = lx_metrics.get("entities_by_type", {})
    all_types = sorted(set(list(mk_types.keys()) + list(lx_types.keys()) + ENTITY_TYPES))
    entity_type_rows = ""
    for etype in all_types:
        mk_c = mk_types.get(etype, 0)
        lx_c = lx_types.get(etype, 0)
        entity_type_rows += f"| {etype} | {mk_c} | {lx_c} |\n"

    # Source grounding counts
    lx_entities = data["langextract_results"].get("entities", [])
    mk_entities = data["markitdown_results"].get("entities", [])
    lx_grounding_count = sum(1 for e in lx_entities if e.get("source_grounding"))
    mk_grounding_count = sum(1 for e in mk_entities if e.get("source_grounding"))
    lx_grounding_pct = (lx_grounding_count / len(lx_entities) * 100) if lx_entities else 0
    mk_grounding_pct = (mk_grounding_count / len(mk_entities) * 100) if mk_entities else 0

    # Integration gaps table rows
    gaps_rows = ""
    for gap in gaps:
        gaps_rows += f"| {gap.description} | {gap.severity} | {gap.effort} | {gap.mitigation} |\n"

    # Recommendation points
    rec_points_text = ""
    for point in rec_points:
        rec_points_text += f"- {point}\n"

    # Executive summary
    executive_summary = _build_executive_summary(
        mk_metrics, lx_metrics, overlap, scores, weighted_avg, recommendation
    )

    # Fill template using simple string replacement
    report = template
    replacements = {
        "{{ document_name }}": metadata.get("document_name", "Unknown"),
        "{{ run_timestamp }}": metadata.get("run_timestamp", "Unknown"),
        "{{ markitdown_model }}": model_ids.get("markitdown_llm", "Unknown"),
        "{{ langextract_model }}": model_ids.get("langextract", "Unknown"),
        "{{ executive_summary }}": executive_summary,
        # Entity counts
        "{{ mid_entity_count }}": str(mk_metrics["entity_count"]),
        "{{ lx_entity_count }}": str(lx_metrics["entity_count"]),
        "{{ mid_type_count }}": str(len(mk_types)),
        "{{ lx_type_count }}": str(len(lx_types)),
        # Overlap
        "{{ overlap_count }}": str(overlap["overlap_count"]),
        "{{ markitdown_only_count }}": str(overlap["markitdown_only_count"]),
        "{{ langextract_only_count }}": str(overlap["langextract_only_count"]),
        "{{ overlap_percentage }}": f"{overlap['overlap_percentage']:.1f}",
        # Relationships
        "{{ mid_rel_count }}": str(mk_metrics["relationship_count"]),
        "{{ lx_rel_count }}": str(lx_metrics["relationship_count"]),
        "{{ mid_rel_type_count }}": str(len(mk_metrics.get("relationships_by_type", {}))),
        "{{ lx_rel_type_count }}": str(len(lx_metrics.get("relationships_by_type", {}))),
        # Source grounding
        "{{ mid_grounding_count }}": str(mk_grounding_count),
        "{{ lx_grounding_count }}": str(lx_grounding_count),
        "{{ mid_grounding_pct }}": f"{mk_grounding_pct:.0f}",
        "{{ lx_grounding_pct }}": f"{lx_grounding_pct:.0f}",
        # Performance
        "{{ mid_time }}": f"{mk_metrics['extraction_time_seconds']:.2f}",
        "{{ lx_time }}": f"{lx_metrics['extraction_time_seconds']:.2f}",
        "{{ mid_cost }}": "N/A",
        "{{ lx_cost }}": "N/A",
        "{{ mid_tokens }}": "N/A",
        "{{ lx_tokens }}": "N/A",
        # Scores
        "{{ entity_recall_score }}": str(scores["entity_recall"].value),
        "{{ entity_recall_justification }}": scores["entity_recall"].justification,
        "{{ entity_recall_comparison }}": scores["entity_recall"].comparison_note,
        "{{ entity_precision_score }}": str(scores["entity_precision"].value),
        "{{ entity_precision_justification }}": scores["entity_precision"].justification,
        "{{ entity_precision_comparison }}": scores["entity_precision"].comparison_note,
        "{{ relationship_accuracy_score }}": str(scores["relationship_accuracy"].value),
        "{{ relationship_accuracy_justification }}": scores["relationship_accuracy"].justification,
        "{{ relationship_accuracy_comparison }}": scores["relationship_accuracy"].comparison_note,
        "{{ source_grounding_score }}": str(scores["source_grounding"].value),
        "{{ source_grounding_justification }}": scores["source_grounding"].justification,
        "{{ source_grounding_comparison }}": scores["source_grounding"].comparison_note,
        "{{ processing_speed_score }}": str(scores["processing_speed"].value),
        "{{ processing_speed_justification }}": scores["processing_speed"].justification,
        "{{ processing_speed_comparison }}": scores["processing_speed"].comparison_note,
        "{{ cost_efficiency_score }}": str(scores["cost_efficiency"].value),
        "{{ cost_efficiency_justification }}": scores["cost_efficiency"].justification,
        "{{ cost_efficiency_comparison }}": scores["cost_efficiency"].comparison_note,
        "{{ integration_effort_score }}": str(scores["integration_effort"].value),
        "{{ integration_effort_justification }}": scores["integration_effort"].justification,
        "{{ integration_effort_comparison }}": scores["integration_effort"].comparison_note,
        "{{ weighted_average }}": f"{weighted_avg:.2f}",
        # Recommendation
        "{{ recommendation }}": recommendation,
        "{{ recommendation_justification }}": rec_justification,
    }

    for placeholder, value in replacements.items():
        report = report.replace(placeholder, value)

    # Replace loop sections with pre-built rows
    # Entity type rows
    entity_loop_start = "{% for row in entity_type_rows %}\n"
    entity_loop_end = "{% endfor %}\n"
    if entity_loop_start in report:
        loop_start = report.index(entity_loop_start)
        loop_end = report.index(entity_loop_end, loop_start) + len(entity_loop_end)
        report = report[:loop_start] + entity_type_rows + report[loop_end:]

    # Integration gaps rows
    gap_loop_start = "{% for gap in integration_gaps %}\n"
    gap_loop_end = "{% endfor %}\n"
    if gap_loop_start in report:
        loop_start = report.index(gap_loop_start)
        loop_end = report.index(gap_loop_end, loop_start) + len(gap_loop_end)
        report = report[:loop_start] + gaps_rows + report[loop_end:]

    # Recommendation points
    rec_loop_start = "{% for point in recommendation_points %}\n"
    rec_loop_end = "{% endfor %}\n"
    if rec_loop_start in report:
        loop_start = report.index(rec_loop_start)
        loop_end = report.index(rec_loop_end, loop_start) + len(rec_loop_end)
        report = report[:loop_start] + rec_points_text + report[loop_end:]

    return report


def _build_executive_summary(
    mk_metrics: Dict[str, Any],
    lx_metrics: Dict[str, Any],
    overlap: Dict[str, Any],
    scores: Dict[str, Score],
    weighted_avg: float,
    recommendation: str,
) -> str:
    """Build a concise executive summary paragraph."""
    mk_count = mk_metrics["entity_count"]
    lx_count = lx_metrics["entity_count"]
    overlap_pct = overlap["overlap_percentage"]

    lines = [
        f"This report compares two extraction pipelines on the same document. "
        f"MarkItDown+LLM extracted {mk_count} entities; LangExtract extracted {lx_count} entities "
        f"with {overlap_pct:.0f}% entity overlap.",
    ]

    if scores["source_grounding"].value >= 3:
        lines.append(
            "LangExtract provides source grounding metadata for traceability."
        )

    mk_time = mk_metrics["extraction_time_seconds"]
    lx_time = lx_metrics["extraction_time_seconds"]
    if lx_time < mk_time:
        lines.append(f"LangExtract was faster ({lx_time:.1f}s vs {mk_time:.1f}s).")
    elif lx_time > mk_time * 1.5:
        lines.append(f"LangExtract was slower ({lx_time:.1f}s vs {mk_time:.1f}s).")

    lines.append(
        f"Overall weighted score: {weighted_avg:.2f}/5. Recommendation: **{recommendation}**."
    )

    return " ".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI: generate report from a benchmark JSON file."""
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <results_json> [output_md]")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    report = generate_report(data)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = json_path.with_suffix(".md")

    output_path.write_text(report, encoding="utf-8")
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
