"""Core Web Vitals findings from PageSpeed Insights (field + lab) and Lighthouse (lab)."""

from __future__ import annotations

from collections.abc import Iterator

from ranq import sources
from ranq.analysis.performance import THRESHOLDS, PerfResult, rate
from ranq.checks.base import AuditContext, check
from ranq.models import Category, Effort, Issue, Severity

P = Category.PERFORMANCE
FIXES = {
    "LCP": "Optimize the largest element: compress/resize hero images (AVIF/WebP), preload it, "
    "avoid lazy-loading it, reduce server response time and render-blocking CSS/JS.",
    "INP": "Break up long JavaScript tasks, defer non-critical scripts, reduce third-party tags, "
    "and avoid heavy work in input handlers.",
    "CLS": "Reserve space for images/ads/embeds (width/height or aspect-ratio), avoid inserting "
    "content above existing content, use font-display: optional/swap with size-adjust.",
}


@check("core-web-vitals", P)
def core_web_vitals(ctx: AuditContext) -> Iterator[Issue]:
    results: list[PerfResult] = ctx.extras.get("performance", [])
    for metric in ("LCP", "INP", "CLS"):
        poor: dict[str, float] = {}
        meh: dict[str, float] = {}
        for r in results:
            if metric in r.field_data:
                bucket = (
                    poor
                    if r.field_categories[metric] == "poor"
                    else (meh if r.field_categories[metric] == "needs-improvement" else None)
                )
                if bucket is not None:
                    bucket[r.url] = r.field_data[metric]
        for bucket, sev, label in (
            (poor, Severity.HIGH, "poor"),
            (meh, Severity.MEDIUM, "needs improvement"),
        ):
            if bucket:
                yield Issue(
                    f"cwv-{metric.lower()}-{label.replace(' ', '-')}",
                    f"{metric} is '{label}' for real users on {len(bucket)} URL(s)",
                    sev,
                    P,
                    f"Chrome UX Report field data (75th percentile, mobile) via PageSpeed Insights. "
                    f"Thresholds: good <= {_fmt(metric, 0)}, poor > {_fmt(metric, 1)}.",
                    FIXES[metric],
                    effort=Effort.MEDIUM,
                    urls=sorted(bucket),
                    evidence=bucket,
                    source=sources.CORE_WEB_VITALS,
                )
    low_lab = {
        f"{r.url} ({r.tool})": round(r.performance_score)
        for r in results
        if r.performance_score is not None and r.performance_score < 50
    }
    if low_lab:
        yield Issue(
            "lab-performance-low",
            f"Lighthouse performance score below 50 on {len(low_lab)} run(s)",
            Severity.MEDIUM,
            P,
            "Lab scores are simulated (throttled mobile) and vary between runs; use them to "
            "diagnose, and field data (above) to judge real users.",
            "Open the Lighthouse report's 'Opportunities' section and address the top items.",
            effort=Effort.MEDIUM,
            urls=sorted({k.split(" (")[0] for k in low_lab}),
            evidence=low_lab,
            source=sources.PAGESPEED_API,
            estimate=True,
        )
    # Prefer field data per metric, not per entire result. Preserve other lab metrics
    # when field data is partial, and don't let a second tool overwrite a poor result.
    field_metrics = {(r.url, metric) for r in results for metric in r.field_data}
    lab_issues: dict[str, dict[str, float]] = {}
    for r in results:
        for metric, value in r.lab.items():
            if (
                metric in ("LCP", "CLS")
                and (r.url, metric) not in field_metrics
                and rate(metric, value) == "poor"
            ):
                metrics_for_url = lab_issues.setdefault(r.url, {})
                metrics_for_url[metric] = max(metrics_for_url.get(metric, value), value)
    if lab_issues:
        metrics = [m for m in ("LCP", "CLS") if any(m in v for v in lab_issues.values())]
        label = "/".join(metrics)
        yield Issue(
            "lab-cwv-poor",
            f"Lab {label} {'is' if len(metrics) == 1 else 'are'} poor on "
            f"{len(lab_issues)} URL(s) (no field data for these metrics)",
            Severity.MEDIUM,
            P,
            "No field data was returned for these metrics. Lab results are simulated "
            "and vary between runs; they do not establish real-user performance or why field "
            "data is unavailable.",
            " ".join(FIXES[m] for m in metrics),
            effort=Effort.MEDIUM,
            urls=sorted(lab_issues),
            evidence=lab_issues,
            source=sources.CORE_WEB_VITALS,
            estimate=True,
        )
    errors = {r.url: r.error for r in results if r.error}
    if errors:
        yield Issue(
            "perf-measurement-failed",
            "Some performance measurements failed",
            Severity.INFO,
            P,
            "PageSpeed/Lighthouse could not measure these URLs.",
            "Set PAGESPEED_API_KEY (free) to raise quota, or install lighthouse locally.",
            urls=sorted(errors),
            evidence=errors,
            source=sources.PAGESPEED_API,
        )


def _fmt(metric: str, idx: int) -> str:
    v = THRESHOLDS[metric][idx]
    return f"{v} ms" if metric != "CLS" else str(v)
