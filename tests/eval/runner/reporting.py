"""
Reporting Module - Generate evaluation reports in various formats.

This module provides report generation for evaluation results:
- HTML reports for human review
- JSON reports for CI/CD integration
- Console output for quick feedback
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AssertionResult, EvalResult, TurnResult

logger = logging.getLogger(__name__)


# ========================================
# Report Data Models
# ========================================

@dataclass
class SuiteReport:
    """Aggregated report for a suite of scenarios."""
    name: str
    timestamp: datetime
    duration_seconds: float
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    total_assertions: int
    passed_assertions: int
    failed_assertions: int
    results: List[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Overall scenario pass rate."""
        if self.total_scenarios == 0:
            return 1.0
        return self.passed_scenarios / self.total_scenarios

    @property
    def assertion_pass_rate(self) -> float:
        """Overall assertion pass rate."""
        if self.total_assertions == 0:
            return 1.0
        return self.passed_assertions / self.total_assertions

    @property
    def all_passed(self) -> bool:
        """Whether all scenarios passed."""
        return self.failed_scenarios == 0

    def get_failed_results(self) -> List[EvalResult]:
        """Get only failed scenario results."""
        return [r for r in self.results if not r.passed]

    def get_results_by_category(self) -> Dict[str, List[EvalResult]]:
        """Group results by category."""
        by_category: Dict[str, List[EvalResult]] = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)
        return by_category

    def get_results_by_severity(self) -> Dict[str, List[EvalResult]]:
        """Group results by severity."""
        by_severity: Dict[str, List[EvalResult]] = {}
        for result in self.results:
            if result.severity not in by_severity:
                by_severity[result.severity] = []
            by_severity[result.severity].append(result)
        return by_severity

    @classmethod
    def from_results(
        cls,
        results: List[EvalResult],
        name: str = "Evaluation Suite",
    ) -> "SuiteReport":
        """Create a SuiteReport from a list of EvalResult."""
        total_assertions = sum(r.total_assertions for r in results)
        failed_assertions = sum(r.failed_assertions_count for r in results)
        total_duration = sum(r.duration_seconds for r in results)

        return cls(
            name=name,
            timestamp=datetime.now(UTC),
            duration_seconds=total_duration,
            total_scenarios=len(results),
            passed_scenarios=sum(1 for r in results if r.passed),
            failed_scenarios=sum(1 for r in results if not r.passed),
            total_assertions=total_assertions,
            passed_assertions=total_assertions - failed_assertions,
            failed_assertions=failed_assertions,
            results=results,
        )


# ========================================
# JSON Reporter
# ========================================

