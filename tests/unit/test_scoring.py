"""Calibration scenarios are synthetic and independent of any customer domain."""

import pytest

from ranq.analysis.performance import PerfResult
from ranq.checks.base import AuditContext
from ranq.config import Config
from ranq.crawler.crawler import CrawlResult
from ranq.models import Issue, PageData, Severity
from ranq.report.builder import audit_coverage, health_score, page_scores
from ranq.report.compare import compare
from ranq.report.scoring import SCORING_VERSION


def finding(severity: Severity, n: int = 1, cid: str = "example") -> Issue:
    return Issue(
        cid, cid, severity, "on-page", "", "", urls=[f"https://example.test/{i}" for i in range(n)]
    )


@pytest.mark.parametrize(
    "severity,lower,upper",
    [
        (Severity.INFO, 100, 100),
        (Severity.LOW, 90, 99),
        (Severity.MEDIUM, 80, 89),
        (Severity.HIGH, 50, 69),
        (Severity.CRITICAL, 1, 49),
    ],
)
def test_single_full_reach_issue_calibration(severity: Severity, lower: int, upper: int) -> None:
    assert lower <= health_score([finding(severity)], 1) <= upper


def test_clean_and_optional_only_sites_remain_clean() -> None:
    assert health_score([], 1) == 100
    assert health_score([finding(Severity.INFO, cid=f"optional-{i}") for i in range(30)], 1) == 100
    assert health_score([], 0) == 0


def test_small_site_with_multiple_problems_is_not_nearly_perfect() -> None:
    issues = [finding(Severity.MEDIUM, cid=f"medium-{i}") for i in range(2)]
    issues += [finding(Severity.LOW, cid=f"low-{i}") for i in range(5)]
    assert 50 <= health_score(issues, 1) < 70
    # Fixing actual issues improves scores; changing the domain cannot change them.
    assert health_score(issues[1:], 1) > health_score(issues, 1)
    for issue in issues:
        issue.urls = ["https://another.test/"]
    assert 50 <= health_score(issues, 1) < 70


def test_multiple_page_reach_and_duplicate_urls() -> None:
    issues = [
        finding(Severity.MEDIUM, 2, "hidden-heading"),
        finding(Severity.MEDIUM, 1, "slow-page"),
    ]
    assert 70 <= health_score(issues, 4) < 90
    issue = finding(Severity.MEDIUM)
    before = health_score([issue], 4)
    issue.urls *= 10
    assert health_score([issue], 4) == before
    assert health_score([finding(Severity.MEDIUM, 4)], 4) < before
    assert health_score([finding(Severity.MEDIUM, 4)], 4) == health_score(
        [finding(Severity.MEDIUM)], 1
    )


def test_extreme_scores_are_bounded_and_page_formula_matches() -> None:
    issues = [finding(Severity.CRITICAL, cid=str(i)) for i in range(100)]
    assert health_score(issues, 1) == 1
    issue = finding(Severity.MEDIUM)
    assert page_scores([issue], issue.urls)[0]["score"] == health_score([issue], 1)


def test_scoring_version_change_does_not_claim_regression() -> None:
    for version in (None, "1", "future"):
        previous = {
            "score": 98,
            "issues": [],
            "scoring_version": version,
            "page_scores": [{"url": "https://example.test/0", "score": 98}],
        }
        result = compare(previous, 86, [], [{"url": "https://example.test/0", "score": 86}])
        assert result.delta is None and not result.scores_comparable
        assert result.pages == []
    assert (
        compare({"score": 86, "issues": [], "scoring_version": SCORING_VERSION}, 90, [], []).delta
        == 4
    )


def test_coverage_reports_unknowns_and_unique_measured_pages() -> None:
    url = "https://example.test/"
    page = PageData(url, url, 200, content_type="text/html")
    ctx = AuditContext(Config(), CrawlResult(url, url, pages={url: page}))
    missing = audit_coverage(ctx)
    assert missing["lab_pages"] == missing["field_pages"] == missing["rendered_pages"] == 0
    ctx.extras["performance"] = [PerfResult(url, "pagespeed", error="quota exceeded")]
    assert audit_coverage(ctx)["lab_pages"] == 0
    assert any("failed" in n for n in audit_coverage(ctx)["notes"])
    ctx.extras["performance"] = [
        PerfResult(url, "pagespeed", lab={"LCP": 6000}),
        PerfResult(url, "lighthouse", lab={"LCP": 6100}),
    ]
    ctx.crawl.truncated = True
    ctx.config.disabled_checks = ["titles"]
    measured = audit_coverage(ctx)
    assert measured["lab_pages"] == 1 and measured["field_pages"] == 0
    assert measured["truncated"] and measured["disabled_checks"] == ["titles"]


def test_coverage_change_does_not_claim_site_improvement() -> None:
    coverage = {"audited_urls": ["https://example.test/"], "lab_urls": []}
    previous = {
        "score": 86,
        "issues": [],
        "scoring_version": SCORING_VERSION,
        "coverage": {**coverage, "lab_urls": ["https://example.test/"]},
    }
    result = compare(previous, 100, [], [], coverage)
    assert result.delta is None
    assert "coverage changed" in result.comparison_note


def test_legacy_comparison_renders_without_false_delta() -> None:
    from ranq.report.builder import Report
    from ranq.report.render import render_html, render_markdown

    report = Report("https://example.test", "today", {}, [], {}, 86)
    report.comparison = compare({"score": 98, "issues": []}, 86, [], [])
    for rendered in (render_html(report), render_markdown(report)):
        assert "website changes" in rendered
        assert "-12" not in rendered


def test_domain_scores_explain_separate_findings_without_optional_penalties() -> None:
    from ranq.report.builder import domain_scores, score_breakdown

    seo = finding(Severity.MEDIUM)
    aeo = finding(Severity.LOW, cid="aeo-example")
    aeo.category = "aeo"
    geo = finding(Severity.INFO, cid="optional-geo")
    geo.category = "geo"
    scores = domain_scores([seo, aeo, geo], 1)
    assert scores["SEO"]["score"] < scores["AEO"]["score"] < scores["GEO"]["score"] == 100
    assert scores["GEO"]["scored_findings"] == 0
    assert sum(row["penalty"] for row in score_breakdown([seo, aeo, geo], 1)) == 20
