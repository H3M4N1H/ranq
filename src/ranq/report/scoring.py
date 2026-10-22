"""Versioned policy for the detected-issue score, not an SEO ranking prediction."""

import math
from typing import Any

from ranq.models import Issue, Severity

SCORING_VERSION = "2"
SCORE_NOTE = (
    "Deprecated legacy penalty score, retained only for JSON/API compatibility. "
    "It is not a validated grade. Use assessment, findings and coverage instead."
)


CUSTOM_GRADE_VERSION = "1"
CUSTOM_GRADE_NOTE = (
    "Ranq custom grade: a heuristic of detected audit issues, not an industry standard "
    "or a measurement of rankings or AI visibility. 100 means no scored findings within "
    "the checks run; unmeasured areas are not verified."
)


def custom_grade(issues: list[Issue], page_count: int, assessed: bool) -> dict[str, Any]:
    """Deduplicate checks and overlapping speed measurements before applying penalties."""
    groups: dict[str, dict[str, float]] = {}
    for issue in issues:
        if issue.severity == Severity.INFO:
            continue
        # These are overlapping observations of performance, not independent defects.
        family = (
            "web-performance"
            if issue.check_id.startswith("cwv-")
            or issue.check_id in ("lab-cwv-poor", "lab-performance-low")
            else issue.check_id
        )
        group = groups.setdefault(family, {})
        affected = ["*"] if issue.site_wide or not issue.urls else set(issue.urls)
        for url in affected:
            group[url] = max(group.get(url, 0), issue.severity.weight)
    rows: list[dict[str, Any]] = []
    for family, targets in sorted(groups.items()):
        site_weight = targets.get("*", 0)
        weights = [max(site_weight, w) for url, w in targets.items() if url != "*"]
        peak = max(targets.values())
        # Baseline for a detected defect + reach across audited pages. Duplicate URL
        # observations contribute only their maximum weight, including mixed severities.
        mean = min(peak, site_weight + sum(w - site_weight for w in weights) / max(page_count, 1))
        penalty = 0.3 * peak + 0.7 * mean
        rows.append({"family": family, "penalty": round(penalty, 6)})
    score = (
        round(100 * math.exp(-sum(r["penalty"] for r in rows) / 100))
        if page_count and (assessed or groups)
        else None
    )
    return {
        "version": CUSTOM_GRADE_VERSION,
        "score": score,
        "breakdown": rows,
        "note": CUSTOM_GRADE_NOTE,
    }
