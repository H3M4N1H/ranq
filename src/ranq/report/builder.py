"""Turns raw issues into a prioritized report with a 30/60/90-day plan."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ranq import __version__
from ranq.analysis.framework import detect as detect_framework
from ranq.checks.base import AuditContext
from ranq.models import Effort, Issue, Severity
from ranq.report.assessment import assess, domain_for, status
from ranq.report.compare import Comparison
from ranq.report.limitations import DISCLAIMER, LIMITATIONS, SCOPE_NOTES
from ranq.report.scoring import SCORE_NOTE, SCORING_VERSION

STANDING_TASKS = {
    "30": [
        "Verify the site in Google Search Console and Bing Webmaster Tools (free) and submit "
        "the sitemap in both (`ranq index gsc-sitemap`, `ranq index bing`).",
        "Set up IndexNow (`ranq index indexnow-key`) so Bing, Yandex, Seznam, Naver and Yep "
        "learn about changes within minutes.",
        "Optionally publish llms.txt or explicit AI rules only when they serve a real need.",
    ],
    "60": [
        "Add or improve structured data for your key page types and validate it in Google's "
        "Rich Results Test and the Schema.org validator.",
        "For applicable informational content, review direct answers under question headings "
        "(see AEO findings).",
        "Make your brand entity consistent: same name, logo, description and links on every "
        "profile listed in the entity checklist.",
    ],
    "90": [
        "Create one genuinely useful, linkable asset (original data, tool, or guide) per "
        "content cluster and promote it to relevant communities and publications.",
        "Re-run `ranq audit` and compare; track AI answers monthly with `ranq visibility`.",
        "Review Search Console 'Pages' and 'Performance' reports for pages that are crawled "
        "but not indexed, and queries with high impressions but low CTR.",
    ],
}


@dataclass(slots=True)
class Report:
    site: str
    generated_at: str
    stats: dict[str, Any]
    issues: list[Issue]
    plan: dict[str, list[dict[str, Any]]]
    score: int
    pages: list[dict[str, Any]] = field(default_factory=list)  # per-page scores, worst first
    coverage: dict[str, Any] = field(default_factory=dict)
    score_breakdown: list[dict[str, Any]] = field(default_factory=list)
    domain_scores: dict[str, Any] = field(default_factory=dict)
    comparison: Comparison | None = None  # vs a previous audit of the same site
    extras: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER
    limitations: list[str] = field(default_factory=lambda: list(LIMITATIONS))
    scope_notes: list[str] = field(default_factory=lambda: list(SCOPE_NOTES))
    version: str = __version__

    @property
    def assessment(self) -> dict[str, Any]:
        return assess(self.issues, self.coverage)

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = Counter(i.severity.value for i in self.issues)
        return {s.value: counts.get(s.value, 0) for s in Severity}

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "generated_at": self.generated_at,
            "version": self.version,
            "assessment": self.assessment,
            "score_deprecated": True,
            "score": self.score,
            "score_note": SCORE_NOTE,
            "scoring_version": SCORING_VERSION,
            "coverage": self.coverage,
            "score_breakdown": self.score_breakdown,
            "domain_scores": self.domain_scores,
            "page_scores": self.pages,
            "comparison": self.comparison.to_dict() if self.comparison else None,
            "stats": self.stats,
            "severity_counts": self.severity_counts,
            "issues": [i.to_dict() for i in self.issues],
            "plan": self.plan,
            "extras": self.extras,
            "disclaimer": self.disclaimer,
            "limitations": self.limitations,
            "scope_notes": self.scope_notes,
        }


def _penalty(issue: Issue, fraction: float) -> float:
    return issue.severity.weight * (0.3 + 0.7 * fraction)


def _to_score(penalty: float) -> int:
    """Diminishing curve: small penalties cost about their face value (a penalty of 10 gives
    90), large ones approach 0 without reaching it, so very bad sites stay comparable and
    only an unreachable site scores 0."""
    return max(1, round(100 * math.exp(-penalty / 100)))


def health_score(issues: list[Issue], page_count: int) -> int:
    """100 * e^(-penalty/100) over weighted issue penalties. Page-level issues scale with the
    share of pages affected; site-wide issues always count in full, so adding pages cannot
    dilute them."""
    if page_count == 0:
        return 0  # nothing could be audited; see the site-unreachable issue
    return _to_score(sum(row["penalty"] for row in score_breakdown(issues, page_count)))


def score_breakdown(issues: list[Issue], page_count: int) -> list[dict[str, Any]]:
    """Expose every contribution so the score can be reproduced from report.json."""
    rows = []
    for issue in issues:
        fraction = (
            1.0 if issue.site_wide else min(len(set(issue.urls)), page_count) / max(page_count, 1)
        )
        rows.append(
            {
                "check_id": issue.check_id,
                "severity": issue.severity.value,
                "weight": issue.severity.weight,
                "affected_share": fraction,
                "site_wide": issue.site_wide,
                "penalty": _penalty(issue, fraction),
            }
        )
    return rows


def domain_scores(issues: list[Issue], page_count: int) -> dict[str, Any]:
    """Disjoint groups explain the overall penalty without counting a finding twice."""
    groups: dict[str, list[Issue]] = {"SEO": [], "AEO": [], "GEO": []}
    for issue in issues:
        domain = (
            "GEO"
            if issue.category == "geo"
            else ("AEO" if issue.category in ("aeo", "e-e-a-t") else "SEO")
        )
        groups[domain].append(issue)
    return {
        name: {
            "score": health_score(group, page_count),
            "scored_findings": sum(i.severity != Severity.INFO for i in group),
        }
        for name, group in groups.items()
    }


def page_scores(issues: list[Issue], page_urls: list[str]) -> list[dict[str, Any]]:
    """Score each crawled page on the page-level issues that list it (each counts as if it
    affected the whole site, i.e. the page). Site-wide issues are excluded: they are in the
    site score, and a page score should say how good that page itself is. Worst first."""
    found: dict[str, list[Issue]] = {url: [] for url in page_urls}
    for issue in issues:
        if issue.site_wide:
            continue
        for url in dict.fromkeys(issue.urls):
            if url in found:
                found[url].append(issue)
    rows = []
    for url, page_issues in found.items():
        page_issues.sort(key=lambda i: (i.severity.rank, i.check_id))
        rows.append(
            {
                "url": url,
                "score": _to_score(sum(_penalty(i, 1.0) for i in page_issues)),
                "status": status([str(i.severity) for i in page_issues]),
                "issues": [
                    {"check_id": i.check_id, "title": i.title, "severity": i.severity.value}
                    for i in page_issues
                ],
            }
        )
    return sorted(rows, key=lambda r: (r["score"], r["url"]))


def build_plan(issues: list[Issue]) -> dict[str, list[dict[str, Any]]]:
    plan: dict[str, list[dict[str, Any]]] = {"30": [], "60": [], "90": []}
    for issue in issues:
        if issue.severity == Severity.INFO:
            continue
        if issue.severity in (Severity.CRITICAL, Severity.HIGH) and issue.effort != Effort.HIGH:
            bucket = "30"
        elif issue.severity in (Severity.HIGH, Severity.MEDIUM):
            bucket = "60"
        else:
            bucket = "90"
        plan[bucket].append(
            {
                "check_id": issue.check_id,
                "title": issue.title,
                "severity": issue.severity.value,
                "effort": issue.effort.value,
                "fix": issue.fix,
            }
        )
    for bucket, tasks in STANDING_TASKS.items():
        plan[bucket].extend(
            {"check_id": "standing", "title": t, "severity": "plan", "effort": "-", "fix": ""}
            for t in tasks
        )
    return plan


def build_report(ctx: AuditContext, issues: list[Issue]) -> Report:
    crawl = ctx.crawl
    html_pages = ctx.pages
    home_page = crawl.pages.get(crawl.start_url) or next(iter(html_pages), None)
    stats = {
        "urls_crawled": len(crawl.pages),
        "html_pages": len(html_pages),
        "indexable_pages": sum(1 for p in html_pages if p.is_indexable),
        "noindex_pages": sum(1 for p in html_pages if p.noindex),
        "redirects": sum(1 for p in crawl.pages.values() if p.redirect_chain),
        "errors_4xx": sum(1 for p in crawl.pages.values() if 400 <= p.status < 500),
        "errors_5xx": sum(1 for p in crawl.pages.values() if p.status >= 500),
        "blocked_by_robots": len(crawl.blocked),
        "sitemap_urls": len(crawl.sitemaps.urls),
        "avg_response_ms": round(sum(p.elapsed_ms for p in html_pages) / len(html_pages))
        if html_pages
        else 0,
        "avg_word_count": round(sum(p.word_count for p in html_pages) / len(html_pages))
        if html_pages
        else 0,
        "framework": getattr(detect_framework(home_page), "name", None),
        "js_rendered": any(p.rendered for p in html_pages),
        "render_error": crawl.render_error,
        "truncated_at_max_pages": crawl.truncated,
        "resumed": crawl.resumed,
    }
    extras: dict[str, Any] = {}
    for key, value in ctx.extras.items():
        if hasattr(value, "to_dict"):
            extras[key] = value.to_dict()
        elif isinstance(value, list):
            extras[key] = [v.to_dict() if hasattr(v, "to_dict") else _plain(v) for v in value]
        else:
            extras[key] = _plain(value)
    return Report(
        site=crawl.site,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        stats=stats,
        issues=issues,
        plan=build_plan(issues),
        score=health_score(issues, len(html_pages)),
        pages=page_scores(issues, [p.url for p in html_pages]),
        extras=extras,
        coverage=audit_coverage(ctx),
        score_breakdown=score_breakdown(issues, len(html_pages)),
        domain_scores=domain_scores(issues, len(html_pages)),
    )


def audit_coverage(ctx: AuditContext) -> dict[str, Any]:
    """Report observed coverage separately; lack of measurements is not a site defect."""
    urls = {p.url for p in ctx.pages}
    perf = ctx.extras.get("performance", [])
    lab = {r.url for r in perf if r.lab or r.performance_score is not None} & urls
    field_urls = {r.url for r in perf if r.field_data} & urls
    rendered = sum(p.rendered for p in ctx.pages)
    notes = [
        f"{len(urls)} HTML page(s) audited; lab performance: {len(lab)}/{len(urls)}; "
        f"field performance: {len(field_urls)}/{len(urls)}; browser rendered: {rendered}/{len(urls)}.",
        "Undiscovered pages and unmeasured checks are not verified. "
        "Rankings and actual AI mentions/citations are not measured.",
    ]
    if ctx.crawl.truncated:
        notes.append("Crawl stopped at the page limit; this is a partial audit.")
    if ctx.config.disabled_checks:
        notes.append("Disabled checks: " + ", ".join(ctx.config.disabled_checks))
    if any(r.error for r in perf):
        notes.append("Some performance requests failed; missing results are not passes.")
    evaluated = (
        {domain_for(c["category"]) for c in ctx.extras.get("checks_run", [])} if urls else set()
    )
    if not ctx.extras.get("aeo"):
        evaluated.discard("AEO")
    if not ctx.extras.get("geo"):
        evaluated.discard("GEO")
    if not lab and not field_urls:
        evaluated.discard("Performance")
    return {
        "assessed_domains": sorted(evaluated),
        "audited_urls": sorted(urls),
        "lab_urls": sorted(lab),
        "field_urls": sorted(field_urls),
        "html_pages": len(urls),
        "lab_pages": len(lab),
        "field_pages": len(field_urls),
        "rendered_pages": rendered,
        "truncated": ctx.crawl.truncated,
        "disabled_checks": list(ctx.config.disabled_checks),
        "notes": notes,
    }


def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(value)
    return value
