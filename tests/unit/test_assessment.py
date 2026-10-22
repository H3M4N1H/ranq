"""Scenario-based validity checks, not a claim of empirical SEO calibration."""

import pytest

from ranq.analysis.performance import PerfResult
from ranq.checks.base import AuditContext, run_checks
from ranq.checks.performance import core_web_vitals
from ranq.checks.technical import response_time
from ranq.config import Config
from ranq.crawler.crawler import CrawlResult
from ranq.models import Category, Issue, PageData, Severity
from ranq.report.assessment import assess, status
from ranq.report.builder import audit_coverage, build_report
from ranq.report.render import render_html, render_markdown

URL = "https://example.test/"


def context() -> AuditContext:
    p = PageData(URL, URL, 200, content_type="text/html")
    return AuditContext(Config(), CrawlResult(URL, URL, pages={URL: p}))


def issue(severity: Severity, category: str = "on-page") -> Issue:
    return Issue("example", "Example finding", severity, Category(category), "", "", urls=[URL])


@pytest.mark.parametrize(
    "severities,expected",
    [
        ([], "No issues detected"),
        (["info"], "No issues detected"),
        (["low"], "Minor issues"),
        (["medium"], "Needs attention"),
        (["high"], "Needs attention"),
        (["critical"], "Critical issues"),
        (["low"] * 100, "Minor issues"),
        (["medium"] * 100, "Needs attention"),
    ],
)
def test_status_has_no_additive_penalties(severities: list[str], expected: str) -> None:
    assert status(severities) == expected


def test_unknown_is_not_a_pass_and_does_not_hide_observed_problems() -> None:
    assert status([], assessed=False) == "Not assessed"
    assert status(["critical"], assessed=False) == "Critical issues"
    result = assess([], {"assessed_domains": ["SEO"]})
    assert result["domains"]["SEO"]["status"] == "No issues detected"
    assert result["domains"]["AEO"]["status"] == "Not assessed"
    assert result["domains"]["GEO"]["status"] == "Not assessed"
    assert result["ai_visibility"] == result["rankings"] == "Not measured"


def test_overlapping_performance_observations_do_not_compound_grade() -> None:
    one = issue(Severity.MEDIUM, "performance")
    coverage = {"assessed_domains": ["SEO", "Performance"]}
    before = assess([one], coverage)
    after = assess([one, issue(Severity.MEDIUM, "performance")], coverage)
    assert before["status"] == after["status"] == "Needs attention"
    assert after["domains"]["Performance"]["findings"] == 2
    assert after["domains"]["SEO"]["status"] == "No issues detected"


def test_optional_advice_and_limited_scope() -> None:
    result = assess(
        [issue(Severity.INFO, "geo")],
        {"assessed_domains": ["GEO"], "truncated": True, "disabled_checks": ["titles"]},
    )
    assert result["limited"]
    assert result["domains"]["GEO"]["status"] == "No issues detected"
    assert result["domains"]["GEO"]["findings"] == 0


def test_disabled_or_unavailable_analysis_is_not_assessed() -> None:
    from ranq.checks.base import REGISTRY, load_plugins

    ctx = context()
    load_plugins()
    ctx.config.disabled_checks = list(REGISTRY)
    assert run_checks(ctx) == []
    report = build_report(ctx, [])
    assert report.assessment["status"] == "Not assessed"
    assert report.assessment["limited"]
    ctx.config.disabled_checks = []
    run_checks(ctx)
    coverage = audit_coverage(ctx)
    assert "SEO" in coverage["assessed_domains"]
    assert "AEO" not in coverage["assessed_domains"]
    assert "GEO" not in coverage["assessed_domains"]
    assert "Performance" not in coverage["assessed_domains"]


def test_crawl_timing_is_an_observation_not_ttfb_or_a_grade() -> None:
    ctx = context()
    ctx.pages[0].elapsed_ms = 1200
    finding = next(response_time(ctx))
    assert finding.check_id == "slow-response" and finding.severity == Severity.INFO
    assert "not TTFB" in finding.description and "single crawl sample" in finding.title
    assert finding.evidence[URL] == 1200
    ctx.pages[0].elapsed_ms = 500
    assert not list(response_time(ctx))


def test_partial_field_data_preserves_missing_metric_lab_findings() -> None:
    ctx = context()
    ctx.extras["performance"] = [
        PerfResult(
            URL,
            "pagespeed",
            field_data={"LCP": 2000},
            field_categories={"LCP": "good"},
            lab={"LCP": 6000, "CLS": 0.4},
        )
    ]
    finding = next(i for i in core_web_vitals(ctx) if i.check_id == "lab-cwv-poor")
    assert finding.evidence == {URL: {"CLS": 0.4}}
    assert "Lab CLS" in finding.title


def test_lab_tool_order_cannot_hide_poor_measurements() -> None:
    ctx = context()
    poor = PerfResult(URL, "pagespeed", lab={"LCP": 6000})
    good = PerfResult(URL, "lighthouse", lab={"LCP": 2000})
    for results in ([poor, good], [good, poor]):
        ctx.extras["performance"] = results
        finding = next(i for i in core_web_vitals(ctx) if i.check_id == "lab-cwv-poor")
        assert finding.evidence == {URL: {"LCP": 6000}}


def test_reports_present_statuses_and_mark_legacy_score_deprecated() -> None:
    ctx = context()
    run_checks(ctx)
    report = build_report(ctx, [issue(Severity.MEDIUM)])
    for text in (render_html(report), render_markdown(report)):
        assert "Needs attention" in text
        assert "Not assessed" in text
        assert "not a percentage" in text
        assert "Automated audit health" not in text
        assert "Ranq custom grade:" in text
        assert "not an industry standard" in text
    data = report.to_dict()
    assert data["score_deprecated"] is True
    assert "Deprecated" in data["score_note"]
    assert data["assessment"]["status"] == "Needs attention"