class JSONReporter:
    """Generate JSON reports for CI/CD integration."""

    def generate_report(self, suite: SuiteReport) -> Dict[str, Any]:
        """Generate a JSON-serializable report."""
        return {
            "name": suite.name,
            "timestamp": suite.timestamp.isoformat(),
            "summary": {
                "duration_seconds": round(suite.duration_seconds, 2),
                "total_scenarios": suite.total_scenarios,
                "passed_scenarios": suite.passed_scenarios,
                "failed_scenarios": suite.failed_scenarios,
                "pass_rate": round(suite.pass_rate * 100, 1),
                "total_assertions": suite.total_assertions,
                "passed_assertions": suite.passed_assertions,
                "failed_assertions": suite.failed_assertions,
                "assertion_pass_rate": round(suite.assertion_pass_rate * 100, 1),
                "all_passed": suite.all_passed,
            },
            "by_category": self._group_by_category(suite),
            "by_severity": self._group_by_severity(suite),
            "scenarios": [self._serialize_result(r) for r in suite.results],
        }

    def _group_by_category(self, suite: SuiteReport) -> Dict[str, Dict]:
        """Group and summarize results by category."""
        groups = suite.get_results_by_category()
        return {
            category: {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
            }
            for category, results in groups.items()
        }

    def _group_by_severity(self, suite: SuiteReport) -> Dict[str, Dict]:
        """Group and summarize results by severity."""
        groups = suite.get_results_by_severity()
        return {
            severity: {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
            }
            for severity, results in groups.items()
        }

    def _serialize_result(self, result: EvalResult) -> Dict[str, Any]:
        """Serialize a single EvalResult."""
        return {
            "scenario_id": result.scenario_id,
            "scenario_name": result.scenario_name,
            "category": result.category,
            "severity": result.severity,
            "passed": result.passed,
            "duration_seconds": round(result.duration_seconds, 2),
            "error": result.error,
            "turns": [self._serialize_turn(t) for t in result.turns],
        }

    def _serialize_turn(self, turn: TurnResult) -> Dict[str, Any]:
        """Serialize a single TurnResult."""
        return {
            "turn_number": turn.turn_number,
            "patient_message": turn.patient_message[:100],
            "agent_response": turn.agent_response[:200],
            "passed": turn.passed,
            "response_time_ms": round(turn.response_time_ms, 1),
            "assertions": [self._serialize_assertion(a) for a in turn.all_assertions],
            "failed_assertions": [
                self._serialize_assertion(a) for a in turn.failed_assertions
            ],
        }

    def _serialize_assertion(self, assertion: AssertionResult) -> Dict[str, Any]:
        """Serialize a single AssertionResult."""
        return {
            "type": assertion.assertion_type,
            "passed": assertion.passed,
            "reason": assertion.reason,
            "details": assertion.details,
            "score": assertion.score,
            "severity": assertion.severity.value if assertion.severity else None,
        }

    def save(self, suite: SuiteReport, path: str) -> None:
        """Save report to a JSON file."""
        report = self.generate_report(suite)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON report saved to {path}")


# ========================================
# HTML Reporter
# ========================================

