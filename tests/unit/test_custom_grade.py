"""The custom policy is reproducible, monotonic and honest about missing coverage."""

import pytest

from ranq.models import Issue, Severity
from ranq.report.scoring import custom_grade


def finding(
    severity: Severity,
    check: str = "example",
    urls: list[str] | None = None,
    site_wide: bool = False,
) -> Issue:
    return Issue(
        check, "Example", severity, "performance", "", "", urls=urls or ["a"], site_wide=site_wide
    )


@pytest.mark.parametrize(
    "severity,expected",
    [
        (Severity.INFO, 100),
        (Severity.LOW, 95),
        (Severity.MEDIUM, 86),
        (Severity.HIGH, 67),
        (Severity.CRITICAL, 37),
    ],
)
def test_documented_weights(severity: Severity, expected: int) -> None:
    assert custom_grade([finding(severity)], 1, True)["score"] == expected


def test_unknown_is_ungraded() -> None:
    assert custom_grade([], 0, True)["score"] is None
    assert custom_grade([], 4, False)["score"] is None
    assert custom_grade([finding(Severity.INFO)], 4, False)["score"] is None
    assert custom_grade([finding(Severity.HIGH)], 4, False)["score"] < 100


def test_duplicates_and_overlapping_performance_count_once() -> None:
    first = finding(Severity.MEDIUM, "lab-cwv-poor")
    before = custom_grade([first], 4, True)
    assert (
        custom_grade([first, first, finding(Severity.MEDIUM, "lab-performance-low")], 4, True)
        == before
    )
    # Hidden headings are unrelated to speed: retain their separate deduction.
    assert (
        custom_grade([first, finding(Severity.MEDIUM, "h1-hidden-in-html")], 4, True)["score"]
        < before["score"]
    )


def test_reach_severity_and_independent_findings_are_monotonic() -> None:
    base = custom_grade([finding(Severity.MEDIUM)], 4, True)["score"]
    assert custom_grade([finding(Severity.MEDIUM, urls=["a", "b"])], 4, True)["score"] < base
    assert custom_grade([finding(Severity.HIGH)], 4, True)["score"] < base
    assert (
        custom_grade([finding(Severity.MEDIUM), finding(Severity.LOW, "other")], 4, True)["score"]
        < base
    )


def test_site_wide_cannot_be_diluted_and_order_does_not_matter() -> None:
    site = finding(Severity.MEDIUM, site_wide=True)
    assert custom_grade([site], 1, True) == custom_grade([site], 100, True)
    extra = finding(Severity.HIGH, urls=["b"])
    assert custom_grade([site, extra], 4, True) == custom_grade([extra, site], 4, True)
    assert custom_grade([site, site], 4, True) == custom_grade([site], 4, True)
