# Audit assessment

Ranq 0.5 replaces displayed percentage grades with a small, transparent findings rubric.
The old scores were not validated SEO grades. Changing a multiplier could make results
look better or worse without making them more accurate, so they are no longer presented.

## Rules

| Observed findings | Assessment |
|---|---|
| Any critical finding | Critical issues |
| Any high or medium finding | Needs attention |
| Low findings only | Minor issues |
| No actionable findings in an assessed area | No issues detected |
| Required analysis unavailable or area's checks not run, with no observed problems | Not assessed |

INFO is advice or an observation and does not worsen the assessment. Findings always take
precedence over missing coverage: an observed critical problem must not disappear behind
"Not assessed". Counts, affected URLs, severity, evidence and recommendations provide detail
within each status. Repeated/overlapping observations do not add arithmetic penalties.
This rubric is a Ranq reporting policy, not an industry certification or empirical grade.

SEO covers crawl, technical, metadata, structured-data, keyword, indexing and security checks.
AEO covers answer-extraction and E-E-A-T checks. GEO covers entity/citation/crawler checks.
Performance has a separate assessment, while its actionable findings also affect the overall
summary. These groups are convenient organization, not proof that a concern affects only one
search channel. Actual search rankings and AI visibility remain **Not measured** by an audit.

## What the labels do not establish

No issues detected means exactly that. It does not mean every possible test passed, that
content is relevant for every query, or that AI providers will cite it. Some checks are only
applicable to particular page types. AEO/GEO without the corresponding analysis is Not assessed;
performance without lab/field results is Not assessed unless another actionable measurement
exists. An entirely disabled audit cannot produce a clean assessment.

Coverage records what ran, HTML pages crawled, lab/field measurements and browser rendering.
Disabled checks and crawl limits stay visible. Partial coverage does not erase known findings,
and missing data is never invented as a positive or negative site signal. An audit cannot
prove it discovered all URLs. Counts of measured URLs do not mean every metric was available.

## Performance evidence

- A crawler's download duration includes connection/network transfer and body download. It
  is not TTFB or LCP. A single sample over 800 ms is INFO, with a recommendation to remeasure.
- Lab measurements are diagnostics and can vary. Poor LCP/CLS and low Lighthouse results
  remain actionable, with raw evidence. Multiple tools' poor lab values are retained using
  the worst observed value per metric, not silently overwritten by tool order.
- Field data describes observed real-user performance. For each URL/metric it takes precedence
  over the corresponding lab warning. Partial field data does not suppress unrelated lab
  metrics. Neither data source is a measurement of overall SEO quality.
- There are no additive deductions: a slow download and poor LCP cannot multiply a percentage
  penalty. Both may be useful evidence without proving the same root cause.

## History and compatibility

Displayed history tracks new, changed and **no longer reported** findings, not points won or
lost. A disappearing warning may reflect measurement variation, changed coverage, configuration,
detector changes or website changes; it is not proof of remediation. Changed URL sets count
as a change even when their size is unchanged.

JSON adds `assessment` (version 1) with overall and domain statuses, affected URLs, limitations,
and explicit unmeasured rankings/visibility. The old `score`, `domain_scores`, `page_scores`
score values, `score_breakdown` and comparison delta fields remain for existing consumers.
`score_deprecated: true` and `score_note` identify them as legacy, unvalidated penalty values.
New consumers should use `assessment`, page `status`, findings and coverage. The legacy formula
is unchanged; its continued presence is a compatibility measure, not a recommendation.

## Validation and references

Synthetic regression scenarios cover clean findings, disabled/unavailable checks, optional
advice, critical failures, many minor findings, overlapping performance observations, partial
field data, tool order and rendered output. They validate the implementation of the rubric;
they do not constitute an independently reviewed SEO benchmark.

- [Google: understanding page experience](https://developers.google.com/search/docs/appearance/page-experience)
  explains that there is no single page-experience ranking signal and good tool scores do not
  guarantee rankings.
- [web.dev: lab and field data differences](https://web.dev/articles/lab-and-field-data-differences)
  explains why simulated and real-user measurements differ.
- [Lighthouse variability](https://github.com/GoogleChrome/lighthouse/blob/main/docs/variability.md)
  documents variation even when website code is unchanged.

Ranq remains an automated diagnostic tool, not a replacement for reviewing query intent,
content usefulness, accessibility, Search Console evidence or real AI visibility observations.
