"""Static dashboard and report rendering tests."""

from __future__ import annotations

import json
import math
import re
import html
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from ai_value_chain.data import DATA_DIR, REPO_ROOT, load_controls, load_use_cases
from ai_value_chain.render import LABEL_LINE, PAGE_TEMPLATE, build
from ai_value_chain.scoring import rank


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.tables: list[list[list[str]]] = []
        self.current_table: list[list[str]] | None = None
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None
        self.hrefs: list[str] = []
        self.header_hrefs: list[str] = []
        self.footer_hrefs: list[str] = []
        self.circles: list[dict[str, str]] = []
        self.element_ids: list[str] = []
        self.script_count = 0
        self.row_classes: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "script":
            self.script_count += 1
        if tag == "a" and attr.get("href"):
            self.hrefs.append(attr["href"])
            ancestors = [name for name, _ in self.stack]
            if "header" in ancestors:
                self.header_hrefs.append(attr["href"])
            if "footer" in ancestors:
                self.footer_hrefs.append(attr["href"])
        if attr.get("id"):
            self.element_ids.append(attr["id"])
        if tag == "circle" and attr.get("data-id"):
            self.circles.append(attr)
        if tag == "table":
            self.current_table = []
        elif tag == "tr" and self.current_table is not None:
            self.current_row = []
            self.row_classes.append(attr.get("class", ""))
        elif tag in {"th", "td"} and self.current_row is not None:
            self.current_cell = []
        self.stack.append((tag, attr))

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self.current_cell is not None and self.current_row is not None:
            self.current_row.append("".join(self.current_cell).strip())
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None and self.current_table is not None:
            self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)


def _build(tmp_path: Path):
    html_path, markdown_path = build(tmp_path)
    page = html_path.read_bytes().decode("utf-8")
    report = markdown_path.read_bytes().decode("utf-8")
    parser = PageParser()
    parser.feed(page)
    return html_path, markdown_path, page, report, parser


def test_scenario_drives_header_and_report_and_general_insurance_terms_are_absent(tmp_path):
    _, _, page, report, _ = _build(tmp_path)
    scenario = json.loads((DATA_DIR / "scenario.json").read_text(encoding="utf-8-sig"))
    assert scenario["title"] in page and scenario["title"] in report
    assert f'{scenario["insurer"]} · {scenario["market"]} · {scenario["currency"]} · {", ".join(scenario["lines"])}' in report
    assert "Which AI use cases should a UK life and protection insurer take forward, and under what controls?" in page
    for output in (page, report):
        assert LABEL_LINE in output
        for banned in ("motor", "home", "commercial property", "general insurer"):
            assert banned not in output.casefold()


def test_dashboard_sections_and_kpis_are_in_required_order(tmp_path):
    _, _, page, report, _ = _build(tmp_path)
    ids = ("kpis", "context", "matrix", "heatmap", "scoring", "ranking", "not-eligible", "governance")
    positions = [page.index(f'id="{section}"') for section in ids]
    assert positions == sorted(positions)
    assert page.index('<header class="hero">') < positions[0]
    assert page.index("</header>") < page.index("<main id=\"top\">") < positions[0]
    assert page.index("<footer>") > positions[-1]
    diagram = REPO_ROOT / "docs" / "diagrams" / "value_chain.svg"
    if diagram.is_file():
        assert positions[1] < page.index('id="value-chain"') < positions[2]
    else:
        assert 'id="value-chain"' not in page
    for label, number in (("Use cases assessed", 14), ("Eligible", 11), ("Shortlisted", 5), ("Not eligible", 3)):
        assert f'<div class="kpi-main"><strong>{number}</strong><span class="kpi-label">{label}</span></div>' in page
    for caption in ("across 5 value-chain stages", "at Medium appetite · internal AI risk tier ≤ Medium", "top 5 by weighted score", "VC-02, VC-14 high · VC-03 unacceptable"):
        assert f'<span class="kpi-caption">{caption}</span>' in page
    assert "Use cases assessed: 14 · Eligible at Medium appetite: 11 · Shortlisted: 5 · Not eligible: 3" in report
    assert ".kpis{display:flex;align-items:stretch;box-sizing:border-box;width:100%;max-width:880px;margin:-40px 0 0;gap:12px" in page
    assert "margin:-40px auto" not in page
    assert '.kpi-label{display:block;font-size:13px;min-width:0;white-space:nowrap}' in page
    assert ".kpi{box-sizing:border-box;flex:1 1 0;min-width:0;" in page
    assert "@media(max-width:759px){.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}" in page
    assert "@media(max-width:419px){.kpis{grid-template-columns:1fr}}" in page
    assert '.kpi-main{display:flex;align-items:baseline;gap:8px;min-width:0}' in page
    strip_start = page.index('<section id="context" class="how-to-read"')
    assert page.rindex('<main id="top">', 0, strip_start) < strip_start
    assert len(re.findall(r'<article class="read-card">', page[strip_start:page.index('</section>', strip_start)])) == 3
    assert re.findall(r'<span class="step-badge">(\d)</span>', page) == ["1", "2", "3"]
    assert ".how-to-read{display:grid;box-sizing:border-box;width:100%;max-width:1200px;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:28px 0}" in page
    assert ".read-card{box-sizing:border-box;" in page
    assert "@media(max-width:759px){.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.how-to-read{grid-template-columns:1fr}.scroll{overflow-x:auto}}" in page
    assert f'{len(load_use_cases())} AI use cases across distribution, underwriting, policy admin, servicing and claims.' in page
    assert "Each must pass the insurer's internal AI risk tier – its own appetite measure, not a regulatory classification." in page
    assert "Eligible use cases are ranked by weighted score; two shortlisted ones carry worked controls and agent accountability." in page
    assert "Lines in scope" not in page and "currency:" not in page


