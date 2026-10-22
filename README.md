# Ranq

[![CI](https://github.com/H3M4N1H/ranq/actions/workflows/ci.yml/badge.svg)](https://github.com/H3M4N1H/ranq/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ranq.svg)](https://pypi.org/project/ranq/)
[![Python](https://img.shields.io/pypi/pyversions/ranq.svg)](https://pypi.org/project/ranq/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/H3M4N1H/ranq/blob/main/LICENSE)

**Free, open-source CLI that audits and optimizes websites for search engines (SEO), answer
engines (AEO) and generative AI engines such as ChatGPT search, Perplexity and Claude (GEO) -
and submits them to every index it legitimately can.**

```bash
pipx install ranq                 # or: pip install ranq
ranq audit https://your-site.com
```

![Ranq auditing a live site, then listing which AI crawlers can access it](https://raw.githubusercontent.com/H3M4N1H/ranq/main/docs/demo.gif)

*A live audit of nodekraft.tech, then its AI-crawler access table. Network waits are
time-lapsed; regenerate with [`scripts/record_demo.py`](https://github.com/H3M4N1H/ranq/blob/main/scripts/record_demo.py).*

No paid APIs. No accounts required for the core audit. MIT licensed. One command gives you a
prioritized report covering technical SEO, Core Web Vitals, structured data, answer-engine
readiness and AI-crawler access; a second generates the fixes (robots.txt, sitemap, llms.txt,
JSON-LD, redirects) for your stack.

Built and maintained by [NodeKraft](https://nodekraft.tech), a security-first digital agency in
Chennai. Want the findings fixed for you? [Talk to us](https://nodekraft.tech).

> **Honesty first.** No tool can guarantee rankings, indexing of every page or keyword, or that
> any AI system will know, cite or recommend your site. Ranq maximizes *eligibility,
> discoverability and citation likelihood*, labels every heuristic as an estimate, cites the
> guideline behind every finding, and never uses spam tactics. See
> [What Ranq cannot do](#what-ranq-cannot-do).

```
ranq audit https://example.com          # crawl + prioritized HTML/Markdown/JSON report
ranq fix https://example.com            # robots.txt, sitemap, llms.txt, JSON-LD, redirects...
ranq diagnose https://example.com/page  # why isn't this URL indexed?
ranq geo bots https://example.com       # which AI crawlers can access the site
```

![Ranq HTML report](https://raw.githubusercontent.com/H3M4N1H/ranq/main/docs/report-screenshot.png)

*The HTML report for the bundled test site, which has planted problems. Open the full
[example report](https://github.com/H3M4N1H/ranq/blob/main/docs/example-report/report.html)
(download it and open it in a browser) or read the
[Markdown version](https://github.com/H3M4N1H/ranq/blob/main/docs/example-report/report.md).
Changes between versions are in the
[CHANGELOG](https://github.com/H3M4N1H/ranq/blob/main/CHANGELOG.md).*

## What it does

| Area | Highlights |
|---|---|
| **Crawler** | Async, robots.txt-aware (RFC 9309 wildcards + longest match), per-host rate limit and `Crawl-delay`, redirect-chain capture, SQLite cache, resumable (`--resume`), optional JavaScript rendering with Playwright, site graph (click depth, inlinks, orphans) |
| **Technical SEO** | Status codes, broken links, redirect chains/loops, soft 404s (site-wide probe + heuristics), HTTPS/HSTS/mixed content, www/http canonicalization, robots.txt validity, sitemap validity and consistency, canonicals, meta robots / X-Robots-Tag, hreflang, viewport, lang, images, compression, security headers, duplicate and near-duplicate content (SimHash), sites on a platform subdomain instead of their own domain (~80 hosts: Vercel, Netlify, Hostinger, GitHub Pages, Wix...), unreachable sites |
| **Performance** | Core Web Vitals field data (CrUX via the free PageSpeed Insights API) and lab data (PageSpeed / local Lighthouse CLI); H1 served invisible until JavaScript runs (entrance animations that delay LCP); images sized by width/height, CSS aspect-ratio or utility classes |
| **On-page & keywords** | Titles, meta descriptions, headings, thin content, JS-only content, anchors, internal linking, Open Graph (including og:url pointing to another page); keyword extraction (TF-IDF, YAKE, n-grams), rule-based intent, topic clustering (local sentence-transformers if installed, else TF-IDF), cannibalization, competitor content gap, opt-in cached Google Autosuggest ideas, keyword-to-page map |
| **Structured data** | JSON-LD extraction and validation (required/recommended properties, nested entities, ISO dates, `@graph`, FAQ visibility policy, WebPage nodes describing another URL); generators for Organization, WebSite (+SearchAction), WebPage, Article, Product, FAQPage, HowTo, BreadcrumbList, Person with `sameAs`, merged with the markup already on the site into one `@graph` for the layout and one per page |
| **AEO** | Question-style headings (calls to action such as "Ready to start?" excluded), 40-60 word answer blocks, answer drafts trimmed from *your own* text, FAQ/definition/steps/table detection, E-E-A-T checks (author, author page, dates, citations, About/Contact/Privacy) |
| **GEO** | Per-bot robots.txt policy for 15 AI crawlers/tokens (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended, CCBot, Bytespider, Meta-ExternalAgent, Amazonbot, cohere-ai); `/llms.txt`, `/llms-full.txt` and Markdown mirrors; entity fact sheet; sameAs graph, brand-consistency checklist and a check that markup, llms.txt and config describe the brand the same way; contact email hidden by Cloudflare obfuscation; Wikidata search + QuickStatements draft; citation-friendliness score; Common Crawl presence; AI-visibility tracker (SQLite) |
| **Indexing** | Sitemap generator, IndexNow (key file + verified batch submission of changed URLs), Google Search Console API (sitemap submit, quota-aware URL Inspection), Bing Webmaster API, engine coverage table, "why isn't this indexed?" diagnostic |
| **Off-page** | Opportunity checklist, curated directory list, robots-aware broken-link finder with Wayback lookups, unlinked brand-mention finder (Hacker News + Wikipedia APIs), strict anti-spam policy |
| **Reporting** | Prioritized issues (Critical/High/Medium/Low) with impact, effort, exact fix, source and evidence; evidence-based SEO/AEO/GEO assessments with coverage and per-page findings; framework detection; standalone HTML dashboard + Markdown + JSON; 30/60/90-day plan; "what this tool cannot do" section |
| **`ranq fix`** | Ready-to-paste robots.txt, sitemap.xml, llms.txt (extends a hand-written one instead of replacing it), JSON-LD, meta tags, security headers (built from your live headers, never weakening them) and redirects for nginx, Apache, Vercel, Netlify and Cloudflare. A FRAMEWORK.md says where each file goes in the detected stack, and Next.js App Router sites also get `app/robots.ts`, `app/sitemap.ts` and a JSON-LD component. Applies to a *local* directory only after a diff preview and per-file confirmation |

## Install

Requires Python 3.11+.

```bash
pipx install ranq                                   # or: pip install ranq
pipx install git+https://github.com/H3M4N1H/ranq  # latest main, before a PyPI release
# Optional extras (pip: pip install "ranq[browser,keywords,google]", or "ranq[full]"):
pipx inject ranq playwright && playwright install chromium  # JavaScript rendering (--render)
pipx inject ranq yake          # YAKE keyword extraction next to TF-IDF (pip: "ranq[keywords]")
pipx inject ranq google-auth   # Search Console via service account (pip: "ranq[google]")
pipx inject ranq sentence-transformers  # local semantic clustering (large: PyTorch)
npm install -g lighthouse          # local Lighthouse lab runs (--lighthouse)
```

From source:

```bash
git clone https://github.com/H3M4N1H/ranq && cd ranq
python -m venv .venv && source .venv/bin/activate
pip install -e ".[full]"
```

Or with Docker:

```bash
docker build -t ranq .                              # add --build-arg WITH_BROWSER=1 for --render
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" ranq audit https://example.com
```

## Quickstart

```bash
ranq init --site https://example.com       # a few questions, pre-filled from your home page (optional)
ranq audit https://example.com              # report in ./ranq-report/report.html
ranq audit https://example.com --render --max-pages 1000 --competitor https://rival.com/page
ranq fix https://example.com                # files in ./ranq-fixes (see INDEX.md)
ranq fix https://example.com --apply-to ./public   # diff + confirm, then write locally
ranq diagnose https://example.com/missing-page --crawl-pages 200
ranq geo bots https://example.com           # which AI crawlers can access the site
```

## Commands

| Command | Purpose |
|---|---|
| `audit URL` | Crawl and report. Options: `--max-pages`, `--depth`, `--delay`, `--concurrency`, `--render`, `--resume`, `--cached`, `--check-external`, `--competitor URL` (repeatable), `--suggest`, `--lighthouse`, `--no-pagespeed`, `--format html/md/json`, `--fail-on critical/high/medium/low`, `--compare old.json` / `--no-compare` (by default each audit is compared with the previous report for the same site; every run is also kept in `<out>/history/`) |
| `fix URL` | Generate fix files. `--ai-policy allow-all/search-only/deny-all`, `--redirect-map old_new.csv`, `--apply-to DIR [--yes]` |
| `diagnose URL` | Robots, status, redirects, noindex, canonical, rendering, soft 404, sitemap, internal links, optional `--gsc` URL Inspection |
| `geo bots / llms / entity / commoncrawl` | AI crawler access table; llms.txt + mirrors only; entity + Wikidata; Common Crawl presence |
| `visibility init / add / prompts / log / import / run / report` | AI-visibility tracker (see below) |
| `index engines / indexnow-key / indexnow / gsc-sitemap / gsc-inspect / bing` | Submissions. All ask for confirmation; all support `--dry-run` |
| `offpage checklist / policy / broken-links / mentions` | Ethical link-building helpers |

### AI-visibility tracker

AI assistants have no free, permitted API for "does this assistant mention my brand", and
automating their consumer apps violates their terms. So the tracker is a log:

```bash
ranq visibility init                                   # prompts from entity.name/category/city
ranq visibility add "best kanban app for small teams"
ranq visibility prompts
ranq visibility log 3 perplexity --mentioned --cited-url https://example.com/guide
ranq visibility import answers.csv                     # prompt,engine,date,mentioned,cited_url,position,notes
ranq visibility run gemini --cmd "python my_gemini_free_tier.py {prompt}"   # your own permitted tool
ranq visibility report --json visibility.json
```

`run` executes *your* command once per prompt (no shell; `{prompt}` is passed as one
argument) and detects brand mentions and links to your domain in its output.

## Configuration (`ranq.yaml`)

Every field is optional; `ranq init` writes one by asking a few questions (pre-filled from what your home page already says), and `ranq init --example` writes a commented file with every setting. API keys are read from
environment variables, never from the YAML.

```yaml
site: https://example.com
crawl: {max_pages: 500, delay_seconds: 0.5, concurrency: 4, render_js: false, exclude: ["/wp-admin"]}
entity:
  name: Example Inc.
  description: One factual sentence about what you do.
  category: project management software
  city: Chennai
  founded: "2019"
  same_as: [https://github.com/example, https://www.linkedin.com/company/example]
geo:
  ai_bot_preset: search-only        # allow-all | search-only | deny-all | custom
  ai_bots: {CCBot: deny}            # per-bot overrides
competitors: [https://competitor.example/pricing]
seed_keywords: [project management]
report: {output_dir: ranq-report, fail_on: never}
disabled_checks: [deep-pages]
plugins: [mycompany.ranq_checks]
```

`search-only` (the default) allows AI search and user-initiated fetchers - so answers can cite
and link you - and blocks training crawlers. Allowed bots inherit your `*` rules, so private
paths stay private.

## Free API keys

All optional; the audit works without any of them.

**PageSpeed Insights (Core Web Vitals)** - works without a key at low volume. For a higher
free quota: Google Cloud Console → create a project → *APIs & Services* → enable **PageSpeed
Insights API** → *Credentials* → **Create API key**. Then `export PAGESPEED_API_KEY=...`.

**Google Search Console** (sitemap submission, URL Inspection):
1. Verify your site in [Search Console](https://search.google.com/search-console).
2. Google Cloud Console → enable the **Google Search Console API**.
3. Either: create a **service account**, download its JSON key, `export
   GSC_SERVICE_ACCOUNT_FILE=/path/key.json`, `pip install -e ".[google]"`, and add the
   service account's email under Search Console → *Settings → Users and permissions* (Full
   permission; Owner if sitemap submission is refused).
   Or: `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/webmasters,https://www.googleapis.com/auth/cloud-platform`
   then `export GSC_ACCESS_TOKEN=$(gcloud auth application-default print-access-token)`.
4. Quotas (enforced locally): URL Inspection 2,000/day and 600/minute per property.

**Bing Webmaster Tools**: verify the site at [bing.com/webmasters](https://www.bing.com/webmasters)
(you can import from Search Console) → *Settings → API access* → generate an **API key** →
`export BING_WEBMASTER_API_KEY=...`.

**IndexNow** (Bing, Yandex, Seznam.cz, Naver, Yep): `ranq index indexnow-key`, upload
the generated `<key>.txt` to your site root, `export INDEXNOW_KEY=<key>`, then
`ranq index indexnow https://example.com` (submits only URLs whose content changed).

## GitHub Action

Audit every deploy and upload the report as an artifact (see `docs/github-action.md`):

```yaml
- uses: H3M4N1H/ranq@main
  with:
    url: https://example.com
    fail-on: critical
    pagespeed-api-key: ${{ secrets.PAGESPEED_API_KEY }}
```

## Plugins

Checks are plain functions registered with `@check`. Ship them in any module and list it under
`plugins:` or expose it via the `ranq.checks` entry-point group. See
[`docs/ARCHITECTURE.md`](https://github.com/H3M4N1H/ranq/blob/main/docs/ARCHITECTURE.md) and `tests/plugins/demo_plugin.py`.

## Ethics

- Obeys robots.txt on every request and redirect hop (including competitor, mention and
  broken-link checks), rate-limits per host and honours `Crawl-delay`.
- Never cloaks, generates doorway pages, fake reviews, or spam links; never scrapes search
  result pages or consumer AI apps.
- Never uses Google's Indexing API (it is only for JobPosting and BroadcastEvent pages).
- Generated markup and copy use only data from your pages or `ranq.yaml`; anything unknown
  is left as a TODO rather than invented.
- Never modifies a site without a diff preview and confirmation, and only in a local directory.

## Assumptions

- "Submit to every index" means the legitimate channels that exist: Google Search Console,
  Bing Webmaster Tools, IndexNow, sitemaps and robots.txt. Other engines either use those
  indexes or offer no submission (listed by `ranq index engines`).
- Keyword volumes are omitted rather than estimated, because no free, reliable source exists.
- The default AI crawler policy is `search-only`; change it in `ranq.yaml`.
- The crawler identifies itself as `Ranq/<version>` and matches robots.txt groups for
  `Ranq` (falling back to `*`).
- Response cache is written on every crawl but only read with `--resume` / `--cached`, so a
  normal audit always reflects the live site.
- Thresholds such as "title > 60 characters", "under 200 words" or "40-60 word answers" are
  common heuristics, not search engine rules; findings based on them are labelled estimates.

## What Ranq cannot do

- Guarantee rankings, indexing of any page, or traffic.
- Make any LLM know, cite or recommend your site; it can only make your content easier to
  retrieve, quote and attribute.
- Provide search volume, keyword difficulty or a full backlink index (use Search Console and
  Bing Webmaster Tools "Links" reports for your real backlinks).
- Enforce robots.txt: bots that ignore it must be blocked at the server/CDN/WAF.
- Promise anything from llms.txt: it is a community proposal that major AI providers have not
  confirmed using.
- Bring back FAQ/HowTo rich results in Google (restricted/removed in 2023), or the sitelinks
  search box (retired in 2024).
- Render pages exactly like Googlebot; headless Chromium is a close approximation.
- Measure Core Web Vitals field data for low-traffic URLs (CrUX has no data for them).

## Roadmap

- Incremental crawls driven by sitemap `lastmod` and HTTP conditional requests
- Log-file analysis (real Googlebot/AI-bot hits vs. robots policy)
- Search Console Search Analytics import (queries, CTR, position) into the keyword map
- More rich-result validators (Event, JobPosting, Recipe, VideoObject details) and SHACL export
- Multi-language keyword extraction (stopword lists beyond English)
- Trend charts across the audit history (`<out>/history/`)
- WordPress / static-site generator integrations for `fix --apply-to`

## Development

```bash
pip install -e ".[dev,full]" && playwright install chromium
pre-commit install
pytest -q                      # spins up a local test site with planted issues
ruff check src tests && ruff format --check src tests && mypy
python tests/serve_site.py 8765 & ranq audit http://127.0.0.1:8765 --no-pagespeed --delay 0
python scripts/record_demo.py https://nodekraft.tech   # README GIF; needs agg on PATH
```

### Releasing

1. Bump `__version__` in `src/ranq/__init__.py` and add a section to `CHANGELOG.md`.
2. Commit, then `git tag v<version> && git push origin v<version>`.
3. The Release workflow checks the tag matches the version, runs the tests, builds, creates the
   GitHub Release with the changelog notes and the sdist/wheel attached, and publishes to PyPI.

One-time PyPI setup (no API token needed): on pypi.org, *Your projects -> Publishing -> Add a
new pending publisher* with owner `H3M4N1H`, repository `ranq`, workflow `release.yml`,
environment `pypi`. Then in the GitHub repository settings add the variable
`PUBLISH_TO_PYPI` = `true` (*Settings -> Secrets and variables -> Actions -> Variables*).
Until then the PyPI job is skipped and releases go to GitHub only.

## Contributing

Bug reports, false positives and pull requests are welcome. A wrong finding is a bug: if Ranq
flags something that is correct on your site, [open a false-positive report](https://github.com/H3M4N1H/ranq/issues/new?template=false_positive.yml)
with the URL and what you expected. New to the codebase? Start with an issue labelled
[good first issue](https://github.com/H3M4N1H/ranq/labels/good%20first%20issue); most checks
are a single function with a test. See
[CONTRIBUTING.md](https://github.com/H3M4N1H/ranq/blob/main/CONTRIBUTING.md) for setup, the
check API and the review bar, and report vulnerabilities privately as described in
[SECURITY.md](https://github.com/H3M4N1H/ranq/blob/main/SECURITY.md).

## License

MIT - see [LICENSE](https://github.com/H3M4N1H/ranq/blob/main/LICENSE).

### Understanding the assessment

Ranq reports **Critical issues**, **Needs attention**, **Minor issues**, **No issues detected**,
or **Not assessed**, with separate SEO/AEO/GEO findings and measurement coverage. These are
severity summaries alongside a **Ranq custom grade /100**. The grade uses severity and
affected-page coverage, deduplicates overlapping performance findings, and excludes optional
advice. It is a custom heuristic, not an industry standard or ranking prediction. Unknown
areas remain unassessed; 100 only means no scored findings in the checks run.
See [the assessment rules](docs/SCORING.md) for the simple rubric and its limitations.

Terminal audits show a compact summary by default. Use `ranq audit URL --verbose` (or `-v`)
for per-page findings, informational notes, detailed comparisons and all report paths.
HTML, Markdown and JSON reports retain the full detail.
