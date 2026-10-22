## What and why

<!-- What does this change, and what problem does it solve? Link the issue: Fixes #123 -->

## How it was tested

<!-- New or updated tests, and any manual run (command + site). -->

## Checklist

- [ ] `ruff check src tests`, `ruff format --check src tests`, `mypy` and `pytest -q` pass locally
- [ ] New or changed checks cite their source and have tests for a page that should trigger them and one that should not
- [ ] User-visible changes have a line under `## [Unreleased]` in `CHANGELOG.md`
- [ ] Docs (README, `ranq init --example`) updated if behavior or options changed