class HTMLReporter:
    """Generate HTML reports for human review."""

    def generate_report(self, suite: SuiteReport) -> str:
        """Generate an HTML report."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{suite.name} - Evaluation Report</title>
    <style>
        {self._get_styles()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{suite.name}</h1>
            <p class="timestamp">Generated: {suite.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
        </header>

        {self._render_summary(suite)}
        {self._render_category_breakdown(suite)}
        {self._render_severity_breakdown(suite)}
        {self._render_failed_scenarios(suite)}
        {self._render_all_scenarios(suite)}

        <footer>
            <p>Generated by SynapseFlow Evaluation Framework</p>
        </footer>
    </div>
</body>
</html>"""

    def _get_styles(self) -> str:
        """Get CSS styles for the report."""
        return """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { text-align: center; margin-bottom: 30px; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        h2 { color: #34495e; margin: 20px 0 15px; padding-bottom: 10px; border-bottom: 2px solid #eee; }
        h3 { color: #7f8c8d; margin: 15px 0 10px; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .summary-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .summary-card.success { border-left: 4px solid #27ae60; }
        .summary-card.danger { border-left: 4px solid #e74c3c; }
        .summary-card.info { border-left: 4px solid #3498db; }
        .summary-card .value { font-size: 2.5em; font-weight: bold; color: #2c3e50; }
        .summary-card .label { color: #7f8c8d; font-size: 0.9em; }
        .progress-bar { height: 10px; background: #ecf0f1; border-radius: 5px; overflow: hidden; margin-top: 10px; }
        .progress-bar .fill { height: 100%; border-radius: 5px; transition: width 0.3s; }
        .progress-bar .fill.success { background: #27ae60; }
        .progress-bar .fill.danger { background: #e74c3c; }
        .section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
        .badge.pass { background: #d4edda; color: #155724; }
        .badge.fail { background: #f8d7da; color: #721c24; }
        .badge.critical { background: #721c24; color: white; }
        .badge.high { background: #e74c3c; color: white; }
        .badge.medium { background: #f39c12; color: white; }
        .badge.low { background: #3498db; color: white; }
        .scenario { border: 1px solid #eee; border-radius: 8px; margin-bottom: 15px; overflow: hidden; }
        .scenario-header { padding: 15px; background: #f8f9fa; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
        .scenario-header:hover { background: #e9ecef; }
        .scenario.failed .scenario-header { background: #fff5f5; }
        .scenario-body { padding: 15px; display: none; border-top: 1px solid #eee; }
        .scenario.expanded .scenario-body { display: block; }
        .turn { padding: 10px; margin: 10px 0; background: #f8f9fa; border-radius: 4px; }
        .turn.failed { background: #fff5f5; border-left: 3px solid #e74c3c; }
        .message { margin: 5px 0; padding: 8px; background: white; border-radius: 4px; }
        .message.patient { border-left: 3px solid #3498db; }
        .message.agent { border-left: 3px solid #27ae60; }
        .assertion { padding: 8px; margin: 5px 0; border-radius: 4px; font-size: 0.9em; }
        .assertion.passed { background: #d4edda; }
        .assertion.failed { background: #f8d7da; }
        .details { color: #666; font-size: 0.85em; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        footer { text-align: center; padding: 20px; color: #7f8c8d; font-size: 0.9em; }
        .toggle-all { cursor: pointer; color: #3498db; font-size: 0.9em; }
        """

    def _render_summary(self, suite: SuiteReport) -> str:
        """Render the summary section."""
        pass_class = "success" if suite.all_passed else "danger"
        pass_rate = suite.pass_rate * 100

        return f"""
        <div class="summary">
            <div class="summary-card {'success' if suite.all_passed else 'danger'}">
                <div class="value">{suite.passed_scenarios}/{suite.total_scenarios}</div>
                <div class="label">Scenarios Passed</div>
                <div class="progress-bar">
                    <div class="fill {pass_class}" style="width: {pass_rate}%"></div>
                </div>
            </div>
            <div class="summary-card info">
                <div class="value">{pass_rate:.1f}%</div>
                <div class="label">Pass Rate</div>
            </div>
            <div class="summary-card info">
                <div class="value">{suite.total_assertions}</div>
                <div class="label">Total Assertions</div>
            </div>
            <div class="summary-card {'success' if suite.failed_assertions == 0 else 'danger'}">
                <div class="value">{suite.failed_assertions}</div>
                <div class="label">Failed Assertions</div>
            </div>
            <div class="summary-card info">
                <div class="value">{suite.duration_seconds:.1f}s</div>
                <div class="label">Total Duration</div>
            </div>
        </div>
        """

    def _render_category_breakdown(self, suite: SuiteReport) -> str:
        """Render breakdown by category."""
        by_category = suite.get_results_by_category()
        if not by_category:
            return ""

        rows = ""
        for category, results in sorted(by_category.items()):
            passed = sum(1 for r in results if r.passed)
            failed = len(results) - passed
            rate = (passed / len(results) * 100) if results else 0
            rows += f"""
            <tr>
                <td>{category}</td>
                <td>{len(results)}</td>
                <td>{passed}</td>
                <td>{failed}</td>
                <td>{rate:.1f}%</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>Results by Category</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Total</th>
                        <th>Passed</th>
                        <th>Failed</th>
                        <th>Pass Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _render_severity_breakdown(self, suite: SuiteReport) -> str:
        """Render breakdown by severity."""
        by_severity = suite.get_results_by_severity()
        if not by_severity:
            return ""

        # Sort by severity order
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_severities = sorted(
            by_severity.items(),
            key=lambda x: severity_order.get(x[0], 99)
        )

        rows = ""
        for severity, results in sorted_severities:
            passed = sum(1 for r in results if r.passed)
            failed = len(results) - passed
            badge_class = severity if severity in ["critical", "high", "medium", "low"] else "info"
            rows += f"""
            <tr>
                <td><span class="badge {badge_class}">{severity.upper()}</span></td>
                <td>{len(results)}</td>
                <td>{passed}</td>
                <td>{failed}</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>Results by Severity</h2>
            <table>
                <thead>
                    <tr>
                        <th>Severity</th>
                        <th>Total</th>
                        <th>Passed</th>
                        <th>Failed</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _render_failed_scenarios(self, suite: SuiteReport) -> str:
        """Render section for failed scenarios."""
        failed = suite.get_failed_results()
        if not failed:
            return """
            <div class="section">
                <h2>Failed Scenarios</h2>
                <p style="color: #27ae60; text-align: center; padding: 20px;">
                    All scenarios passed!
                </p>
            </div>
            """

        scenarios_html = ""
        for result in failed:
            scenarios_html += self._render_scenario(result, expanded=True)

        return f"""
        <div class="section">
            <h2>Failed Scenarios ({len(failed)})</h2>
            {scenarios_html}
        </div>
        """

    def _render_all_scenarios(self, suite: SuiteReport) -> str:
        """Render all scenarios section."""
        scenarios_html = ""
        for result in suite.results:
            scenarios_html += self._render_scenario(result, expanded=False)

        return f"""
        <div class="section">
            <h2>All Scenarios ({len(suite.results)})</h2>
            <p class="toggle-all" onclick="toggleAll()">Expand/Collapse All</p>
            {scenarios_html}
        </div>
        <script>
            document.querySelectorAll('.scenario-header').forEach(header => {{
                header.addEventListener('click', () => {{
                    header.parentElement.classList.toggle('expanded');
                }});
            }});
            function toggleAll() {{
                const scenarios = document.querySelectorAll('.scenario');
                const allExpanded = Array.from(scenarios).every(s => s.classList.contains('expanded'));
                scenarios.forEach(s => {{
                    if (allExpanded) s.classList.remove('expanded');
                    else s.classList.add('expanded');
                }});
            }}
        </script>
        """

    def _render_scenario(self, result: EvalResult, expanded: bool = False) -> str:
        """Render a single scenario."""
        status_badge = '<span class="badge pass">PASS</span>' if result.passed else '<span class="badge fail">FAIL</span>'
        severity_badge = f'<span class="badge {result.severity}">{result.severity.upper()}</span>'
        expanded_class = "expanded" if expanded else ""
        failed_class = "failed" if not result.passed else ""

        turns_html = ""
        for turn in result.turns:
            turns_html += self._render_turn(turn)

        error_html = ""
        if result.error:
            error_html = f'<div class="assertion failed"><strong>Error:</strong> {result.error}</div>'

        return f"""
        <div class="scenario {failed_class} {expanded_class}">
            <div class="scenario-header">
                <div>
                    <strong>{result.scenario_name}</strong>
                    <span style="color: #7f8c8d; margin-left: 10px;">{result.scenario_id}</span>
                </div>
                <div>
                    {severity_badge}
                    {status_badge}
                    <span style="color: #7f8c8d; margin-left: 10px;">{result.duration_seconds:.2f}s</span>
                </div>
            </div>
            <div class="scenario-body">
                <p><strong>Category:</strong> {result.category}</p>
                {error_html}
                {turns_html}
            </div>
        </div>
        """

    def _render_turn(self, turn: TurnResult) -> str:
        """Render a single turn."""
        failed_class = "failed" if not turn.passed else ""

        assertions_html = ""
        for assertion in turn.all_assertions:
            passed_class = "passed" if assertion.passed else "failed"
            score_str = f" (Score: {assertion.score:.2f})" if assertion.score else ""
            assertions_html += f"""
            <div class="assertion {passed_class}">
                <strong>[{assertion.assertion_type}]</strong> {assertion.reason}{score_str}
                <div class="details">{assertion.details}</div>
            </div>
            """

        return f"""
        <div class="turn {failed_class}">
            <h4>Turn {turn.turn_number} ({turn.response_time_ms:.0f}ms)</h4>
            <div class="message patient">
                <strong>Patient:</strong> {turn.patient_message[:200]}{'...' if len(turn.patient_message) > 200 else ''}
            </div>
            <div class="message agent">
                <strong>Agent:</strong> {turn.agent_response[:300]}{'...' if len(turn.agent_response) > 300 else ''}
            </div>
            <h5>Assertions:</h5>
            {assertions_html}
        </div>
        """

    def save(self, suite: SuiteReport, path: str) -> None:
        """Save report to an HTML file."""
        html = self.generate_report(suite)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML report saved to {path}")


