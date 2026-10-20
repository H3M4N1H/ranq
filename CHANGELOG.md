# Changelog

All notable changes to Ranq (formerly SEOForge). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Recognize array-valued business types when extracting names, profiles and logos. Reuse
  published descriptions and founding dates in entity completeness checks and fact sheets,
  and preserve multi-type business markup in generated fixes.
- Recognize declared `alternateName` values instead of flagging them as inconsistent brands.
- Recognize About/Contact sections with linked, nonempty fragment targets. Keep them out of
  the crawl graph and avoid dead-end warnings for pages with valid section navigation.
  Missing or empty fragment targets still do not satisfy these checks.
- Apply Offer price requirements in Product/SoftwareApplication contexts rather than to
  every service catalog. Validate the nested price value, not merely the presence of a
  `priceSpecification` object; distinguish recommended currency from required price.
- Name the failing lab metric (LCP, CLS, or both) and give the corresponding fixes, without
  assuming why field data was unavailable.

### Changed

- Implicit AI crawler policies and word-overlap differences between brand descriptions are
  informational and no longer reduce the health score. Actual blocked search bots and
  explicit policy mismatches remain actionable findings.
- Scores may increase due to these detector corrections alone. Establish a fresh baseline
  with this version before measuring website improvements; retain the old reports.

## [0.4.0] - 2026-10-13

### Changed

- **Smaller default install.** Playwright and YAKE are no longer installed by default, which
  drops roughly 70 MB of downloads (Playwright's driver, NumPy, networkx). Install them as
  extras: `ranq[browser]` for JavaScript rendering (`--render`), `ranq[keywords]` for YAKE
  keyword extraction, or `ranq[full]` for both plus `google`. Without `ranq[browser]`,
  `--render` is skipped with a message saying what to install. Without `ranq[keywords]`,
  keywords come from TF-IDF only, and the report says so.

## [0.3.0] - 2026-10-12

### Changed

- **Renamed from SEOForge to Ranq.** The package, the command (`ranq audit ...`), the config
  file (`ranq.yaml`), the output folders (`ranq-report/`, `ranq-fixes/`), the data folder
  (`.ranq/`), the crawler User-Agent (`Ranq/<version>`, robots.txt group `Ranq`) and the
  plugin entry-point group (`ranq.checks`) all use the new name. An existing `seoforge.yaml`
  is still read when there is no `ranq.yaml`. The GitHub repository moved to
  `H3M4N1H/ranq`; the old URL redirects.
- Built and maintained by [NodeKraft](https://nodekraft.tech): credited in the README, the
  package metadata and the footer of every report.

### Security

- Report links built from crawled data (such as `sameAs` URLs) only allow `http(s)`; a
  `javascript:` URL could otherwise run in the HTML report when clicked.
- HTML comments in generated meta tags cannot be closed early by crawled text.
- CI scans the full history for secrets (gitleaks) and audits dependencies (pip-audit);
  workflow checkouts no longer keep the GitHub token; the PyPI publish action is pinned to a
  commit; Dependabot keeps actions and dependencies updated; `SECURITY.md` explains private
  reporting.
- `jinja2` minimum raised to 3.1.6.

## [0.2.0] - 2026-10-12

### Added

- **Per-page scores**: every crawled page gets a score from its own issues, shown in the CLI,
  a Pages tab in the HTML report, the Markdown report and `report.json`.
- **Audit comparison**: each audit is compared with the previous report for the same site (or
  `--compare old.json`): score change, fixed / new / changed issues and page-score changes.
  Every run is archived in `<out>/history/`. `--no-compare` turns it off.
- **Guided `seoforge init`**: asks a few questions pre-filled from what the home page already
  says (brand name, description, city, founding year, social profiles). `--example` writes
  the commented template.
- **Framework detection** (Next.js App/Pages Router, Nuxt, Astro, SvelteKit, Remix, Gatsby,
  Docusaurus, WordPress, Shopify, Wix, Squarespace, Webflow, Framer, Ghost, Hugo, Jekyll,
  Eleventy). `fix` writes `FRAMEWORK.md` saying where each file goes; Next.js App Router sites
  also get `app/robots.ts`, `app/sitemap.ts` and a safe JSON-LD component.
- New checks:
  - `no-custom-domain` (high): the site runs on a platform subdomain (about 80 hosts,
    including Vercel, Netlify, Hostinger, GitHub Pages, Cloudflare Pages, Wix and Webflow).
  - `site-unreachable` (critical): no crawlable HTML page, with the reason (HTTP status,
    fetch error, robots.txt, off-site redirect).
  - `h1-hidden-in-html` (medium): the H1 is served invisible and revealed by JavaScript,
    which delays Largest Contentful Paint.
  - `og-url-mismatch` (medium): og:url points to another page.
  - `jsonld-webpage-wrong-url` (medium): a WebPage node describes another URL (layout-level
    markup copied to every page).
  - `brand-description-inconsistent` (low): JSON-LD, llms.txt and config describe the brand
    differently.
  - `email-obfuscated` (low): Cloudflare Email Obfuscation hides the contact address.

### Changed

- **Health score**: site-wide issues (missing About page, llms.txt, robots.txt, Organization
  markup, HTTPS...) now count in full instead of being diluted by page count. A site where
  nothing could be crawled scores 0. Penalties map to the score on a diminishing curve
  (`100 * e^(-penalty/100)`), so sites with many problems stay comparable instead of all
  bottoming out at 0.
- `fix` builds JSON-LD on top of the site's existing markup and writes one `@graph` for the
  shared layout plus one per page, so each file can replace what is there without losing
  nodes.
- `fix` builds security headers from the live response headers and never weakens an existing
  value (for example `X-Frame-Options: DENY`).
- `fix` keeps a hand-written `llms.txt` and only appends pages it does not link yet.
- Running from a folder whose `seoforge.yaml` describes another site no longer applies that
  site's entity, competitors and keywords.
- Markdown mirrors and `llms-full.txt` skip hidden elements and keep words in flex/grid
  layouts apart.
- Calls to action phrased as questions ("Ready to start?") are no longer treated as AEO
  questions.
- Images sized by CSS (Next.js `fill`, Tailwind `w-N h-N`, inline width/height or
  aspect-ratio) are no longer reported as missing dimensions.
- Cloudflare `/cdn-cgi/` endpoints are never crawled.
- GitHub Actions use checkout, setup-python and upload-artifact v7 (Node 24).

### Fixed

- The Organization generator dropped the address and founders already published on the site.
- The Wikidata draft lowercased brand names ("brightWorks") and repeated "<Name> is a".
- JSON-LD output now escapes `</` so crawled text cannot close the script tag.

## [0.1.0] - 2026-10-03

First release: robots-aware crawler, technical / on-page / performance audit, structured data
validation and generators, AEO and E-E-A-T checks, GEO (AI crawler policy, llms.txt, entity
tools, citation score, AI-visibility tracker), indexing (IndexNow, Search Console, Bing),
off-page helpers, `seoforge fix`, HTML / Markdown / JSON reports, Docker image, GitHub Action
and CI.

[0.4.0]: https://github.com/H3M4N1H/ranq/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/H3M4N1H/ranq/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/H3M4N1H/ranq/compare/2e7659f...v0.2.0
[0.1.0]: https://github.com/H3M4N1H/ranq/tree/2e7659f
