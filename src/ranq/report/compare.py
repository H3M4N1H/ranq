"""Compare an audit with a previous one: score change, fixed / new / changed issues and per-page
score changes. Works with any earlier report.json (older ones without page scores too)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ranq.models import Issue
from ranq.report.scoring import SCORING_VERSION
from ranq.urls import same_site


@dataclass(slots=True)
class IssueChange:
    check_id: str
    title: str
    severity: str
    before: int  # affected URLs before (0 = not present)
    after: int  # affected URLs now (0 = fixed)


@dataclass(slots=True)
class PageChange:
    url: str
    before: int | None  # None = page not in the previous audit
    after: int | None  # None = page no longer crawled


@dataclass(slots=True)
class Comparison:
    previous_generated_at: str
    previous_score: int
    score: int
    scores_comparable: bool = True
    comparison_note: str = ""
    fixed: list[IssueChange] = field(default_factory=list)
    new: list[IssueChange] = field(default_factory=list)
    changed: list[IssueChange] = field(default_factory=list)  # still present, scope changed
    unchanged: int = 0
    pages: list[PageChange] = field(default_factory=list)

    @property
    def delta(self) -> int | None:
        return self.score - self.previous_score if self.scores_comparable else None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "delta": self.delta}


def load_previous(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "issues" in data and "score" in data else None


def comparable(previous: dict[str, Any], site: str) -> bool:
    return isinstance(previous.get("site"), str) and same_site(previous["site"], site)


def compare(
    previous: dict[str, Any],
    score: int,
    issues: list[Issue],
    page_scores: list[dict[str, Any]],
    coverage: dict[str, Any] | None = None,
) -> Comparison:
    before = {i["check_id"]: i for i in previous.get("issues", []) if "check_id" in i}
    after = {i.check_id: i for i in issues}
    result = Comparison(
        previous_generated_at=str(previous.get("generated_at", "")),
        previous_score=int(previous.get("score", 0)),
        score=score,
        scores_comparable=previous.get("scoring_version") == SCORING_VERSION,
    )
    if not result.scores_comparable:
        result.comparison_note = "Scoring model changed; scores are not comparable."
    elif coverage is not None:
        prior = previous.get("coverage", {})
        keys = (
            "audited_urls",
            "lab_urls",
            "field_urls",
            "rendered_pages",
            "truncated",
            "disabled_checks",
        )
        if any(prior.get(k) != coverage.get(k) for k in keys):
            result.scores_comparable = False
            result.comparison_note = "Audit coverage changed; scores are not directly comparable."
    for cid, old in before.items():
        if cid not in after:
            result.fixed.append(
                IssueChange(
                    cid, old.get("title", cid), old.get("severity", ""), len(old.get("urls", [])), 0
                )
            )
    for cid, issue in after.items():
        old = before.get(cid)
        if old is None:
            result.new.append(
                IssueChange(cid, issue.title, issue.severity.value, 0, len(issue.urls))
            )
        elif (
            set(old.get("urls", [])) != set(issue.urls)
            or old.get("severity") != issue.severity.value
        ):
            result.changed.append(
                IssueChange(
                    cid,
                    issue.title,
                    issue.severity.value,
                    len(old.get("urls", [])),
                    len(issue.urls),
                )
            )
        else:
            result.unchanged += 1
    old_pages = {p["url"]: p["score"] for p in previous.get("page_scores", []) if "url" in p}
    if old_pages and result.scores_comparable:
        new_pages = {p["url"]: p["score"] for p in page_scores}
        for url in sorted(old_pages.keys() | new_pages.keys()):
            b, a = old_pages.get(url), new_pages.get(url)
            if b != a:
                result.pages.append(PageChange(url, b, a))
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    for bucket in (result.fixed, result.new, result.changed):
        bucket.sort(key=lambda c: (rank.get(c.severity, 9), c.check_id))
    return result