def test_hero_contents_footer_sources_and_kpi_captions(tmp_path):
    _, _, page, _, parser = _build(tmp_path)
    scenario = json.loads((DATA_DIR / "scenario.json").read_text(encoding="utf-8-sig"))
    assert '<header class="hero">' in page
    assert f'<span class="hero-pill">{LABEL_LINE}</span>' in page
    assert f'<h1>{scenario["title"]}</h1>' in page
    assert "Which AI use cases should a UK life and protection insurer take forward, and under what controls?" in page
    expected_chips = (scenario["market"], scenario["currency"], *scenario["lines"])
    chips = re.search(r'<div class="hero-chips">(.*?)</div>', page).group(1)
    assert re.findall(r'<span class="hero-chip">(.*?)</span>', chips) == [html.escape(value) for value in expected_chips]
    assert '<a class="hero-button primary" href="#ranking">View ranking</a>' in page
    assert '<a class="hero-button outline" href="#governance">Worked governance</a>' in page
    assert not [href for href in parser.header_hrefs if "github.com" in href]
    prefix = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/"
    assert len(parser.footer_hrefs) == 5
    assert all(href.startswith(prefix) for href in parser.footer_hrefs)
    assert "Source data:" in page
    assert parser.element_ids.count("ranking") == 1
    assert parser.element_ids.count("governance") == 1
    assert all(parser.element_ids.count(target) == 1 for target in ("ranking", "governance"))
    for css_value in (
        ".hero{width:100%;padding:28px 0 60px",
        ".hero-pill{display:inline-block;font-size:11px;letter-spacing:.02em;padding:3px 10px",
        ".hero h1{font-size:30px;line-height:1.2;font-weight:700;margin:12px 0 6px}",
        "@media(max-width:759px){.hero h1{font-size:24px}}",
        ".hero-question{font-size:16px;line-height:1.4;opacity:.9;max-width:680px",
        ".hero-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}",
        ".hero-chip{display:inline-block;font-size:12px;padding:3px 9px",
        ".hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}",
        ".hero-button{display:inline-flex;align-items:center;justify-content:center;font-size:13px;padding:8px 14px;border-radius:6px",
        ".kpis{display:flex;align-items:stretch;box-sizing:border-box;width:100%;max-width:880px;margin:-40px 0 0;gap:12px",
        "border-top:3px solid var(--kpi-border,var(--border));border-radius:10px;padding:12px 16px",
        ".kpi-main{display:flex;align-items:baseline;gap:8px;min-width:0}",
        ".kpi strong{font-size:24px;font-weight:700",
        ".kpi-label{display:block;font-size:13px;min-width:0;white-space:nowrap}.kpi-caption{display:block;font-size:11px",
        "h2{font-size:20px;line-height:1.3;margin:36px 0 10px}h3{font-size:16px;",
        ".matrix-wrap{width:100%;max-width:600px;margin:0 auto}",
        ".heatmap-wrap{width:100%;max-width:520px;margin:0 auto}",
        ".matrix-legend{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:8px 16px;font-size:12px",
        ".diagram{display:block;width:100%;max-width:720px;height:auto;margin:0 auto}",
    ):
        assert css_value in page
    assert "linear-gradient(135deg,var(--hero-start) 0%,var(--hero-end) 100%)" in page
    assert "--hero-start:#0b4f5c;--hero-end:#0f766e" in page
    assert "--hero-start:#062f37;--hero-end:#0b4f5c" in page
    assert "margin:-40px 0 0" in page
    assert "box-shadow:0 6px 20px rgba(0,0,0,.08)" in page


