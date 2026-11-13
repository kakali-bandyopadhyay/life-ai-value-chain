"""Parity and static wiring checks for the dependency-free browser layer."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest

from ai_value_chain.data import DATA_DIR, load_controls, load_use_cases
from ai_value_chain.render import build
from ai_value_chain.scoring import rank


REPO_ROOT = Path(__file__).resolve().parents[1]
COMBINATIONS = (
    ("medium", (5, 3, 2)),
    ("high", (5, 3, 2)),
    ("low", (5, 3, 2)),
    ("medium", (10, 0, 0)),
    ("medium", (0, 0, 10)),
    ("high", (1, 1, 1)),
    ("medium", (0, 0, 0)),
)


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []
        self.current: dict[str, str | None] | None = None
        self.contents: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = dict(attrs)
            self.scripts.append(self.current)
            self.contents.append("")

    def handle_data(self, data):
        if self.current is not None:
            self.contents[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = None


def _page(tmp_path: Path) -> str:
    html_path, _ = build(tmp_path)
    return html_path.read_text(encoding="utf-8")


def test_inline_data_and_classic_relative_scripts(tmp_path):
    page = _page(tmp_path)
    parser = ScriptParser()
    parser.feed(page)
    external = [script for script in parser.scripts if script.get("src")]
    assert external == [
        {"src": "rank.js", "defer": None},
        {"src": "app.js", "defer": None},
    ]
    assert all(script.get("type") != "module" for script in external)
    inline = [script for script in parser.scripts if script.get("type") == "application/json"]
    assert len(inline) == 1 and inline[0].get("id") == "vc-data"
    content = parser.contents[parser.scripts.index(inline[0])]
    embedded = json.loads(content)
    cases = load_use_cases()
    controls = load_controls()
    worked_ids = sorted(row["use_case_id"] for row in cases if row["worked_governance"])
    summary = {}
    for use_case_id in worked_ids:
        counts = Counter(row["test_result"] for row in controls if row["use_case_id"] == use_case_id)
        summary[use_case_id] = {
            "pass": counts["pass"],
            "fail": counts["fail"],
            "not tested": counts["not tested"],
            "exceptions": sum(bool(row.get("exception_id")) for row in controls if row["use_case_id"] == use_case_id),
        }
    expected = {
        "use_cases": cases,
        "scoring_config": json.loads((DATA_DIR / "scoring_config.json").read_text(encoding="utf-8")),
        "controls_summary": summary,
        "scenario": json.loads((DATA_DIR / "scenario.json").read_text(encoding="utf-8-sig")),
    }
    assert embedded == expected
    assert not any(re.search(r"https?://", content, re.I) for content in parser.contents)


def test_explorer_panel_markup_and_safety(tmp_path):
    page = _page(tmp_path)
    config = json.loads((DATA_DIR / "scoring_config.json").read_text(encoding="utf-8"))
    sliders = re.findall(r'<input id="weight-([^\"]+)" type="range" min="(\d+)" max="(\d+)" step="(\d+)" value="(\d+)"', page)
    assert sliders == [(key, "0", "10", "1", str(config["default_weights"][key])) for key in ("value", "feasibility", "data_readiness")]
    for key, label in (("value", "Value"), ("feasibility", "Feasibility"), ("data_readiness", "Data readiness")):
        value = config["default_weights"][key]
        assert f'aria-valuetext="{label} weight {value}"' in page
    radios = re.findall(r'<label class="appetite-option"><input type="radio" name="appetite" value="(\w+)"( checked)?><span>([^<]+)</span></label>', page)
    assert [(value, label) for value, _, label in radios] == [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    assert [value for value, checked, _ in radios if checked] == [config["default_max_risk"]]
    panel = page.split('<div class="explorer-panel"', 1)[1].split("</div></section>", 1)[0]
    stage_chips = re.findall(r'<button type="button" class="stage-chip" data-stage="([^"]+)" aria-pressed="(true|false)">', panel)
    assert [stage for stage, _ in stage_chips] == ["all", "distribution", "underwriting", "policy_admin", "servicing", "claims"]
    assert stage_chips[0][1] == "true"
    assert 'class="reset-ranking"' in panel
    assert 'aria-live="polite"' in panel
    css = page.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "@media(min-width:1100px){.explorer-controls{grid-template-columns:repeat(4,minmax(0,1fr))}}" in css
    assert "@media(min-width:640px) and (max-width:1099px){.explorer-controls{grid-template-columns:repeat(2,minmax(0,1fr))}}" in css
    assert "@media(max-width:639px){.explorer-controls{grid-template-columns:1fr}" in css
    assert ".stage-chip{white-space:nowrap}" in css
    assert ".ranked-table tr.is-selected td" in css
    for name in ("rank.js", "app.js"):
        source = (REPO_ROOT / "docs" / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", source, re.I)
        assert not re.search(r"alert\s*\(|confirm\s*\(|prompt\s*\(|localStorage|document\.cookie", source, re.I)
    assert '<div class="explorer-panel"' in page and "Explore the ranking" in page


def test_rank_javascript_matches_python(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js not found on PATH; JavaScript parity comparison skipped")
    args = [f"{appetite}:{','.join(map(str, weights))}" for appetite, weights in COMBINATIONS]
    completed = subprocess.run(
        [node, str(REPO_ROOT / "tests" / "parity.cjs"), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    actual = json.loads(completed.stdout)
    cases = load_use_cases()
    assert len(actual) == len(COMBINATIONS)
    for result, (appetite, weights) in zip(actual, COMBINATIONS):
        python_weights = dict(zip(("value", "feasibility", "data_readiness"), weights))
        if sum(weights) == 0:
            with pytest.raises(ValueError, match="Set at least one weight above 0"):
                rank(cases, python_weights, appetite)
            assert result["error"] == "Set at least one weight above 0"
            continue
        ranked, ineligible = rank(cases, python_weights, appetite)
        assert [(row["rank"], row["use_case_id"], row["score"], row["shortlisted"]) for row in result["result"]["ranked"]] == [
            (row["rank"], row["use_case_id"], row["score"], row["shortlisted"]) for row in ranked
        ]
        assert [(row["use_case_id"], row["status"]) for row in result["result"]["ineligible"]] == [
            (row["use_case_id"], row["status"]) for row in ineligible
        ]
