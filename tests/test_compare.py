import json
from pathlib import Path

from typer.testing import CliRunner

from ranq.cli import app
from ranq.models import Issue, Severity
from ranq.report.compare import compare
from ranq.report.scoring import SCORING_VERSION


def _issue(cid: str, sev: Severity, n: int) -> Issue:
    return Issue(cid, cid, sev, "on-page", "", "", urls=[f"https://s.test/{i}" for i in range(n)])


def test_compare_buckets() -> None:
    previous = {
        "site": "https://s.test",
        "scoring_version": SCORING_VERSION,
        "generated_at": "2026-10-01 10:00 UTC",
        "score": 70,
        "issues": [
            {"check_id": "h1-missing", "title": "no H1", "severity": "medium", "urls": ["a"]},
            {"check_id": "thin-content", "title": "thin", "severity": "medium", "urls": ["a", "b"]},
            {"check_id": "llms-txt-missing", "title": "llms", "severity": "low", "urls": ["x"]},
        ],
        "page_scores": [{"url": "https://s.test/", "score": 80}],
    }
    now = [_issue("thin-content", Severity.MEDIUM, 1), _issue("llms-txt-missing", Severity.LOW, 1)]
    now.append(_issue("og-url-mismatch", Severity.MEDIUM, 1))
    pages = [{"url": "https://s.test/", "score": 92}, {"url": "https://s.test/about", "score": 100}]
    c = compare(previous, 76, now, pages)
    assert c.delta == 6
    assert [i.check_id for i in c.fixed] == ["h1-missing"]
    assert [i.check_id for i in c.new] == ["og-url-mismatch"]
    assert [(i.check_id, i.before, i.after) for i in c.changed] == [("thin-content", 2, 1)]
    assert c.unchanged == 1
    assert [(p.url, p.before, p.after) for p in c.pages] == [
        ("https://s.test/", 80, 92),
        ("https://s.test/about", None, 100),
    ]


def test_audit_compares_with_previous_run(site_url: str, tmp_path: Path) -> None:
    cfg = tmp_path / "ranq.yaml"
    cfg.write_text(f"data_dir: {tmp_path / 'd'}\n")
    out = tmp_path / "report"
    args = [
        "audit",
        site_url,
        "-c",
        str(cfg),
        "-o",
        str(out),
        "--no-pagespeed",
        "--verbose",
        "-n",
        "20",
        "--delay",
        "0",
    ]
    first = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "Since" not in first.output
    # Pretend an issue existed last time and is fixed now.
    data = json.loads((out / "report.json").read_text())
    data["issues"].append({"check_id": "gone-now", "title": "Old problem", "severity": "high"})
    data["score"] -= 5
    (out / "report.json").write_text(json.dumps(data))
    second = CliRunner().invoke(app, args)
    assert second.exit_code == 0, second.output
    assert "Since" in second.output and "no longer reported  Old problem" in second.output
    saved = json.loads((out / "report.json").read_text())
    assert saved["comparison"]["fixed"][0]["check_id"] == "gone-now"
    assert "Changes since" in (out / "report.md").read_text()
    assert 'id="tab-changes"' in (out / "report.html").read_text()
    assert len(list((out / "history").glob("report-*.json"))) >= 1
    other = CliRunner().invoke(app, [*args, "--no-compare"])
    assert "Since" not in other.output