def test_priority_matrix_has_14_unique_points_with_required_classes(tmp_path):
    _, _, page, _, parser = _build(tmp_path)
    ids = [circle["data-id"] for circle in parser.circles]
    assert all("id" not in circle for circle in parser.circles)
    assert len(ids) == 14
    assert len(set(ids)) == 14
    assert Counter("shortlisted-point" in circle["class"].split() for circle in parser.circles)[True] == 5
    assert Counter("eligible-point" in circle["class"].split() for circle in parser.circles)[True] == 6
    assert Counter("gated-point" in circle["class"].split() for circle in parser.circles)[True] == 3
    cases = {row["use_case_id"]: row for row in load_use_cases()}
    assert set(ids) == set(cases)
    for circle in parser.circles:
        assert float(circle["r"]) == 6 + 2.5 * cases[circle["data-id"]]["data_readiness"]
    assert 'Feasibility (1–5)' in page and 'Value (1–5)' in page
    matrix = page.split('data-chart="priority-matrix"', 1)[1].split("</svg>", 1)[0]
    assert 'viewBox="0 0 720 440"' in page
    assert '<text x="650" y="400" text-anchor="middle">5</text>' in matrix
    assert '<text x="55" y="44" text-anchor="end">5</text>' in matrix
    assert 'x1="70"' in matrix and 'x2="650"' in matrix
    circles = {
        use_case_id: (float(x), float(y), float(radius))
        for use_case_id, x, y, radius in re.findall(
            r'<circle class="(?:shortlisted-point|eligible-point|gated-point)" data-id="(VC-\d+)" cx="(-?\d+(?:\.\d+)?)" cy="(-?\d+(?:\.\d+)?)" r="(\d+(?:\.\d+)?)"/>',
            matrix,
        )
    }
    labels = {
        use_case_id: (float(x), float(y))
        for x, y, use_case_id in re.findall(
            r'<text class="matrix-label" x="(-?\d+(?:\.\d+)?)" y="(-?\d+(?:\.\d+)?)" text-anchor="middle">(VC-\d+)</text>',
            matrix,
        )
    }
    grouped = {}
    for use_case_id, case in cases.items():
        grouped.setdefault((case["feasibility"], case["value"]), []).append(use_case_id)
    for (feasibility, value), group in grouped.items():
        ordered = sorted(group)
        expected_offsets = {1: (0,), 2: (-22, 22), 3: (-22, 0, 22)}[len(ordered)]
        base_x = 70 + (feasibility - 1) * 145
        base_y = 380 - (value - 1) * 85
        for index, use_case_id in enumerate(ordered):
            circle_x, circle_y, radius = circles[use_case_id]
            assert circle_x == base_x + expected_offsets[index]
            assert circle_y == base_y
            label_x, label_y = labels[use_case_id]
            assert label_x == circle_x
            if index % 2 == 0:
                assert label_y < circle_y - radius
            else:
                assert label_y > circle_y + radius
    assert re.findall(r'<text x="\d+" y="400" text-anchor="middle">(\d)</text>', matrix) == list("12345")
    assert re.findall(r'<text x="55" y="\d+" text-anchor="end">(\d)</text>', matrix) == list("12345")
    label_points = list(labels.values())
    assert all(math.dist(a, b) >= 12 for index, a in enumerate(label_points) for b in label_points[index + 1:])
    assert "</svg></div><div class=\"matrix-legend\"" in page
    assert "Not eligible – risk gate" in page
    assert "Bubble size = data readiness. Dashed = blocked by the internal AI risk gate at appetite." in page
    assert ".chart .matrix-label{font-size:11px}" in page
    assert ".matrix-legend{display:flex" in page and "font-size:12px" in page


