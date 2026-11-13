"""Build the deterministic static dashboard and Markdown assessment report."""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .data import DATA_DIR, REPO_ROOT, load_actions, load_controls, load_use_cases, validate
from .scoring import rank


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<title>{title}</title>
{styles}
</head>
<body>
{content}
{data_script}
<script src="rank.js" defer></script><script src="app.js" defer></script>
</body>
</html>
"""

GITHUB_BLOB = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/"
STAGES = ("distribution", "underwriting", "policy_admin", "servicing", "claims")
STAGE_LABELS = {"distribution": "Distribution", "underwriting": "Underwriting", "policy_admin": "Policy admin", "servicing": "Servicing", "claims": "Claims"}
RISK_TIERS = ("low", "medium", "high", "unacceptable")
RISK_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "unacceptable": "Unacceptable"}
LABEL_LINE = "Simulated scenario · synthetic data · illustrative, not legal advice"
BOUNDARY = (
    "Synthetic and illustrative. The internal AI risk tier is not a regulatory classification. "
    "This material needs Legal/Compliance validation, is not production-ready, and is not any firm's policy."
)


def _load_config() -> dict[str, Any]:
    return json.loads((DATA_DIR / "scoring_config.json").read_text(encoding="utf-8"))


def _load_scenario() -> dict[str, Any]:
    return json.loads((DATA_DIR / "scenario.json").read_text(encoding="utf-8-sig"))


def _esc(value: Any) -> str:
    return html.escape(str(value) if value not in (None, "") else "–", quote=True)


def _repo_url(path: str) -> str:
    return GITHUB_BLOB + path


def _links() -> list[tuple[str, str]]:
    return [
        ("Use case data", "data/use_cases.json"),
        ("Scoring configuration", "data/scoring_config.json"),
        ("Scoring reference", "ai_value_chain/scoring.py"),
        ("Controls trace", "data/controls_trace.json"),
        ("Agent accountability", "data/agent_accountability.json"),
    ]


def _ranked_data() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = _load_config()
    scenario = _load_scenario()
    cases = load_use_cases()
    ranked, ineligible = rank(cases, config["default_weights"], config["default_max_risk"])
    return config, scenario, cases, ranked, ineligible


def _mermaid_text(value: str) -> str:
    return value.replace("&", "#amp;").replace('"', "#quot;").replace("\n", " ")


def _diagram_source() -> str:
    """Create a deterministic Mermaid summary from the supplied assessment data."""
    config, scenario, cases, ranked, ineligible = _ranked_data()
    appetite = RISK_LABELS[config["default_max_risk"]]
    stage_counts = Counter(row["value_chain_stage"] for row in cases)
    worked = sorted((row for row in cases if row["worked_governance"]), key=lambda row: row["use_case_id"])
    high_ids = sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "high")
    unacceptable_ids = sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "unacceptable")
    not_eligible_lines = [f'{", ".join(high_ids)} · high'] if high_ids else []
    not_eligible_lines.extend(f"{use_case_id} · unacceptable" for use_case_id in unacceptable_ids)
    worked_lines = [f'{row["use_case_id"]} {_mermaid_text(row["name"])}' for row in worked]
    controls_count = len(load_controls())
    actions_count = len(load_actions())
    stages = (
        ("S1", "distribution"),
        ("S2", "underwriting"),
        ("S3", "policy_admin"),
        ("S4", "servicing"),
        ("S5", "claims"),
    )
    lines = [
        '%%{init: {"flowchart": {"nodeSpacing": 24, "rankSpacing": 36, "curve": "basis"}, "themeVariables": {"fontSize": "14px"}}}%%',
        "flowchart LR",
        '  subgraph VC["Value chain"]',
        "    direction TB",
    ]
    for node_id, stage in stages:
        lines.append(f'    {node_id}["{STAGE_LABELS[stage]}<br/>{stage_counts[stage]} use cases"]')
    lines.extend([
        "    S1 ~~~ S2 ~~~ S3 ~~~ S4 ~~~ S5",
        "  end",
        f'  VC --> GATE{{{{"Internal AI risk gate<br/>appetite: {appetite}"}}}}',
        f'  GATE --> SL["Ranked shortlist<br/>top {config["shortlist_size"]} of {len(ranked)} eligible"]',
        f'  GATE -.-> NE["Not eligible ({len(ineligible)})<br/>{"<br/>".join(not_eligible_lines)}"]',
        f'  SL --> GOV["Worked governance<br/>{"<br/>".join(worked_lines)}"]',
        f'  GOV --> CT["Controls trace<br/>{controls_count} controls"]',
        f'  GOV --> AA["Agent accountability<br/>{actions_count} actions"]',
        "  classDef gate fill:#fff3d6,stroke:#b26a00;",
        "  classDef ne fill:#fdeaea,stroke:#b71c1c,stroke-dasharray:4 3;",
        "  classDef sl fill:#e0f2f1,stroke:#00695c;",
        "  classDef gov fill:#ffffff,stroke:#00695c",
        "  class GATE gate; class NE ne; class SL sl; class GOV,CT,AA gov",
    ])
    return "\n".join(lines) + "\n"


def _column_class(header: str) -> str:
    label = header.casefold()
    if label in {"rank", "value", "feasibility", "data readiness", "score"}:
        return "num"
    if label == "id":
        return "id-cell"
    if label == "review":
        return "date"
    return "wrap"


def _html_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    widths: tuple[int, ...],
    classes: str = "",
    row_classes: list[str] | None = None,
    header_labels: tuple[str, ...] | None = None,
    row_ids: list[str] | None = None,
) -> str:
    if len(headers) != len(widths) or sum(widths) != 100:
        raise ValueError("Table column widths must match the headers and total 100%")
    labels = header_labels or tuple(_esc(header) for header in headers)
    head = "".join(f'<th scope="col" class="{_column_class(header)}">{labels[index]}</th>' for index, header in enumerate(headers))
    colgroup = "".join(f'<col style="width:{width}%">' for width in widths)
    body = []
    for index, row in enumerate(rows):
        cells = "".join(f'<td class="{_column_class(headers[col])}">{cell}</td>' for col, cell in enumerate(row))
        extra = f' class="{row_classes[index]}"' if row_classes and row_classes[index] else ""
        use_case = f' data-use-case-id="{_esc(row_ids[index])}"' if row_ids else ""
        body.append(f"<tr{extra}{use_case}>{cells}</tr>")
    return f'<div class="scroll"><table class="{classes}"><colgroup>{colgroup}</colgroup><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _controls_for(use_case_id: str, controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((row for row in controls if row["use_case_id"] == use_case_id), key=lambda row: row["control_id"])


def _actions_for(use_case_id: str, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {name: index for index, name in enumerate(("recommend", "approve", "execute", "override", "stop"))}
    return sorted((row for row in actions if row["use_case_id"] == use_case_id), key=lambda row: order[row["action"]])


def _evidence_html(row: dict[str, Any]) -> str:
    reference = row["evidence_ref"]
    description = _esc(row.get("evidence_description"))
    if reference.startswith("https://"):
        source = f'<a href="{_esc(reference)}">Design record</a>'
    else:
        chip = "Simulated evidence" if reference == "simulated" else "No evidence – exception"
        source = f'<span class="chip muted">{chip}</span>'
    return f'<div class="evidence-ref">{source}</div><small class="evidence-description">{description}</small>'


def _result_html(result: str) -> str:
    return f'<span class="chip result result-{_esc(result).replace(" ", "-")}">{_esc(result)}</span>'


def _risk_html(tier: str) -> str:
    return f'<span class="chip tier tier-{_esc(tier)}">{_esc(RISK_LABELS[tier])}</span>'


def _agent_allowed_html(value: str) -> str:
    return f'<span class="chip agent agent-{_esc(value)}">{_esc(value.title())}</span>'


def _status_html(label: str, kind: str) -> str:
    return f'<span class="chip status status-{kind}">{_esc(label)}</span>'


def _exception_text(row: dict[str, Any]) -> str:
    if row.get("exception_id"):
        reason = f" — {_esc(row['exception_reason'])}" if row.get("exception_reason") else ""
        return _esc(row["exception_id"]) + reason
    return _esc(row.get("remediation_note") or "–")


def _exception_detail_html(row: dict[str, Any]) -> str:
    if row.get("exception_id") or row.get("remediation_note"):
        return f'<small class="result-detail">{_exception_text(row)}</small>'
    return ""


def _stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["test_result"] for row in rows)
    return {"pass": counts["pass"], "fail": counts["fail"], "not tested": counts["not tested"], "exceptions": sum(bool(row.get("exception_id")) for row in rows)}


def _stats_html(rows: list[dict[str, Any]]) -> str:
    counts = _stats(rows)
    return '<div class="stats">' + "".join(
        f'<span class="chip stat">{label}: <strong>{counts[key]}</strong></span>'
        for key, label in (("pass", "Pass"), ("fail", "Fail"), ("not tested", "Not tested"), ("exceptions", "Exceptions"))
    ) + "</div>"


def _css() -> str:
    return """<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#202631;--muted:#657080;--surface:#f4f6f8;--border:#d3d9e0;--link:#1456a0;--accent:#087e8b;--matrix-eligible:#cfe8ef;--grid:#d3d9e0;--chip-bg:#e7ebef;--chip-fg:#3d4752;--tier-low-fg:#1b5e20;--tier-low-bg:#e8f5e9;--tier-medium-fg:#7a4a00;--tier-medium-bg:#fff3d6;--tier-high-fg:#b71c1c;--tier-high-bg:#fdeaea;--tier-unacceptable-fg:#fff;--tier-unacceptable-bg:#7f1d1d;--pass-fg:#14532d;--pass-bg:#dff3e5;--fail-fg:#8b1e1e;--fail-bg:#fbe2e2;--not-tested-fg:#475569;--not-tested-bg:#eef2f6;--agent-yes-fg:#075e63;--agent-yes-bg:#d9f2f0;--agent-no-fg:#475569;--agent-no-bg:#eef2f6;--shortlisted-fg:#fff;--shortlisted-bg:#087e8b;--eligible-fg:#087e8b;--eligible-bg:transparent;--not-eligible-fg:#b71c1c;--not-eligible-bg:transparent;--heat-neutral:#f1f5f9;--heat-count-outline:#334155;--heat-low:#e8f5e9;--heat-medium:#fff3d6;--heat-high:#fdeaea;--heat-unacceptable:#7f1d1d;--gated-stroke:#b71c1c}
