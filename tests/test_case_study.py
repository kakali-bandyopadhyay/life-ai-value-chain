"""Generated static case-study page checks."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from ai_value_chain.data import REPO_ROOT, load_actions, load_controls, load_use_cases
from ai_value_chain.render import build
from ai_value_chain.scoring import rank


class CaseStudyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: list[str] = []
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def _build(tmp_path: Path):
    dashboard, _ = build(tmp_path)
    case_path = tmp_path / "case-study" / "index.html"
    assert case_path.is_file()
    page = case_path.read_bytes().decode("utf-8")
    dashboard_page = dashboard.read_text(encoding="utf-8")
    parser = CaseStudyParser()
    parser.feed(page)
    return case_path, page, dashboard_page, parser


def test_case_study_hero_styles_and_static_page(tmp_path):
    _, page, _, parser = _build(tmp_path)
    favicon = '<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">'
    assert page.count(favicon) == 1
    assert '<span class="hero-pill">Case study · simulated scenario · synthetic data · illustrative, not legal advice</span>' in page
    assert "<h1>Life and protection AI: which use cases go forward, under what controls</h1>" in page
    assert "Which AI use cases should a UK life and protection insurer take forward, and under what controls?" in page
    assert '<a class="hero-button primary" href="../">Open the live dashboard</a>' in page
    assert '<a class="hero-button outline" href="https://github.com/kakali-bandyopadhyay/life-ai-value-chain">Code</a>' in page
    chips = re.search(r'<div class="hero-chips">(.*?)</div>', page).group(1)
    assert re.findall(r'<span class="hero-chip">(.*?)</span>', chips) == [
        "UK", "GBP", "Individual life", "Group life &amp; disability", "Income protection", "Annuities"
    ]
    assert "<script" not in page.casefold()
    assert ".case-study-hero{padding:24px 0 32px}" in page
    assert "max-width:820px;margin:0 auto" in page
    assert "body{font-size:15px;line-height:1.6}" in page
    assert ".article-main h2{font-size:20px}.article-main h3{font-size:16px}" in page
    assert "prefers-color-scheme:dark" in page
    assert parser.ids.count("VC-01") == 0
    assert page.index('id="problem"') < page.index('id="approach"') < page.index('id="gate"') < page.index('id="worked-agents"') < page.index('id="real-and-simulated"') < page.index('id="limits"')


def test_problem_approach_and_computed_gate_table(tmp_path):
    _, page, _, parser = _build(tmp_path)
    config = json.loads((REPO_ROOT / "data" / "scoring_config.json").read_text(encoding="utf-8"))
    cases = load_use_cases()
    medium, medium_ineligible = rank(cases, config["default_weights"], "medium")
    high, _ = rank(cases, config["default_weights"], "high")
    grouped = []
    high_ids = sorted(row["use_case_id"] for row in medium_ineligible if row["risk_tier"] == "high")
    unacceptable_ids = sorted(row["use_case_id"] for row in medium_ineligible if row["risk_tier"] == "unacceptable")
    if high_ids:
        grouped.append(f'{", ".join(high_ids)} high')
    if unacceptable_ids:
        grouped.append(f'{", ".join(unacceptable_ids)} unacceptable')
    expected = (
        f'At Medium appetite, {len(medium)} of {len(cases)} use cases are eligible. '
        f'The gate removes {len(medium_ineligible)}: {"; ".join(grouped)}. '
        f'At High appetite the top-ranked use case would be {high[0]["use_case_id"]} ({high[0]["score"]:.1f}); '
        "at Medium it is not eligible, so no weighting can bring it back."
    )
    assert expected in page
    assert [(row["use_case_id"], row["risk_tier"]) for row in medium_ineligible] == [
        ("VC-02", "high"), ("VC-03", "unacceptable"), ("VC-14", "high")
    ]
    assert [(row["use_case_id"], row["score"]) for row in high[:1]] == [("VC-02", 90.0)]
    assert medium[0]["use_case_id"] == "VC-01"
    table_position = page.index('<table class="gate-table">')
    gate_part = page[page.index('id="gate"'):page.index('id="worked-agents"')]
    assert '<div class="scroll"><table class="gate-table">' in gate_part
    assert all(case_id in gate_part for case_id in ("VC-02", "VC-03", "VC-14", "VC-01"))
    assert "Ranked #1 at Medium" in gate_part
    assert "Automated Underwriting Acceptance with Premium Loadings" in gate_part
    assert "Not eligible at any appetite" in gate_part
    assert "<img class=\"diagram\" src=\"../diagrams/value_chain.svg\"" in page
    assert "<strong>Assess</strong>" in page and "<strong>Gate</strong>" in page and "<strong>Prioritise and govern</strong>" in page
    assert table_position > page.index('id="gate"')
    assert len(parser.tables) == 1


def test_worked_agent_permissions_and_open_findings_match_source_data(tmp_path):
    _, page, _, _ = _build(tmp_path)
    cases = sorted((row for row in load_use_cases() if row["worked_governance"]), key=lambda row: row["use_case_id"])
    controls = load_controls()
    actions = load_actions()
    assert [case["use_case_id"] for case in cases] == ["VC-01", "VC-05"]
    for case in cases:
        use_case_id = case["use_case_id"]
        start = page.index(f'<article class="case-study-card" id="worked-{use_case_id}">')
        end = page.index("</article>", start)
        card = page[start:end]
        assert html.escape(case["description"]) in card
        permission_lists = re.findall(r'<ul class="permission-list">(.*?)</ul>', card, flags=re.S)
        assert len(permission_lists) == 2
        case_actions = [row for row in actions if row["use_case_id"] == use_case_id]
        for listing, allowed in zip(permission_lists, (True, False)):
            expected_actions = [row for row in case_actions if (row["agent_allowed"] == "yes") is allowed]
            assert len(re.findall(r"<li>", listing)) == len(expected_actions)
            for action in expected_actions:
                assert html.escape(action["action"].title()) in listing
                assert html.escape(action["tool_permissions"]) in listing
                assert html.escape(action["accountable_human_role"]) in listing
        case_controls = [row for row in controls if row["use_case_id"] == use_case_id]
        for control in case_controls:
            if control["test_result"] == "fail":
                assert html.escape(control["control_id"]) in card
                assert html.escape(control["requirement"]) in card
                assert html.escape(control["remediation_note"]) in card
            if control.get("exception_id"):
                assert html.escape(control["exception_id"]) in card
                assert html.escape(control["exception_reason"]) in card
        assert f'href="../#{use_case_id}"' in card
        assert "Pass:" in card and "Fail:" in card and "Not tested:" in card and "Exceptions:" in card


def test_links_tables_boundaries_and_dashboard_button(tmp_path):
    _, page, dashboard, parser = _build(tmp_path)
    github_prefix = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain"
    github_hrefs = [href for href in parser.hrefs if "github.com" in href]
    assert len(github_hrefs) == 6
    for href in github_hrefs:
        assert href.startswith(github_prefix)
        route = urlparse(href).path
        if "/blob/main/" in route:
            relative = route.split("/blob/main/", 1)[1]
            assert (REPO_ROOT / relative).is_file()
        else:
            assert route == "/kakali-bandyopadhyay/life-ai-value-chain"
    assert '<a class="hero-button outline" href="case-study/">Read the case study</a>' in dashboard
    assert dashboard.index("Worked governance</a>") < dashboard.index("Read the case study</a>")
    assert (REPO_ROOT / "docs" / "index.html").is_file()
    assert (REPO_ROOT / "docs" / "diagrams" / "value_chain.svg").is_file()
    dashboard_ids = set(re.findall(r'\bid="([^"]+)"', dashboard))
    assert {"VC-01", "VC-05"}.issubset(dashboard_ids)
    assert "../" in parser.hrefs
    assert "../#VC-01" in parser.hrefs and "../#VC-05" in parser.hrefs
    assert "../diagrams/value_chain.svg" in page
    assert '<p>MIT licence</p>' in page
    visible_text = html.unescape(re.sub(r"<[^>]+>", " ", page)).casefold()
    for banned in ("fca", "pra", "solvency ii", "consumer duty", "gdpr", "ico"):
        assert not re.search(rf"\b{re.escape(banned)}\b", visible_text)
    assert "no law or regulator is interpreted" in visible_text

    table_specs = re.findall(r'<div class="scroll"><table class="[^"]+"><colgroup>(.*?)</colgroup>', page, flags=re.S)
    assert len(table_specs) == len(parser.tables) == 1
    for colgroup in table_specs:
        widths = [int(value) for value in re.findall(r'width:(\d+)%', colgroup)]
        assert sum(widths) == 100
    assert "table-layout:fixed" in page


def test_case_study_and_dashboard_builds_are_deterministic_utf8_lf(tmp_path):
    dashboard, report = build(tmp_path)
    case_study = tmp_path / "case-study" / "index.html"
    paths = (dashboard, report, case_study, tmp_path / "diagrams" / "value_chain.mmd")
    first = tuple(path.read_bytes() for path in paths)
    assert all(not content.startswith(b"\xef\xbb\xbf") and b"\r\n" not in content for content in first)
    build(tmp_path)
    assert first == tuple(path.read_bytes() for path in paths)