def test_risk_heatmap_counts_match_data_and_sum_to_14(tmp_path):
    _, _, page, _, _ = _build(tmp_path)
    heatmap = page.split('data-chart="risk-heatmap"', 1)[1].split("</svg>", 1)[0]
    cells = re.findall(
        r'<rect class="heat-cell heat-(low|medium|high|unacceptable) heat-c(\d)"[^>]*/><text class="heat-count [^"]+ heat-c(\d)"[^>]*>(\d+)</text>',
        heatmap,
    )
    actual = [int(count) for _, _, _, count in cells]
    cases = load_use_cases()
    stages = ("distribution", "underwriting", "policy_admin", "servicing", "claims")
    tiers = ("low", "medium", "high", "unacceptable")
    expected = [sum(row["value_chain_stage"] == stage and row["risk_tier"] == tier for row in cases) for stage in stages for tier in tiers]
    assert actual == expected
    assert sum(actual) == 14
    assert [(tier, int(cell_class), int(text_class)) for tier, cell_class, text_class, _ in cells] == [
        (tier, min(count, 3), min(count, 3))
        for stage in stages for tier in tiers
        for count in [sum(row["value_chain_stage"] == stage and row["risk_tier"] == tier for row in cases)]
    ]
    assert "Unacceptable</text><text class=\"heat-header heat-text-unacceptable\"" in heatmap
    assert "· never eligible</text>" in heatmap
    assert "Appetite: Medium" in page
    assert 'viewBox="0 0 640 360"' in page
    assert page.count('class="heat-cell heat-') == 20
    assert page.count('width="120" height="52"') == 20
    assert 'heat-header heat-text-low' in heatmap and 'heat-header heat-text-unacceptable' in heatmap
    for rule in (".heat-c0{fill:var(--heat-neutral);fill-opacity:1}", ".heat-c1{fill:var(--heat-tier);fill-opacity:.35}", ".heat-c2{fill:var(--heat-tier);fill-opacity:.6}", ".heat-c3{fill:var(--heat-tier);fill-opacity:.85}"):
        assert rule in page
    assert "--heat-neutral:#f1f5f9" in page
    assert ".chart .heat-count.heat-c3{fill:#fff" in page
    assert ".chart .appetite-label{font-size:12px" in page


def test_ranked_table_matches_independent_snapshot_and_shortlist(tmp_path):
    _, _, _, _, parser = _build(tmp_path)
    ranked, ineligible = rank(load_use_cases(), {"value": 5, "feasibility": 3, "data_readiness": 2}, "medium")
    expected = [
        ("VC-01", "76.0"), ("VC-09", "76.0"), ("VC-13", "72.0"), ("VC-05", "70.0"),
        ("VC-11", "70.0"), ("VC-07", "66.0"), ("VC-06", "66.0"), ("VC-10", "64.0"),
        ("VC-12", "60.0"), ("VC-04", "60.0"), ("VC-08", "56.0"),
    ]
    ranking = parser.tables[0]
    assert [(row[1], row[9]) for row in ranking[1:]] == expected
    assert [row["use_case_id"] for row in ranked] == [use_case_id for use_case_id, _ in expected]
    assert len(ineligible) == 3
    assert [row[0] for row in parser.tables[1][1:]] == ["VC-02", "VC-03", "VC-14"]


def test_favicon_tags_exact_github_links_resolve_and_no_external_urls(tmp_path):
    _, _, page, _, parser = _build(tmp_path)
    favicon = '<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">'
    assert favicon in PAGE_TEMPLATE
    assert page.count(favicon) == 1
    prefix = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/"
    github = [href for href in parser.hrefs if "github.com" in href]
    assert github
    for href in github:
        assert href.startswith(prefix)
        relative_path = href[len(prefix):].split("#", 1)[0].split("?", 1)[0]
        assert (REPO_ROOT / relative_path).is_file()
    urls = re.findall(r"https?://[^\s\"'<>)]*", page)
    assert all(url.startswith(prefix) for url in urls)
    assert parser.script_count == 3


