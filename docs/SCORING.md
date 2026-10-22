# Audit assessment

Ranq 0.5 presents a **Ranq custom grade /100** alongside a severity assessment.
This is a transparent heuristic, not an industry standard, empirical SEO-quality percentage,
or ranking/AI-visibility prediction. Whole numbers avoid suggesting unsupported precision.

## Custom grade (version 1)

Weights: critical 100, high 40, medium 15, low 5, INFO 0. These are Ranq policy choices,
not measured ranking effects. They are not tuned to any particular website or desired score.

1. Group observations by check ID. Group field CWV, lab CWV and Lighthouse performance
   findings into one `web-performance` family to avoid charging overlapping evidence twice.
   Other performance checks (such as hidden H1) remain independent.
2. Within each family, use the highest severity weight per affected URL. Duplicate reports
   cannot increase the grade penalty. A site-wide observation applies to every audited page.
3. Family penalty = `0.3 * highest weight + 0.7 * mean weight across audited HTML pages`.
   Unaffected pages contribute zero. Missing affected URLs are conservatively site-wide.
   The baseline prevents a genuine defect disappearing into a large crawl; the mean reflects
   reach. Site-wide findings cannot be diluted by adding pages.
4. Grade = `round(100 * exp(-sum(family penalties) / 100))`. This monotonic, diminishing
   curve avoids a sudden zero when several findings accumulate. INFO contributes nothing.
   Example: one medium finding on all pages yields 86; one low yields 95; one critical
   yields 37. The severity status always remains visible beside the number.
5. Apply the same formula independently to each area. The overall grade includes all
   findings directly; it is not an average padded by clean or unavailable areas.

No audited HTML pages means **Not assessed**, not zero or 100. An area with neither executed
analysis nor observed actionable findings is also ungraded. Coverage limitations remain
visible but do not invent site defects. Grades from different configurations or coverage
are not directly comparable. Even 100 only means no scored findings within checks run.

The JSON `assessment.grade` and each `assessment.domains.*.grade` contain version, score,
family deductions and explanatory note. Status and grade are complementary: the number
summarizes accumulated findings; the status highlights the worst observed severity.


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
within each status. Repeated observations do not add duplicate arithmetic penalties.
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
- Slow downloads are INFO. Overlapping lab/field performance findings share a grade family;
  all evidence remains visible even when it adds no further deduction.

## History and compatibility

Displayed history tracks new, changed and **no longer reported** findings, not points won or
lost. A disappearing warning may reflect measurement variation, changed coverage, configuration,
detector changes or website changes; it is not proof of remediation. Changed URL sets count
as a change even when their size is unchanged.

JSON adds `assessment` (version 2) with overall and domain statuses, affected URLs, limitations,
and explicit unmeasured rankings/visibility. The old `score`, `domain_scores`, `page_scores`
score values, `score_breakdown` and comparison delta fields remain for existing consumers.
`score_deprecated: true` and `score_note` identify them as legacy, unvalidated penalty values.
New consumers should use `assessment.grade`, area grades, page `status`, findings and coverage. The legacy formula
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
