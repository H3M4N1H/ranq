"""Default output stays compact without hiding findings or incomplete coverage."""

from io import StringIO

import pytest
from rich.console import Console

from ranq import cli
from ranq.models import Issue, Severity
from ranq.report.builder import Report
from ranq.report.compare import compare


def sample_report() -> Report:
    return Report(
        site="https://example.test",
        generated_at="today",
        stats={"html_pages": 4},
        issues=[
            Issue(
                "h1-hidden-in-html",
                "Hidden H1 on two pages",
                Severity.MEDIUM,
                "on-page",
                "",
                "",
                urls=["a", "b"],
            ),
            Issue("optional", "Optional crawler policy", Severity.INFO, "geo", "", ""),
        ],
        plan={},
        score=78,
        pages=[{"url": "https://example.test/work", "score": 82, "issues": []}],
        coverage={
            "html_pages": 4,
            "lab_pages": 3,
            "field_pages": 0,
            "rendered_pages": 0,
            "notes": ["Detailed coverage", "Detailed limits", "Crawl stopped at the page limit."],
        },
        domain_scores={"SEO": {"score": 82}, "AEO": {"score": 100}, "GEO": {"score": 95}},
    )


def render_summary(monkeypatch: pytest.MonkeyPatch, report: Report, verbose: bool = False) -> str:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, width=100, color_system=None))
    cli._print_summary(report, verbose=verbose)
    return output.getvalue()


def test_compact_summary_keeps_actionable_findings_and_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = render_summary(monkeypatch, sample_report())
    assert "Audit: Needs attention" in text and "Hidden H1 on two pages" in text
    assert "lab 3/4" in text and "field 0/4" in text and "rendered 0/4" in text
    assert "Crawl stopped at the page limit" in text
    assert "1 informational notes" in text and "no assessment impact" in text
    assert "Optional crawler policy" not in text and "https://example.test/work" not in text
    assert "does not mean verified readiness" in text and "--verbose" in text
    assert "0 critical" not in text and "0 high" not in text


def test_verbose_summary_retains_optional_advice_and_page_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = render_summary(monkeypatch, sample_report(), verbose=True)
    assert "Optional crawler policy" in text
    assert "https://example.test/work" in text and "No issues detected" in text
    assert "Detailed coverage" in text and "Detailed limits" in text
    assert cli.DISCLAIMER.split(".")[0] in text.replace("\n", " ")


def test_compact_model_change_does_not_show_fake_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = sample_report()
    report.comparison = compare(
        {"score": 94, "issues": []}, report.score, report.issues, report.pages
    )
    text = render_summary(monkeypatch, report)
    assert "Since last audit" in text and "/100" not in text
    assert "94 -> 78" not in text and "-16" not in text


def test_info_only_summary_does_not_suggest_actionable_problems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = sample_report()
    report.issues = report.issues[1:]
    assert "No actionable findings" in render_summary(monkeypatch, report)