def test_tables_are_scroll_wrapped_and_css_supports_required_layout_and_dark_mode(tmp_path):
    _, _, page, _, parser = _build(tmp_path)
    assert parser.tables
    assert page.count("<div class=\"scroll\">") == len(parser.tables)
    assert "white-space:nowrap" in page
    assert "min-width:980px" not in page
    assert "table-layout:fixed" in page
    assert "max-width:1200px" in page
    assert "max-width:720px" in page
    assert "max-width:520px" in page
    assert "max-width:600px" in page
    assert "max-width:720px" in page
    assert "prefers-color-scheme:dark" in page
    assert "overflow-wrap:break-word" in page
    assert "overflow-wrap:anywhere" not in page
    assert "@media(max-width:759px){.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.how-to-read{grid-template-columns:1fr}.scroll{overflow-x:auto}}" in page
    assert re.search(r"\.scroll\{[^}]*overflow-x:visible", page)
    table_specs = re.findall(r'<table class="([^"]+)"><colgroup>(.*?)</colgroup>', page)
    assert len(table_specs) == len(parser.tables) == 6
    widths = [[int(value) for value in re.findall(r'width:(\d+)%', cols)] for _, cols in table_specs]
    assert widths == [
        [6, 7, 25, 9, 11, 6, 7, 7, 9, 5, 8],
        [8, 32, 16, 20, 24],
        [12, 36, 13, 16, 15, 8],
        [10, 9, 31, 16, 22, 12],
        [12, 36, 13, 16, 15, 8],
        [10, 9, 31, 16, 22, 12],
    ]
    assert sum(widths[2]) == 100
    assert '.result-detail{display:block;white-space:normal;overflow-wrap:break-word;font-size:12px;margin-top:6px;line-height:1.4}' in page
    css = page.split("<style>", 1)[1].split("</style>", 1)[0]
    nowrap_rules = [selector.strip() for rule in css.split("}") if "white-space:nowrap" in rule for selector in rule.split("{", 1)[0].split(",")]
    assert all('td' not in selector or selector.strip() in {'td.id-cell', 'td.num'} for selector in nowrap_rules)
    for descriptive_class in ('.wrap', '.control-description', '.evidence-description', '.result-detail'):
        assert not any(descriptive_class in selector for selector in nowrap_rules)


def test_visual_tables_use_combined_controls_and_agent_chips(tmp_path):
    _, _, page, _, parser = _build(tmp_path)
    control_tables = [table for table in parser.tables if table[0] and table[0][0] == "Control"]
    accountability_tables = [table for table in parser.tables if table[0] and table[0][0] == "Action"]
    assert len(control_tables) == len(accountability_tables) == 2
    for table in control_tables:
        assert table[0] == ["Control", "Requirement and control", "Owner", "Evidence", "Result", "Review"]
        assert all(len(row) == 6 for row in table)
    for table in accountability_tables:
        assert table[0] == ["Action", "Agent allowed", "Tool permissions", "Accountable role", "Escalation path", "Log field"]
        assert all(len(row) == 6 for row in table)
    assert ".control-requirement{font-size:14px}" in page
    assert ".control-description{font-size:13px" in page
    assert ".log-field" in page and "word-break:break-all" in page
    assert ".tier-low" in page and ".tier-medium" in page and ".tier-high" in page and ".tier-unacceptable" in page
    assert ".result-pass" in page and ".result-fail" in page and ".result-not-tested" in page
    assert ".agent-yes" in page and ".agent-no" in page
    assert ".status-shortlisted" in page and ".status-eligible" in page and ".status-not-eligible" in page
    for color in ("#1b5e20", "#e8f5e9", "#7a4a00", "#fff3d6", "#b71c1c", "#fdeaea", "#7f1d1d", "#475569", "#eef2f6"):
        assert color in page
    dark = page.split("@media(prefers-color-scheme:dark){:root{", 1)[1].split("}}", 1)[0]
    for variable in ("--tier-low-bg:#173c29", "--tier-medium-bg:#4a3d17", "--tier-high-bg:#4a2226", "--tier-unacceptable-bg:#450a0a", "--pass-bg:#173c29", "--fail-bg:#4a2226", "--not-tested-bg:#26313d", "--agent-yes-bg:#123d40", "--agent-no-bg:#26313d", "--shortlisted-bg:#54abc2"):
        assert variable in dark


