# Automated audit health

Ranq scores detected issues, not rankings, content quality in every context, or actual AI
mentions and citations. The number is a transparent prioritization heuristic. There is no
validated universal SEO/AEO/GEO grade, and this model is not calibrated against ranking data.

## Why version 2 changes scores

Version 1 divided severity weights by four before applying its curve. A whole-site critical
finding alone scored 78; a medium finding alone scored 96. Those outcomes understated the
severity Ranq had assigned to the findings. Version 2 uses the existing weights in full.
It does not add findings, reverse page-type exemptions, or charge for optional INFO guidance.

| One finding affecting the entire audited site | Weight | Old score | Version 2 |
|---|---:|---:|---:|
| Critical | 100 | 78 | 37 |
| High | 40 | 90 | 67 |
| Medium | 15 | 96 | 86 |
| Low | 5 | 99 | 95 |
| Info | 0 | 100 | 100 |

These are explicit policy choices, not probabilities or Google/Lighthouse scores. Regression
scenarios cover clean sites, optional-only findings, isolated low issues, high/critical
failures, multiple medium issues, affected-page share, and large numbers of findings. A site
with two full-reach medium findings and five low findings scores 58; fixing a finding always
improves its unrounded score. A single low issue still leaves 95. We do not force every site
into a low band or penalize a legitimate one-page site for being small.

## Formula and scope

`score = round(100 * exp(-sum(penalties) / 100))`

- Site-wide finding: penalty = severity weight.
- Page finding: penalty = weight × (0.3 + 0.7 × affected unique URLs / audited HTML pages).
  The share is capped at 1. The 30% floor keeps a serious isolated defect visible in a large
  crawl; site-wide defects cannot be diluted by adding pages.
- INFO contributes zero. Effort affects task priority, not health.
- Audited sites have a minimum score of 1; no auditable HTML produces 0. Integer scores can
  saturate at 1 on severely broken sites; use the findings to distinguish them.
- Per-page scores apply the same weights to that page's findings; site-wide issues are
  excluded, so a page can score higher than the overall audit.
- JSON includes `scoring_version`, `score_breakdown` (weight, affected share, penalty), and
  `domain_scores`. Recompute the total from the breakdown to explain every deduction.

SEO, AEO and GEO are disjoint findings groups, not independently measured readiness grades:
AEO includes answer extraction and E-E-A-T; GEO includes crawler access, citation heuristics
and entity checks; SEO contains the remaining crawl, technical, performance, metadata,
structured-data, indexing, keyword and security checks. The overall score combines penalties,
not the arithmetic average of these group scores. No scored GEO findings means 100 for the
GEO group, **not** verified visibility in AI answers.

## Coverage and comparisons

Coverage shows audited HTML URLs, URLs with any lab measurements, URLs with field measurements,
rendered-page count, crawl truncation and disabled checks. A measurement count does not mean
all metrics were measured. Missing or failed performance requests are unknown, never proof
of fast pages. An audit cannot prove it discovered every URL. Missing data is disclosed rather
than being treated as a website defect or assigned invented performance values.

A score of 100 means no scored findings within the completed audit scope. It cannot certify
uncrawled pages, disabled checks, rankings, or actual AI visibility. Audits should be compared
with consistent configuration and measurements; even matching coverage cannot remove lab
variability or changes in detector behavior.

When the scoring version or tracked coverage differs, report comparisons suppress the numeric
delta and per-page score changes. Old reports without a scoring version are treated as legacy.
Issue changes remain available, labeled **no longer reported** instead of **fixed**: detection,
coverage, configuration or website changes can all explain a finding disappearing. The JSON
`fixed` key remains for backward compatibility; it does not prove remediation.

## Research informing the boundaries

- [Lighthouse performance scoring](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring)
  is a weighted combination of measured metric scores, with empirically derived distributions.
  Ranq's issue-severity model is not an alternative Lighthouse performance measurement.
- [Google's Core Web Vitals guidance](https://developers.google.com/search/docs/appearance/core-web-vitals)
  distinguishes loading, interactivity and stability. Ranq preserves these findings and
  distinguishes lab results from real-user measurements.

Future empirical calibration needs a representative, independently reviewed set of sites and
severity judgments. Two example domains cannot establish that calibration. Changes to these
policy weights must be documented and versioned, with the scenario tests updated deliberately.