# ========================================
# Console Reporter
# ========================================

class ConsoleReporter:
    """Generate console output for quick feedback."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors

    def _color(self, text: str, color: str) -> str:
        """Apply ANSI color codes."""
        if not self.use_colors:
            return text
        colors = {
            "green": "\033[92m",
            "red": "\033[91m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }
        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def print_summary(self, suite: SuiteReport) -> None:
        """Print a summary of the evaluation results."""
        print()
        print(self._color("=" * 60, "bold"))
        print(self._color(f"  {suite.name}", "bold"))
        print(self._color("=" * 60, "bold"))
        print()

        # Overall status
        if suite.all_passed:
            status = self._color("ALL PASSED", "green")
        else:
            status = self._color("SOME FAILED", "red")

        print(f"  Status: {status}")
        print(f"  Duration: {suite.duration_seconds:.2f}s")
        print()

        # Scenarios
        print(f"  Scenarios:")
        print(f"    Total:  {suite.total_scenarios}")
        print(f"    Passed: {self._color(str(suite.passed_scenarios), 'green')}")
        print(f"    Failed: {self._color(str(suite.failed_scenarios), 'red') if suite.failed_scenarios else '0'}")
        print(f"    Rate:   {suite.pass_rate * 100:.1f}%")
        print()

        # Assertions
        print(f"  Assertions:")
        print(f"    Total:  {suite.total_assertions}")
        print(f"    Passed: {self._color(str(suite.passed_assertions), 'green')}")
        print(f"    Failed: {self._color(str(suite.failed_assertions), 'red') if suite.failed_assertions else '0'}")
        print()

        # Failed scenarios
        failed = suite.get_failed_results()
        if failed:
            print(self._color("  Failed Scenarios:", "red"))
            for result in failed:
                print(f"    - [{result.severity}] {result.scenario_id}: {result.scenario_name}")
                for turn in result.turns:
                    for assertion in turn.failed_assertions:
                        print(f"        Turn {turn.turn_number}: [{assertion.assertion_type}] {assertion.reason}")
            print()

        print(self._color("=" * 60, "bold"))
        print()


# ========================================
# Report Manager
# ========================================

class ReportManager:
    """Manage generation of multiple report formats."""

    def __init__(self, output_dir: str = "eval_reports"):
        self.output_dir = Path(output_dir)
        self.json_reporter = JSONReporter()
        self.html_reporter = HTMLReporter()
        self.console_reporter = ConsoleReporter()

    def generate_all(
        self,
        results: List[EvalResult],
        name: str = "Evaluation Report",
        print_console: bool = True,
    ) -> SuiteReport:
        """Generate all report formats."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create suite report
        suite = SuiteReport.from_results(results, name=name)

        # Generate timestamp for filenames
        timestamp = suite.timestamp.strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_path = self.output_dir / f"report_{timestamp}.json"
        self.json_reporter.save(suite, str(json_path))

        # Save HTML report
        html_path = self.output_dir / f"report_{timestamp}.html"
        self.html_reporter.save(suite, str(html_path))

        # Also save as latest
        self.json_reporter.save(suite, str(self.output_dir / "latest.json"))
        self.html_reporter.save(suite, str(self.output_dir / "latest.html"))

        # Print console summary
        if print_console:
            self.console_reporter.print_summary(suite)

        logger.info(f"Reports generated in {self.output_dir}")
        return suite