def test_worked_cards_have_two_use_cases_four_stat_chips_and_governance_tables(tmp_path):
    _, _, page, report, parser = _build(tmp_path)
    cases = [row for row in load_use_cases() if row["worked_governance"]]
    assert [case["use_case_id"] for case in cases] == ["VC-01", "VC-05"]
    assert 'href="#VC-01"' in page and 'href="#VC-05"' in page
    controls = load_controls()
    for case in cases:
        assert f'id="{case["use_case_id"]}"' in page
        rows = [row for row in controls if row["use_case_id"] == case["use_case_id"]]
        counts = Counter(row["test_result"] for row in rows)
        exceptions = sum(bool(row.get("exception_id")) for row in rows)
        for expected in (f'Pass: <strong>{counts["pass"]}</strong>', f'Fail: <strong>{counts["fail"]}</strong>', f'Not tested: <strong>{counts["not tested"]}</strong>', f'Exceptions: <strong>{exceptions}</strong>'):
            assert expected in page
        assert f"Pass: {counts['pass']} · Fail: {counts['fail']} · Not tested: {counts['not tested']} · Exceptions: {exceptions}" in report
    assert len([table for table in parser.tables if table[0][0] == "Control"]) == 2
    assert len([table for table in parser.tables if table[0][0] == "Action"]) == 2


def test_build_outputs_are_deterministic_utf8_and_markdown_has_stage_tier_table(tmp_path):
    html_path, markdown_path, _, report, _ = _build(tmp_path)
    diagram_path = tmp_path / "diagrams" / "value_chain.mmd"
    first = (html_path.read_bytes(), markdown_path.read_bytes(), diagram_path.read_bytes())
    assert all(not content.startswith(b"\xef\xbb\xbf") and b"\r\n" not in content for content in first)
    build(tmp_path)
    assert first == (html_path.read_bytes(), markdown_path.read_bytes(), diagram_path.read_bytes())
    assert "## Stage × internal risk tier counts" in report
    assert "| Stage | Low | Medium | High | Unacceptable |" in report
    assert not re.search(r"</?[A-Za-z][^>]*>", report)
    diagram = (tmp_path / "diagrams" / "value_chain.mmd").read_text(encoding="utf-8")
    assert "&lt;" not in diagram and "&gt;" not in diagram and "&amp;" not in diagram
    assert "S1[\"Distribution<br/>2 use cases\"]" in diagram
    assert "S2[\"Underwriting<br/>4 use cases\"]" in diagram
    assert "S3[\"Policy admin<br/>4 use cases\"]" in diagram
    assert "S4[\"Servicing<br/>2 use cases\"]" in diagram
    assert "S5[\"Claims<br/>2 use cases\"]" in diagram
    assert 'GATE{{"Internal AI risk gate<br/>appetite: Medium"}}' in diagram
    assert 'SL["Ranked shortlist<br/>top 5 of 11 eligible"]' in diagram
    assert 'NE["Not eligible (3)<br/>VC-02, VC-14 · high<br/>VC-03 · unacceptable"]' in diagram
    assert 'GOV["Worked governance<br/>VC-01 Underwriting Evidence Summariser<br/>VC-05 Policy-Admin Data Exception Agent"]' in diagram
    assert 'CT["Controls trace<br/>24 controls"]' in diagram
    assert 'AA["Agent accountability<br/>10 actions"]' in diagram
    assert "classDef gate fill:#fff3d6,stroke:#b26a00;" in diagram
    assert "classDef ne fill:#fdeaea,stroke:#b71c1c,stroke-dasharray:4 3;" in diagram
    assert "classDef sl fill:#e0f2f1,stroke:#00695c;" in diagram
    assert "classDef gov fill:#ffffff,stroke:#00695c" in diagram
    assert '<img class="diagram"' in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert ".diagram{display:block;width:100%;max-width:720px;height:auto;margin:0 auto}" in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_page_ids_are_unique_and_worked_cards_are_the_only_vc_ids(tmp_path):
    _, _, _, _, parser = _build(tmp_path)
    assert len(parser.element_ids) == len(set(parser.element_ids))
    assert parser.element_ids.count("VC-01") == 1
    assert parser.element_ids.count("VC-05") == 1
