"""Simple findings-based assessment. With a separate, explicitly custom numeric grade."""

from typing import Any

from ranq.models import Issue, Severity
from ranq.report.scoring import custom_grade

ASSESSMENT_NOTE = (
    "Assessment reflects detected issues, not a percentage of SEO quality. "
    "No issues detected is not proof of readiness; untested areas remain unknown. "
    "Search rankings and actual AI visibility are not measured by this audit."
)


def domain_for(category: str) -> str:
    if category == "performance":
        return "Performance"
    if category == "geo":
        return "GEO"
    if category in ("aeo", "e-e-a-t"):
        return "AEO"
    return "SEO"


def status(severities: list[str], assessed: bool = True) -> str:
    # Findings take precedence over unavailable data: never hide an observed problem.
    if "critical" in severities:
        return "Critical issues"
    if "high" in severities or "medium" in severities:
        return "Needs attention"
    if "low" in severities:
        return "Minor issues"
    return "No issues detected" if assessed else "Not assessed"


def assess(issues: list[Issue], coverage: dict[str, Any]) -> dict[str, Any]:
    assessed = set(coverage.get("assessed_domains", []))
    domains = {}
    for domain in ("SEO", "AEO", "GEO", "Performance"):
        group = [
            i for i in issues if domain_for(i.category) == domain and i.severity != Severity.INFO
        ]
        domains[domain] = {
            "status": status([i.severity.value for i in group], domain in assessed),
            "grade": custom_grade(group, coverage.get("html_pages", 0), domain in assessed),
            "findings": len(group),
            "affected_urls": sorted({url for i in group for url in i.urls}),
        }
    return {
        "version": "2",
        "grade": custom_grade(issues, coverage.get("html_pages", 0), bool(assessed)),
        "status": status([i.severity.value for i in issues], bool(assessed)),
        "domains": domains,
        "limited": bool(coverage.get("truncated") or coverage.get("disabled_checks")),
        "note": ASSESSMENT_NOTE,
        "rankings": "Not measured",
        "ai_visibility": "Not measured",
    }
