# Contributing to Ranq

Thanks for helping. Ranq is used to make decisions about real sites, so the bar for a change
is simple: every finding must be correct, cited and actionable, and the tool must stay polite
to the sites it crawls.

## Ways to help

- **Report a false positive.** If Ranq flags something that is correct on your site, that is
  a bug. Use the [false-positive form](https://github.com/H3M4N1H/ranq/issues/new?template=false_positive.yml)
  and include the check id (shown in the JSON report) and the smallest HTML that reproduces it.
- **Report a bug** or **request a feature** with the other issue forms.
- **Pick up an issue** labelled [good first issue](https://github.com/H3M4N1H/ranq/labels/good%20first%20issue)
  or [help wanted](https://github.com/H3M4N1H/ranq/labels/help%20wanted). Comment on it first
  so two people don't build the same thing.
- **Security issues** go through private reporting, never a public issue. See
  [SECURITY.md](SECURITY.md).

For anything larger than a bug fix (a new command, a new dependency, a change to scoring),
open an issue to agree on the approach before writing the code.

## Development setup

Requires Python 3.11+.

```bash
git clone https://github.com/H3M4N1H/ranq && cd ranq
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,full]" && playwright install chromium
pre-commit install
```

Before you push, run what CI runs:

```bash
ruff check src tests && ruff format --check src tests
mypy                           # strict mode
pytest -q                      # starts a local test site with planted problems
```

To try a change by hand against the test site:

```bash
python tests/serve_site.py 8765 &
ranq audit http://127.0.0.1:8765 --no-pagespeed --delay 0
```

## Where things live

`docs/ARCHITECTURE.md` has the full map. The parts most contributions touch:

| Path | What it holds |
|---|---|
| `src/ranq/checks/` | Audit checks, one module per area (technical, on-page, aeo, geo...) |
| `src/ranq/analysis/` | Analysis the checks build on: structured data rules, keywords, framework detection |
| `src/ranq/geo/ai_bots.py` | Registry of AI crawlers and their documented purpose |
| `src/ranq/sources.py` | Citations for the guidelines that checks are based on |
| `src/ranq/generators/` | Files that `ranq fix` writes |
| `tests/site/` | The local test site; add a page here when a check needs end-to-end coverage |
| `tests/unit/` | Fast tests that build an `AuditContext` from inline HTML |

## Writing a check

A check is a function that takes an `AuditContext` and yields `Issue`s:

```python
from collections.abc import Iterator

from ranq import sources
from ranq.checks.base import AuditContext, check
from ranq.models import Category, Effort, Issue, Severity


@check("image-alt", Category.ONPAGE)
def image_alt(ctx: AuditContext) -> Iterator[Issue]:
    # alt="" is valid for decorative images, so only a missing attribute counts
    hits = [p.url for p in ctx.pages if any(img.alt is None for img in p.images)]
    if hits:
        yield Issue(
            "image-alt",
            f"{len(hits)} page(s) have images without alt text",
            Severity.LOW,
            Category.ONPAGE,
            description="What is wrong and why it matters, in one or two sentences.",
            fix="The exact change to make.",
            effort=Effort.LOW,
            urls=hits,
            source=sources.IMAGES,
        )
```

(A simplified version of the existing check in `checks/technical.py`.) Every check must:

- **Cite its source.** Link the search engine's or AI operator's own documentation through
  `src/ranq/sources.py`. If a rule is a common heuristic rather than a documented rule, say
  so and set `estimate=True`.
- **Give an exact fix**, not "improve your content".
- **Avoid false positives on real sites.** Think about pages it should *not* fire on (app
  shells, business sites without a blog, sites with a hand-written llms.txt) and test them.
  A noisy check gets disabled by users, and then its correct findings are lost too.
- **Pick severity by impact on discovery**, not by how easy the fix is. Use `info` for
  optional advice.
- **Ship with tests** in `tests/unit/` covering at least one page that should trigger it and
  one that should not.

Built-in checks register on import; a new module goes in `BUILTIN_MODULES` in
`src/ranq/checks/__init__.py`. Third-party checks can be shipped as plugins instead (see the
Plugins section of the README and `tests/plugins/demo_plugin.py`).

## Ground rules

These are not negotiable, because they are why people can trust the tool:

- Obey robots.txt on every request, keep per-host rate limits, and never scrape search result
  pages or consumer AI apps.
- Never invent data. Generated markup and copy use only what is on the page or in `ranq.yaml`;
  anything unknown is left as a TODO.
- Never write to a site without a diff preview and confirmation, and only in a local directory.
- No paid APIs in the core audit. Optional integrations must degrade gracefully without a key.
- Treat everything crawled as untrusted input (escape it in reports, validate URLs).

## Pull requests

- Keep each PR to one change and explain *why* in the description.
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for anything users will notice.
- New dependencies need a reason; prefer an optional extra over a core dependency.
- CI must pass on Python 3.11, 3.12 and 3.13.

By contributing you agree that your work is released under the [MIT License](LICENSE), and
that you will follow the [Code of Conduct](CODE_OF_CONDUCT.md).