:root{--hero-start:#0b4f5c;--hero-end:#0f766e;--kpi-assessed:#94a3b8;--kpi-eligible:#14b8a6;--kpi-shortlisted:#0f766e;--kpi-ineligible:#b71c1c}
@media(prefers-color-scheme:dark){:root{--bg:#111820;--fg:#e7edf3;--muted:#a6b1bd;--surface:#1b2530;--border:#354352;--link:#8ab4f8;--accent:#27a9b5;--matrix-eligible:#24444d;--grid:#354352;--chip-bg:#26313d;--chip-fg:#d5dde5;--tier-low-fg:#a7d8ad;--tier-low-bg:#173c29;--tier-medium-fg:#f1d28a;--tier-medium-bg:#4a3d17;--tier-high-fg:#f1a3a3;--tier-high-bg:#4a2226;--tier-unacceptable-fg:#fff;--tier-unacceptable-bg:#450a0a;--pass-fg:#a7d8ad;--pass-bg:#173c29;--fail-fg:#f1a3a3;--fail-bg:#4a2226;--not-tested-fg:#cbd5e1;--not-tested-bg:#26313d;--agent-yes-fg:#8dddd5;--agent-yes-bg:#123d40;--agent-no-fg:#cbd5e1;--agent-no-bg:#26313d;--shortlisted-fg:#062f37;--shortlisted-bg:#54abc2;--eligible-fg:#54c4ca;--eligible-bg:transparent;--not-eligible-fg:#f1a3a3;--not-eligible-bg:transparent;--heat-neutral:#26313d;--heat-count-outline:#0f172a;--heat-low:#173c29;--heat-medium:#4a3d17;--heat-high:#4a2226;--heat-unacceptable:#450a0a;--gated-stroke:#f1a3a3;--hero-start:#062f37;--hero-end:#0b4f5c}}
*{box-sizing:border-box}html,body{margin:0;width:100%;max-width:100%;background:var(--bg);color:var(--fg)}body{font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{width:100%;max-width:1200px;margin:0 auto;padding:0 16px 36px}.hero{width:100%;padding:28px 0 60px;background:linear-gradient(135deg,var(--hero-start) 0%,var(--hero-end) 100%);color:#fff}.hero-inner{width:100%;max-width:1200px;margin:0 auto;padding:0 16px}.hero-pill{display:inline-block;font-size:11px;letter-spacing:.02em;padding:3px 10px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35)}.hero h1{font-size:30px;line-height:1.2;font-weight:700;margin:12px 0 6px}.hero-question{font-size:16px;line-height:1.4;opacity:.9;max-width:680px;margin:0}.hero-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.hero-chip{display:inline-block;font-size:12px;padding:3px 9px;border-radius:999px;background:rgba(255,255,255,.12);white-space:nowrap}.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.hero-button{display:inline-flex;align-items:center;justify-content:center;font-size:13px;padding:8px 14px;border-radius:6px;font-weight:600;text-decoration:none}.hero-button.primary{background:#fff;color:#0b4f5c}.hero-button.outline{background:transparent;border:1px solid #fff;color:#fff}h1{font-size:28px;line-height:1.25;margin:24px 0 8px}h2{font-size:20px;line-height:1.3;margin:36px 0 10px}h3{font-size:16px;line-height:1.35;margin:0}h4{font-size:16px;margin:18px 0 6px}p{margin:8px 0 12px}a{color:var(--link);overflow-wrap:break-word}.topline{font-weight:650}.scenario-line{font-weight:600}.site-links{display:flex;flex-wrap:wrap;gap:6px 16px;margin:12px 0 20px}.context p{margin:4px 0}.how-to-read{display:grid;box-sizing:border-box;width:100%;max-width:1200px;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:28px 0}.read-card{box-sizing:border-box;min-width:0;padding:12px 14px;border-left:3px solid #0f766e;background:var(--surface);border-radius:8px;font-size:13px;line-height:1.45}.read-card-heading{display:flex;align-items:center;gap:8px}.step-badge{display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;width:22px;height:22px;flex:0 0 22px;border-radius:50%;background:#0f766e;color:#fff;font-size:12px;font-weight:700}.read-card-heading strong{font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}.read-card p{margin:8px 0 0}.kpis{display:flex;align-items:stretch;box-sizing:border-box;width:100%;max-width:880px;margin:-40px 0 0;gap:12px;position:relative;z-index:1}.kpi{box-sizing:border-box;flex:1 1 0;min-width:0;background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--kpi-border,var(--border));border-radius:10px;padding:12px 16px;box-shadow:0 6px 20px rgba(0,0,0,.08)}.kpi-assessed{--kpi-border:var(--kpi-assessed)}.kpi-eligible{--kpi-border:var(--kpi-eligible)}.kpi-shortlisted{--kpi-border:var(--kpi-shortlisted)}.kpi-ineligible{--kpi-border:var(--kpi-ineligible)}.kpi-main{display:flex;align-items:baseline;gap:8px;min-width:0}.kpi strong{font-size:24px;font-weight:700;line-height:1.2}.kpi-label{display:block;font-size:13px;min-width:0;white-space:nowrap}.kpi-caption{display:block;font-size:11px;color:var(--muted);margin-top:3px}.scroll{width:100%;max-width:100%;overflow-x:visible;margin:10px 0 18px;border:1px solid var(--border);border-radius:7px}table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:14px;line-height:1.35}th,td{text-align:left;vertical-align:top;padding:6px 3px;border-bottom:1px solid var(--border);overflow-wrap:break-word}th{background:var(--surface);font-weight:700}th.id-cell,td.id-cell,th.num,td.num,.chip,.date{white-space:nowrap}th.num,td.num{text-align:center;font-variant-numeric:tabular-nums}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:color-mix(in srgb,var(--surface) 55%,transparent)}.date{font-size:12px}.status{font-size:10px;padding:2px 3px}.chip{display:inline-block;font-size:12px;padding:2px 7px;border-radius:999px;line-height:1.35;vertical-align:middle;border:1px solid transparent}.tier-low{color:var(--tier-low-fg);background:var(--tier-low-bg)}.tier-medium{color:var(--tier-medium-fg);background:var(--tier-medium-bg)}.tier-high{color:var(--tier-high-fg);background:var(--tier-high-bg)}.tier-unacceptable{color:var(--tier-unacceptable-fg);background:var(--tier-unacceptable-bg)}.result-pass{color:var(--pass-fg);background:var(--pass-bg)}.result-fail{color:var(--fail-fg);background:var(--fail-bg)}.result-not-tested{color:var(--not-tested-fg);background:var(--not-tested-bg)}.agent-yes{color:var(--agent-yes-fg);background:var(--agent-yes-bg)}.agent-no{color:var(--agent-no-fg);background:var(--agent-no-bg)}.status-shortlisted{color:var(--shortlisted-fg);background:var(--shortlisted-bg)}.status-eligible{color:var(--eligible-fg);background:var(--eligible-bg);border-color:var(--eligible-fg)}.status-not-eligible{color:var(--not-eligible-fg);background:var(--not-eligible-bg);border-color:var(--not-eligible-fg)}.family-chip{font-size:11px;margin-top:3px}.evidence-description{display:block;font-size:12px;line-height:1.3;margin-top:4px}.result-detail{display:block;white-space:normal;overflow-wrap:break-word;font-size:12px;margin-top:6px;line-height:1.4}.log-field{font:12px/1.3 ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}.control-requirement{font-size:14px}.control-description{font-size:13px;margin-top:4px}.stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.governance-card{border:1px solid var(--border);border-radius:12px;padding:20px;margin:0 0 24px}.card-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px}.card-heading h3{flex:1 1 240px}.matrix-wrap{width:100%;max-width:600px;margin:0 auto}.chart{display:block;width:100%;height:auto}.chart text{fill:var(--fg);font:12px system-ui,sans-serif}.chart .axis-title{font-size:12px;font-weight:700}.chart .matrix-label{font-size:11px}.chart .gridline{stroke:var(--grid);stroke-width:1}.chart .axis{stroke:var(--muted);stroke-width:1}.chart .shortlisted-point{fill:var(--accent);stroke:var(--accent);stroke-width:2}.chart .eligible-point{fill:var(--matrix-eligible);stroke:var(--accent);stroke-width:2}.chart .gated-point{fill:transparent;stroke:var(--gated-stroke);stroke-width:2;stroke-dasharray:4 3}.heatmap-wrap{width:100%;max-width:520px;margin:0 auto}.heatmap-chart{display:block;width:100%;height:auto}.chart .heat-low{--heat-tier:var(--heat-low)}.chart .heat-medium{--heat-tier:var(--heat-medium)}.chart .heat-high{--heat-tier:var(--heat-high)}.chart .heat-unacceptable{--heat-tier:var(--heat-unacceptable)}.chart .heat-cell{stroke:var(--border);stroke-width:1}.chart .heat-cell.heat-c0{fill:var(--heat-neutral);fill-opacity:1}.chart .heat-cell.heat-c1{fill:var(--heat-tier);fill-opacity:.35}.chart .heat-cell.heat-c2{fill:var(--heat-tier);fill-opacity:.6}.chart .heat-cell.heat-c3{fill:var(--heat-tier);fill-opacity:.85}.chart .heat-count{font-size:18px;font-weight:700}.chart .heat-count.heat-c0{fill:var(--muted)}.chart .heat-count.heat-c1,.chart .heat-count.heat-c2{fill:var(--fg)}.chart .heat-count.heat-c3{fill:#fff;stroke:var(--heat-count-outline);stroke-width:1px;paint-order:stroke}.chart .heat-header{font-size:13px;font-weight:700}.chart .appetite-line{stroke:var(--muted);stroke-width:2;stroke-dasharray:5 4}.chart .appetite-label{font-size:12px;font-weight:700}.chart .heat-text-low{fill:var(--tier-low-fg)}.chart .heat-text-medium{fill:var(--tier-medium-fg)}.chart .heat-text-high{fill:var(--tier-high-fg)}.chart .heat-text-unacceptable{fill:var(--tier-unacceptable-fg)}.chart .appetite-line{stroke:var(--muted);stroke-width:2;stroke-dasharray:5 4}.matrix-legend{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:8px 16px;font-size:12px;margin:2px auto 6px}.legend-item{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}.legend-mark{display:inline-block;width:12px;height:12px;border-radius:50%;background:var(--accent)}.legend-mark.eligible{background:var(--bg);border:1.5px solid var(--accent)}.legend-mark.gated{background:transparent;border:1.5px dashed var(--gated-stroke)}.diagram{display:block;width:100%;max-width:720px;height:auto;margin:0 auto}.chart-figure{margin:10px 0 18px}figcaption{color:var(--muted);font-size:14px}.formula{border:1px solid var(--border);background:var(--surface);padding:12px 14px;border-radius:8px;font:14px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:break-word}footer{border-top:1px solid var(--border);margin-top:30px;padding-top:12px;color:var(--muted)}
 .explorer-panel{box-sizing:border-box;padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--surface);margin:12px 0}.explorer-panel h3{margin:0}.explorer-hint{font-size:13px;color:var(--muted);margin:4px 0 12px}.explorer-controls{display:grid;box-sizing:border-box;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.weight-control{box-sizing:border-box;min-width:0}.weight-label-row{display:flex;justify-content:space-between;gap:8px;font-size:13px}.weight-label-row output{font-variant-numeric:tabular-nums}.weight-control input[type=range]{display:block;width:100%;margin:8px 0 0;accent-color:#0f766e}.risk-fieldset{box-sizing:border-box;min-width:0;margin:0;padding:0;border:0}.risk-fieldset legend{font-size:13px;margin-bottom:6px}.appetite-options{display:flex;gap:6px}.appetite-option{position:relative;flex:1 1 0;min-width:0;text-align:center;font-size:13px}.appetite-option input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}.appetite-option span{display:block;padding:5px 8px;border:1px solid var(--border);border-radius:6px;cursor:pointer}.appetite-option input:checked+span{background:#0f766e;color:#fff;border-color:#0f766e}.appetite-option input:focus-visible+span{outline:2px solid #0b4f5c;outline-offset:2px}.explorer-actions{display:flex;align-items:center;gap:12px;margin-top:12px}.stage-filters{display:flex;flex-wrap:wrap;gap:6px}.stage-chip,.reset-ranking{font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;border:1px solid var(--border);border-radius:999px;padding:5px 10px;background:var(--bg);color:var(--fg);cursor:pointer}.stage-chip{white-space:nowrap}.stage-chip[aria-pressed=true]{background:#0f766e;color:#fff;border-color:#0f766e}.reset-ranking{margin-left:auto;white-space:nowrap}.explorer-formula{margin-top:12px}.weight-error{color:#b71c1c;font-size:13px;margin:6px 0 0}.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.row-detail{box-sizing:border-box;margin:12px 0 0;padding:16px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}.detail-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.detail-heading h3{margin:0}.detail-close{border:1px solid var(--border);border-radius:6px;padding:4px 10px;background:var(--bg);color:var(--fg);cursor:pointer}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px;margin-top:12px}.detail-field{min-width:0;font-size:13px;overflow-wrap:break-word}.detail-field strong{display:block;font-size:12px;color:var(--muted)}.detail-rationales{margin-top:12px}.detail-rationales p{font-size:13px;margin:6px 0}.detail-governance{font-size:13px;margin-top:12px}.ranked-table tr.is-selected td,.ineligible-table tr.is-selected td{background:color-mix(in srgb,#0f766e 10%,var(--surface))}.ranked-table tr.is-selected td:first-child,.ineligible-table tr.is-selected td:first-child{border-left:3px solid #0f766e}.formula-error{color:#b71c1c}
@media(min-width:1100px){.explorer-controls{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:640px) and (max-width:1099px){.explorer-controls{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:639px){.explorer-controls{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}}
@media(max-width:759px){.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.how-to-read{grid-template-columns:1fr}.scroll{overflow-x:auto}}
@media(max-width:419px){.kpis{grid-template-columns:1fr}}
@media(max-width:759px){.hero h1{font-size:24px}}
</style>"""


def _kpis_html(cases: list[dict[str, Any]], ranked: list[dict[str, Any]], ineligible: list[dict[str, Any]], appetite: str, shortlist_size: int) -> str:
    high_ids = ", ".join(sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "high"))
    unacceptable_ids = ", ".join(sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "unacceptable"))
    not_eligible_caption = " · ".join(
        part for part in (f"{high_ids} high" if high_ids else "", f"{unacceptable_ids} unacceptable" if unacceptable_ids else "") if part
    )
    values = (
        ("kpi-assessed", "Use cases assessed", len(cases), f"across {len({row['value_chain_stage'] for row in cases})} value-chain stages"),
        ("kpi-eligible", "Eligible", len(ranked), f"at {RISK_LABELS[appetite]} appetite · internal AI risk tier ≤ {RISK_LABELS[appetite]}"),
        ("kpi-shortlisted", "Shortlisted", sum(row["shortlisted"] for row in ranked), f"top {shortlist_size} by weighted score"),
        ("kpi-ineligible", "Not eligible", len(ineligible), not_eligible_caption),
    )
    return '<section id="kpis" aria-label="Assessment summary"><div class="kpis">' + "".join(
        f'<div class="kpi {css_class}"><div class="kpi-main"><strong>{number}</strong><span class="kpi-label">{_esc(label)}</span></div><span class="kpi-caption">{_esc(caption)}</span></div>' for css_class, label, number, caption in values
    ) + "</div></section>"


def _priority_matrix(cases: list[dict[str, Any]], ranked: list[dict[str, Any]], ineligible: list[dict[str, Any]], appetite: str) -> str:
    classes = {row["use_case_id"]: "shortlisted-point" if row["shortlisted"] else "eligible-point" for row in ranked}
    classes.update({row["use_case_id"]: "gated-point" for row in ineligible})
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        groups[(case["feasibility"], case["value"])].append(case)
    offsets: dict[str, int] = {}
    for group in groups.values():
        ordered = sorted(group, key=lambda row: row["use_case_id"])
        positions = {-1: -22, 0: 0, 1: 22}
        selected = (-1, 1) if len(ordered) == 2 else ((-1, 0, 1) if len(ordered) >= 3 else (0,))
        for case, slot in zip(ordered, selected):
            offsets[case["use_case_id"]] = positions[slot]
    pieces = ['<svg class="chart priority-chart" viewBox="0 0 720 440" role="img" aria-labelledby="matrix-title matrix-desc" data-chart="priority-matrix">', '<title id="matrix-title">Priority matrix</title><desc id="matrix-desc">Use cases plotted by feasibility and value; bubble size shows data readiness.</desc>']
    for value in range(1, 6):
        y = 380 - (value - 1) * 85
        pieces.append(f'<line class="gridline" x1="70" y1="{y}" x2="650" y2="{y}"/><text x="55" y="{y + 4}" text-anchor="end">{value}</text>')
    for feasibility in range(1, 6):
        x = 70 + (feasibility - 1) * 145
        pieces.append(f'<line class="gridline" x1="{x}" y1="40" x2="{x}" y2="380"/><text x="{x}" y="400" text-anchor="middle">{feasibility}</text>')
    pieces.extend(['<line class="axis" x1="70" y1="380" x2="650" y2="380"/>', '<line class="axis" x1="70" y1="40" x2="70" y2="380"/>', '<text class="axis-title" x="360" y="429" text-anchor="middle">Feasibility (1–5)</text>', '<text class="axis-title" x="16" y="210" text-anchor="middle" transform="rotate(-90 16 210)">Value (1–5)</text>'])
    for case in cases:
        x = 70 + (case["feasibility"] - 1) * 145 + offsets[case["use_case_id"]]
        y = 380 - (case["value"] - 1) * 85
        radius = 6 + 2.5 * case["data_readiness"]
        case_class = classes[case["use_case_id"]]
        pieces.append(f'<circle class="{case_class}" data-id="{_esc(case["use_case_id"])}" cx="{x}" cy="{y}" r="{radius}"/>')
        group = sorted(groups[(case["feasibility"], case["value"])], key=lambda row: row["use_case_id"])
        label_index = next(index for index, member in enumerate(group) if member["use_case_id"] == case["use_case_id"])
        label_y = y - radius - 4 if label_index % 2 == 0 else y + radius + 12
        pieces.append(f'<text class="matrix-label" x="{x}" y="{label_y}" text-anchor="middle">{_esc(case["use_case_id"])}</text>')
    pieces.append("</svg>")
    legend = ('<div class="matrix-legend" aria-label="Priority matrix legend">'
              '<span class="legend-item"><span class="legend-mark shortlisted"></span>Shortlisted</span>'
              '<span class="legend-item"><span class="legend-mark eligible"></span>Eligible</span>'
              '<span class="legend-item"><span class="legend-mark gated"></span>Not eligible – risk gate</span>'
              '<span class="legend-item">Bubble size = data readiness</span></div>')
    return '<section id="matrix"><h2>Priority matrix</h2><figure class="chart-figure"><div class="matrix-wrap">' + "".join(pieces) + '</div>' + legend + f'<figcaption><span id="matrix-appetite">Appetite: {_esc(RISK_LABELS[appetite])}</span> · Bubble size = data readiness. Dashed = blocked by the internal AI risk gate at appetite.</figcaption></figure></section>'


def _heatmap(cases: list[dict[str, Any]], appetite: str) -> str:
    counts = Counter((row["value_chain_stage"], row["risk_tier"]) for row in cases)
    total = sum(counts.values())
    pieces = ['<svg class="chart heatmap-chart" viewBox="0 0 640 360" role="img" aria-labelledby="heat-title heat-desc" data-chart="risk-heatmap">', '<title id="heat-title">Use cases by stage and internal AI risk tier</title>', f'<desc id="heat-desc">Counts total {total} across five value-chain stages and four risk tiers.</desc>']
    headers = ("Low", "Medium", "High", "Unacceptable")
    x0, y0, cw, ch = 140, 76, 120, 52
    for col, header in enumerate(headers):
        x = x0 + col * cw + cw / 2
        tier = RISK_TIERS[col]
        if tier == "unacceptable":
            pieces.append(f'<text class="heat-header heat-text-{tier}" x="{x}" y="42" text-anchor="middle">{header}</text><text class="heat-header heat-text-{tier}" x="{x}" y="57" text-anchor="middle">· never eligible</text>')
        else:
            pieces.append(f'<text class="heat-header heat-text-{tier}" x="{x}" y="52" text-anchor="middle">{header}</text>')
    for row_index, stage in enumerate(STAGES):
        y = y0 + row_index * ch
        pieces.append(f'<text x="{x0 - 12}" y="{y + 33}" text-anchor="end">{_esc(STAGE_LABELS[stage])}</text>')
        for col, tier in enumerate(RISK_TIERS):
            x = x0 + col * cw
            count = counts[(stage, tier)]
            count_class = min(count, 3)
            pieces.append(f'<rect class="heat-cell heat-{tier} heat-c{count_class}" x="{x}" y="{y}" width="{cw}" height="{ch}"/>')
            pieces.append(f'<text class="heat-count heat-text-{tier} heat-c{count_class}" x="{x + cw / 2}" y="{y + 33}" text-anchor="middle">{count}</text>')
    appetite_col = RISK_TIERS.index(appetite)
    appetite_x = x0 + (appetite_col + 1) * cw
    pieces.append(f'<line class="appetite-line" x1="{appetite_x}" y1="20" x2="{appetite_x}" y2="{y0 + len(STAGES) * ch}"/>')
    pieces.append(f'<text class="appetite-label" x="{appetite_x + 5}" y="14">Appetite: {_esc(RISK_LABELS[appetite])}</text>')
    pieces.append("</svg>")
    return '<section id="heatmap"><h2>Risk heatmap</h2><figure class="heatmap-wrap">' + "".join(pieces) + f'<figcaption>Counts by value-chain stage and internal AI risk tier · total {total}</figcaption></figure></section>'


def _table_rows(ranked: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> list[list[str]]:
    rows = []
    for row in ranked:
        case = by_id[row["use_case_id"]]
        case_id = _esc(row["use_case_id"])
        if case["worked_governance"]:
            case_id = f'<a href="#{case_id}">{case_id}</a>'
        status = "shortlisted" if row["shortlisted"] else "eligible"
        label = "Shortlisted" if row["shortlisted"] else "Eligible"
        rows.append([str(row["rank"]), case_id, _esc(case["name"]), _esc(STAGE_LABELS[case["value_chain_stage"]]), _esc(case["line_of_business"].title()), str(case["value"]), str(case["feasibility"]), str(case["data_readiness"]), _risk_html(case["risk_tier"]), f'{row["score"]:.1f}', _status_html(label, status)])
    return rows


def _formula(config: dict[str, Any]) -> str:
    weights = config["default_weights"]
    total = sum(weights.values())
    appetite = RISK_LABELS[config["default_max_risk"]]
    return (f"Gate: eligible only when internal AI risk tier ≤ appetite ({appetite}); unacceptable is never eligible.\n"
            f"Score = round(100 × ({weights['value']} × value + {weights['feasibility']} × feasibility + {weights['data_readiness']} × data readiness) ÷ (5 × {total}), 1).\n"
            "Tie-break: value descending, data readiness descending, then use case ID ascending.")


def _live_formula(config: dict[str, Any]) -> str:
    weights = config["default_weights"]
    appetite = RISK_LABELS[config["default_max_risk"]]
    total = sum(weights.values())
    return f"Appetite: {appetite} · Score = 100 × ({weights['value']}·value + {weights['feasibility']}·feasibility + {weights['data_readiness']}·data readiness) ÷ (5 × {total})"


def _explorer_panel(config: dict[str, Any]) -> str:
    weights = config["default_weights"]
    weight_controls = []
    for key, label in (("value", "Value"), ("feasibility", "Feasibility"), ("data_readiness", "Data readiness")):
        value = weights[key]
        weight_controls.append(
            f'<div class="weight-control"><div class="weight-label-row"><label for="weight-{key}">{label}</label>'
            f'<output id="weight-{key}-output" for="weight-{key}">{value}</output></div>'
            f'<input id="weight-{key}" type="range" min="0" max="10" step="1" value="{value}" '
            f'aria-label="{label} weight" aria-valuetext="{label} weight {value}"></div>'
        )
    appetite_buttons = []
    for appetite in config["allowed_max_risk"]:
        label = RISK_LABELS[appetite]
        checked = " checked" if appetite == config["default_max_risk"] else ""
        appetite_buttons.append(
            f'<label class="appetite-option"><input type="radio" name="appetite" value="{appetite}"{checked}>'
            f'<span>{label}</span></label>'
        )
    stage_buttons = ['<button type="button" class="stage-chip" data-stage="all" aria-pressed="true">All</button>']
    for stage in STAGES:
        stage_buttons.append(
            f'<button type="button" class="stage-chip" data-stage="{stage}" aria-pressed="false">{_esc(STAGE_LABELS[stage])}</button>'
        )
    return (
        '<div class="explorer-panel" aria-labelledby="explorer-heading">'
        '<h3 id="explorer-heading">Explore the ranking</h3>'
        '<p class="explorer-hint">Change the weights or the risk appetite. The gate is applied first; weights only rank eligible use cases.</p>'
        f'<div class="explorer-controls">{"".join(weight_controls)}'
        f'<fieldset class="risk-fieldset"><legend>Risk appetite (gate)</legend><div class="appetite-options">{"".join(appetite_buttons)}</div></fieldset></div>'
        f'<div class="explorer-actions"><div class="stage-filters" aria-label="Filter by value-chain stage">{"".join(stage_buttons)}</div>'
        '<button type="button" class="reset-ranking">Reset to defaults</button></div>'
        '<p class="weight-error" id="weight-error" hidden></p>'
        '<div class="visually-hidden" id="ranking-announcement" aria-live="polite"></div>'
        '</div>'
    )


def _html_content() -> str:
    config, scenario, cases, ranked, ineligible = _ranked_data()
    controls, actions = load_controls(), load_actions()
    by_id = {row["use_case_id"]: row for row in cases}
    worked = [case for case in cases if case["worked_governance"]]
    insurer_short = scenario["insurer"].removeprefix("Simulated ")
    question = f"Which AI use cases should a {insurer_short} take forward, and under what controls?"
    hero_chips = "".join(
        f'<span class="hero-chip">{_esc(value)}</span>'
        for value in (scenario["market"], scenario["currency"], *scenario["lines"])
    )
    hero = (
        '<header class="hero"><div class="hero-inner">'
        f'<span class="hero-pill">{LABEL_LINE}</span>'
        f'<h1>{_esc(scenario["title"])}</h1>'
        f'<p class="hero-question">{_esc(question)}</p>'
        f'<div class="hero-chips">{hero_chips}</div>'
        '<div class="hero-actions"><a class="hero-button primary" href="#ranking">View ranking</a>'
        '<a class="hero-button outline" href="#governance">Worked governance</a></div>'
        '</div></header>'
    )
    present_stages = [stage for stage in STAGES if any(case["value_chain_stage"] == stage for case in cases)]
    stage_names = [STAGE_LABELS[stage].lower() for stage in present_stages]
    stage_summary = ", ".join(stage_names[:-1]) + (f" and {stage_names[-1]}" if len(stage_names) > 1 else (stage_names[0] if stage_names else "no value-chain stages"))
    worked_shortlisted = sum(row["shortlisted"] and by_id[row["use_case_id"]]["worked_governance"] for row in ranked)
    count_words = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    worked_count_text = count_words.get(worked_shortlisted, str(worked_shortlisted))
    body = ['<main id="top">']
    body.append(_kpis_html(cases, ranked, ineligible, config["default_max_risk"], config["shortlist_size"]))
    body.extend([
        '<section id="context" class="how-to-read" aria-label="How to read this page">'
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">1</span><strong>Assess</strong></div>'
        f'<p>{len(cases)} AI use cases across {_esc(stage_summary)}.</p></article>'
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">2</span><strong>Gate</strong></div>'
        "<p>Each must pass the insurer's internal AI risk tier – its own appetite measure, not a regulatory classification.</p></article>"
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">3</span><strong>Prioritise and govern</strong></div>'
        f'<p>Eligible use cases are ranked by weighted score; {worked_count_text} shortlisted ones carry worked controls and agent accountability.</p></article>'
        '</section>'
    ])
    if (REPO_ROOT / "docs" / "diagrams" / "value_chain.svg").is_file():
        body.append('<section id="value-chain"><h2>Value chain</h2><figure><img class="diagram" src="diagrams/value_chain.svg" alt="Value chain to governance flow"></figure></section>')
    body.extend([
        _priority_matrix(cases, ranked, ineligible, config["default_max_risk"]),
        _heatmap(cases, config["default_max_risk"]),
        '<section id="scoring"><h2>Scoring formula</h2>',
        f'<div class="formula" id="score-formula">{_esc(_live_formula(config))}</div></section>',
        '<section id="ranking"><h2>Ranked use cases</h2>',
        _explorer_panel(config),
        _html_table(
            ["Rank", "ID", "Use case", "Stage", "Line", "Value", "Feasibility", "Data readiness", "Internal AI risk tier", "Score", "Status"],
            _table_rows(ranked, by_id), widths=(6, 7, 25, 9, 11, 6, 7, 7, 9, 5, 8), classes="ranked-table",
            header_labels=("Rank", "ID", "Use case", "Stage", "Line", "Value", "Feasibility", "Data<br>readiness", "Internal AI<br>risk tier", "Score", "Status"),
            row_ids=[row["use_case_id"] for row in ranked],
        ),
        '<div class="row-detail" id="row-detail" role="region" aria-label="Use case details" tabindex="-1" hidden></div>',
        '</section><section id="not-eligible"><h2>Not eligible</h2>',
    ])
    ineligible_rows = [[_esc(row["use_case_id"]), _esc(by_id[row["use_case_id"]]["name"]), _esc(STAGE_LABELS[by_id[row["use_case_id"]]["value_chain_stage"]]), _risk_html(by_id[row["use_case_id"]]["risk_tier"]), _status_html("Not eligible", "not-eligible")] for row in ineligible]
    body.extend([_html_table(["ID", "Use case", "Stage", "Internal AI risk tier", "Status"], ineligible_rows, widths=(8, 32, 16, 20, 24), classes="ineligible-table", row_ids=[row["use_case_id"] for row in ineligible]), '</section><section id="governance" data-section="worked-governance"><h2>Worked governance</h2>'])
    for case in worked:
        use_case_id = case["use_case_id"]
        case_controls, case_actions = _controls_for(use_case_id, controls), _actions_for(use_case_id, actions)
        control_rows = [[f'<strong class="id-cell">{_esc(item["control_id"])}</strong><br><span class="chip family-chip">{_esc(item["requirement_family"].title())}</span>', f'<strong class="control-requirement">{_esc(item["requirement"])}</strong><div class="control-description">{_esc(item["control"])}</div>', _esc(item["owner_role"]), _evidence_html(item), f'<div>{_result_html(item["test_result"])}</div>{_exception_detail_html(item)}', f'<span class="date">{_esc(item["review_date"])}</span>'] for item in case_controls]
        action_rows = [[_esc(item["action"].title()), _agent_allowed_html(item["agent_allowed"]), _esc(item["tool_permissions"]), _esc(item["accountable_human_role"]), _esc(item["escalation_path"]), f'<span class="log-field">{_esc(item["log_field"])}</span>'] for item in case_actions]
        body.extend([f'<article class="governance-card" id="{_esc(use_case_id)}"><div class="card-heading"><span class="chip">{_esc(use_case_id)}</span><h3>{_esc(case["name"])}</h3><span class="chip">{_esc(STAGE_LABELS[case["value_chain_stage"]])}</span>{_risk_html(case["risk_tier"])}</div>', f'<p>{_esc(case["description"])}</p><p><strong>Owner role:</strong> {_esc(case["owner_role"])}</p>', _stats_html(case_controls), '<h4>Controls trace</h4>', _html_table(["Control", "Requirement and control", "Owner", "Evidence", "Result", "Review"], control_rows, widths=(12, 36, 13, 16, 15, 8), classes="controls-table"), '<h4>Agent accountability</h4>', _html_table(["Action", "Agent allowed", "Tool permissions", "Accountable role", "Escalation path", "Log field"], action_rows, widths=(10, 9, 31, 16, 22, 12), classes="accountability-table"), '</article>'])
    source_links = " · ".join(f'<a href="{_repo_url(path)}">{_esc(label)}</a>' for label, path in _links())
    body.extend(['</section>', f'<footer><p>{_esc(BOUNDARY)}</p><p>Source data: {source_links}</p><p>MIT licence</p></footer></main>'])
    controls_summary = {
        case["use_case_id"]: _stats(_controls_for(case["use_case_id"], controls))
        for case in worked
    }
    embedded_data = {
        "use_cases": cases,
        "scoring_config": config,
        "controls_summary": controls_summary,
        "scenario": scenario,
    }
    json_payload = json.dumps(embedded_data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    data_script = f'<script type="application/json" id="vc-data">{json_payload}</script>'
    return PAGE_TEMPLATE.format(title=_esc(scenario["title"]), styles=_css(), content=hero + "\n" + "\n".join(body), data_script=data_script)


def _md_escape(value: Any) -> str:
    return str(value if value not in (None, "") else "–").replace("|", "\\|").replace("\n", " ")


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(row) + " |" for row in rows])


def _md_evidence(row: dict[str, Any]) -> str:
    reference = row["evidence_ref"]
    description = _md_escape(row.get("evidence_description"))
    if reference.startswith("https://"):
        return f"[Design record]({reference})"
    label = "Simulated evidence" if reference == "simulated" else "No evidence – exception"
    return f"**{label}** — {description}"


def _markdown_content() -> str:
    config, scenario, cases, ranked, ineligible = _ranked_data()
    controls, actions = load_controls(), load_actions()
    by_id = {row["use_case_id"]: row for row in cases}
    worked = [case for case in cases if case["worked_governance"]]
    scenario_line = f'{scenario["insurer"]} · {scenario["market"]} · {scenario["currency"]} · {", ".join(scenario["lines"])}'
    kpi_line = f"Use cases assessed: {len(cases)} · Eligible at {RISK_LABELS[config['default_max_risk']]} appetite: {len(ranked)} · Shortlisted: {sum(row['shortlisted'] for row in ranked)} · Not eligible: {len(ineligible)}"
    lines = [f'# {scenario["title"]}\n\n{LABEL_LINE}\n\n{scenario_line}\n\n{kpi_line}\n\n', "## Context\n\n", f'{scenario["insurer"]} operates in {scenario["market"]}; the assessment covers {len(cases)} use cases across {len(STAGES)} value-chain stages: {", ".join(STAGE_LABELS[stage] for stage in STAGES)}.  \n', f'Lines in scope: {", ".join(scenario["lines"])}; currency: {scenario["currency"]}.  \n', "Each use case passes an internal AI risk gate before it is ranked, using the selected appetite and weighted assessment criteria.  \n", f"{len(worked)} use cases include a worked governance pack with controls trace and agent accountability.  \n", "The internal AI risk tier is an internal appetite measure, not a regulatory classification.\n\n"]
    lines.append("## Stage × internal risk tier counts\n\n")
    stage_counts = [[STAGE_LABELS[stage], *[str(sum(case["value_chain_stage"] == stage and case["risk_tier"] == tier for case in cases)) for tier in RISK_TIERS]] for stage in STAGES]
    lines.extend([_md_table(["Stage", *[RISK_LABELS[tier] for tier in RISK_TIERS]], stage_counts), "\n\n"])
    lines.extend(["## Scoring formula\n\n", _formula(config), "\n\n## Ranked use cases\n\n"])
    ranking = []
    for row in ranked:
        case = by_id[row["use_case_id"]]
        case_id = f'[{row["use_case_id"]}](#{row["use_case_id"].lower()})' if case["worked_governance"] else row["use_case_id"]
        ranking.append([str(row["rank"]), case_id, _md_escape(case["name"]), STAGE_LABELS[case["value_chain_stage"]], case["line_of_business"].title(), str(case["value"]), str(case["feasibility"]), str(case["data_readiness"]), RISK_LABELS[case["risk_tier"]], f'{row["score"]:.1f}', "Shortlisted" if row["shortlisted"] else "Eligible"])
    lines.extend([_md_table(["Rank", "ID", "Use case", "Stage", "Line", "Value", "Feasibility", "Data readiness", "Internal AI risk tier", "Score", "Status"], ranking), "\n\n## Not eligible\n\n"])
    blocked = [[row["use_case_id"], _md_escape(by_id[row["use_case_id"]]["name"]), STAGE_LABELS[by_id[row["use_case_id"]]["value_chain_stage"]], RISK_LABELS[by_id[row["use_case_id"]]["risk_tier"]], row["status"]] for row in ineligible]
    lines.extend([_md_table(["ID", "Use case", "Stage", "Internal AI risk tier", "Status"], blocked), "\n\n## Worked governance\n\n"])
    for case in worked:
        use_case_id = case["use_case_id"]
        case_controls, case_actions = _controls_for(use_case_id, controls), _actions_for(use_case_id, actions)
        stats = _stats(case_controls)
        lines.extend([f'### {use_case_id} · {_md_escape(case["name"])} · {STAGE_LABELS[case["value_chain_stage"]]} · {RISK_LABELS[case["risk_tier"]]} risk tier\n\n', f'{_md_escape(case["description"])}\n\n**Owner role:** {_md_escape(case["owner_role"])}\n\n', f'Pass: {stats["pass"]} · Fail: {stats["fail"]} · Not tested: {stats["not tested"]} · Exceptions: {stats["exceptions"]}\n\n', "#### Controls trace\n\n"])
        control_rows = [[_md_escape(row["control_id"]), _md_escape(row["requirement_family"].title()), _md_escape(row["requirement"]), _md_escape(row["control"]), _md_escape(row["owner_role"]), _md_evidence(row), row["test_result"], _md_escape(row.get("exception_id") or row.get("remediation_note")), row["review_date"]] for row in case_controls]
        action_rows = [[row["action"].title(), row["agent_allowed"], _md_escape(row["tool_permissions"]), _md_escape(row["accountable_human_role"]), _md_escape(row["escalation_path"]), row["log_field"]] for row in case_actions]
        lines.extend([_md_table(["Control ID", "Family", "Requirement", "Control description", "Owner role", "Evidence", "Result", "Exception", "Review date"], control_rows), "\n\n#### Agent accountability\n\n", _md_table(["Action", "Agent allowed", "Tool permissions", "Accountable human role", "Escalation path", "Log field"], action_rows), "\n\n"])
    lines.extend(["---\n\n", BOUNDARY, "\n\nMIT licence\n"])
    return "".join(lines)


def build(output_dir: str | Path | None = None) -> tuple[Path, Path]:
    """Write the static page and report as deterministic UTF-8/LF files."""
    errors = validate()
    if errors:
        raise ValueError("Cannot build with invalid data:\n" + "\n".join(errors))
    target_dir = Path(output_dir) if output_dir is not None else REPO_ROOT / "docs"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "diagrams").mkdir(parents=True, exist_ok=True)
    (target_dir / "diagrams" / "value_chain.mmd").write_bytes(_diagram_source().encode("utf-8"))
    html_path, markdown_path = target_dir / "index.html", target_dir / "ASSESSMENT.md"
    html_path.write_bytes(_html_content().replace("\r\n", "\n").encode("utf-8"))
    markdown_path.write_bytes(_markdown_content().replace("\r\n", "\n").encode("utf-8"))
    return html_path, markdown_path
