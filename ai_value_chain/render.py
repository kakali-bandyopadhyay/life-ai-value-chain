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

CASE_STUDY_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<title>{title}</title>
{styles}
</head>
<body class="cs-page">
{content}
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


def _value_chain_svg() -> str:
    """Render an accessible, data-derived value-chain flow diagram as inline SVG."""
    config, _, cases, ranked, ineligible = _ranked_data()
    appetite = RISK_LABELS[config["default_max_risk"]]
    stage_counts = Counter(row["value_chain_stage"] for row in cases)
    high_ids = sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "high")
    unacceptable_ids = sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == "unacceptable")
    ineligible_ids = " · ".join(high_ids + unacceptable_ids)
    worked_ids = sorted(row["use_case_id"] for row in cases if row["worked_governance"])
    controls_count = len(load_controls())
    actions_count = len(load_actions())
    stage_order = ("distribution", "underwriting", "policy_admin", "servicing", "claims")
    stage_x = tuple(10 + 140 * index for index in range(len(stage_order)))
    stage_parts = []
    for stage, x in zip(stage_order, stage_x):
        center = x + 66
        stage_parts.append(
            f'<g class="stage" data-stage="{stage}" data-box="stage-{stage}"><rect x="{x}" y="16" width="132" height="52" rx="8"/>'
            f'<text class="box-title" x="{center}" y="37" text-anchor="middle"><tspan>{_esc(STAGE_LABELS[stage])}</tspan></text>'
            f'<text class="box-detail" x="{center}" y="54" text-anchor="middle">{stage_counts[stage]} use cases</text></g>'
        )
    edges = []
    for index, (stage, x) in enumerate(zip(stage_order, stage_x)):
        stage_center = x + 66
        gate_x = 262 + 49 * index
        edges.append(
            f'<line class="flow-arrow" data-source="stage-{stage}" data-target="gate" x1="{stage_center}" y1="68" x2="{gate_x}" y2="112" marker-end="url(#flow-arrowhead)"/>'
        )
    edges.extend([
        '<line class="flow-arrow" data-source="gate" data-target="shortlist" x1="360" y1="164" x2="360" y2="212" marker-end="url(#flow-arrowhead)"/>',
        '<line class="flow-arrow dashed" data-source="gate" data-target="ne" x1="460" y1="164" x2="620" y2="212" marker-end="url(#flow-arrowhead)"/>',
        '<line class="flow-arrow" data-source="shortlist" data-target="worked" x1="360" y1="264" x2="360" y2="300" marker-end="url(#flow-arrowhead)"/>',
        '<line class="flow-arrow" data-source="worked" data-target="controls" x1="292" y1="352" x2="292" y2="392" marker-end="url(#flow-arrowhead)"/>',
        '<line class="flow-arrow" data-source="worked" data-target="accountability" x1="428" y1="352" x2="428" y2="392" marker-end="url(#flow-arrowhead)"/>',
    ])
    worked_text = " · ".join(worked_ids)
    return (
        '<svg class="diagram value-chain-flow" viewBox="0 0 720 460" role="img" aria-labelledby="value-chain-title value-chain-desc">'
        '<title id="value-chain-title">Value chain assessment and governance flow</title>'
        f'<desc id="value-chain-desc">{len(cases)} use cases across five stages pass through an internal AI risk gate at {html.escape(appetite)} appetite. '
        f'{len(ineligible)} are not eligible; the ranked shortlist flows to worked governance, {controls_count} controls and {actions_count} accountability actions.</desc>'
        '<defs><marker id="flow-arrowhead" markerUnits="userSpaceOnUse" viewBox="0 0 7 7" markerWidth="7" markerHeight="7" refX="7" refY="3.5" orient="auto"><path class="arrowhead" d="M0,0 L7,3.5 L0,7 z"/></marker></defs>'
        + "".join(edges)
        + "".join(stage_parts)
        + '<g class="gate" data-box="gate"><rect x="230" y="112" width="260" height="52" rx="8"/>'
        + '<text class="box-title" x="360" y="134" text-anchor="middle">Internal AI risk gate</text>'
        + f'<text class="box-detail" x="360" y="152" text-anchor="middle">appetite: {html.escape(appetite)}</text></g>'
        + '<g class="shortlist" data-box="shortlist"><rect x="230" y="212" width="260" height="52" rx="8"/>'
        + '<text class="box-title" x="360" y="234" text-anchor="middle">Ranked shortlist</text>'
        + f'<text class="box-detail" x="360" y="252" text-anchor="middle">top {config["shortlist_size"]} of {len(ranked)} eligible</text></g>'
        + f'<g class="ne" data-box="ne"><rect x="530" y="212" width="180" height="52" rx="8"/><text class="box-title" x="620" y="234" text-anchor="middle">Not eligible ({len(ineligible)})</text>'
        + f'<text class="box-detail" x="620" y="252" text-anchor="middle">{html.escape(ineligible_ids)}</text></g>'
        + '<g class="gov worked" data-box="worked"><rect x="230" y="300" width="260" height="52" rx="8"/>'
        + '<text class="box-title" x="360" y="322" text-anchor="middle">Worked governance</text>'
        + f'<text class="box-detail" x="360" y="340" text-anchor="middle">{html.escape(worked_text)}</text></g>'
        + '<g class="gov controls" data-box="controls"><rect x="230" y="392" width="124" height="52" rx="8"/>'
        + '<text class="box-title" x="292" y="414" text-anchor="middle">Controls trace</text>'
        + f'<text class="box-detail" x="292" y="432" text-anchor="middle">{controls_count} controls</text></g>'
        + '<g class="gov accountability" data-box="accountability"><rect x="366" y="392" width="124" height="52" rx="8"/>'
        + '<text class="box-title" x="428" y="414" text-anchor="middle">Accountability</text>'
        + f'<text class="box-detail" x="428" y="432" text-anchor="middle">{actions_count} agent actions</text></g>'
        + "</svg>"
    )


def _chart_figure(number: int, title: str, chart: str, caption: str, figure_class: str) -> str:
    return (
        f'<figure class="chart-figure {figure_class}"><div class="fig-title">Figure {number} · {_esc(title)}</div>'
        f'{chart}<figcaption>{caption}</figcaption></figure>'
    )


FLOW_FIGURE_TITLE = "From candidate use cases to governed agents"


def _flow_figure_caption() -> str:
    _, _, _, _, ineligible = _ranked_data()
    by_tier = []
    for tier, label in (("high", "high"), ("unacceptable", "unacceptable")):
        ids = sorted(row["use_case_id"] for row in ineligible if row["risk_tier"] == tier)
        if ids:
            by_tier.append(f'{", ".join(ids)} {label}')
    exclusions = " · ".join(by_tier)
    return (
        "Every use case passes the internal AI risk gate before ranking; only shortlisted use cases get worked governance, "
        f"while the gate excludes {exclusions}. "
        "Source: data/use_cases.json, data/scoring_config.json, data/controls_trace.json, data/agent_accountability.json · synthetic data."
    )


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
:root{color-scheme:light dark;--bg:#fff;--fg:#202631;--muted:#657080;--surface:#f4f6f8;--border:#d3d9e0;--link:#1456a0;--accent:#087e8b;--matrix-eligible:#cfe8ef;--grid:#d3d9e0;--chip-bg:#e7ebef;--chip-fg:#3d4752;--tier-low-fg:#1b5e20;--tier-low-bg:#e8f5e9;--tier-medium-fg:#7a4a00;--tier-medium-bg:#fff3d6;--tier-high-fg:#b71c1c;--tier-high-bg:#fdeaea;--tier-unacceptable-fg:#fff;--tier-unacceptable-bg:#7f1d1d;--pass-fg:#14532d;--pass-bg:#dff3e5;--fail-fg:#8b1e1e;--fail-bg:#fbe2e2;--not-tested-fg:#475569;--not-tested-bg:#eef2f6;--agent-yes-fg:#075e63;--agent-yes-bg:#d9f2f0;--agent-no-fg:#475569;--agent-no-bg:#eef2f6;--shortlisted-fg:#fff;--shortlisted-bg:#087e8b;--eligible-fg:#087e8b;--eligible-bg:transparent;--not-eligible-fg:#b71c1c;--not-eligible-bg:transparent;--heat-neutral:#f1f5f9;--heat-count-outline:#334155;--heat-low:#e8f5e9;--heat-medium:#fff3d6;--heat-high:#fdeaea;--heat-unacceptable:#7f1d1d;--gated-stroke:#b71c1c;--flow-stage-fill:#f4f6f8;--flow-stage-stroke:#64748b;--flow-gate-fill:#fff3d6;--flow-gate-stroke:#b26a00;--flow-shortlist-fill:#e0f2f1;--flow-shortlist-stroke:#00695c;--flow-ne-fill:#fdeaea;--flow-ne-stroke:#b71c1c;--flow-gov-fill:#fff;--flow-gov-stroke:#00695c;--flow-arrow:#657080}
:root{--hero-start:#0b4f5c;--hero-end:#0f766e;--kpi-assessed:#94a3b8;--kpi-eligible:#14b8a6;--kpi-shortlisted:#0f766e;--kpi-ineligible:#b71c1c}
@media(prefers-color-scheme:dark){:root{--bg:#111820;--fg:#e7edf3;--muted:#a6b1bd;--surface:#1b2530;--border:#354352;--link:#8ab4f8;--accent:#27a9b5;--matrix-eligible:#24444d;--grid:#354352;--chip-bg:#26313d;--chip-fg:#d5dde5;--tier-low-fg:#a7d8ad;--tier-low-bg:#173c29;--tier-medium-fg:#f1d28a;--tier-medium-bg:#4a3d17;--tier-high-fg:#f1a3a3;--tier-high-bg:#4a2226;--tier-unacceptable-fg:#fff;--tier-unacceptable-bg:#450a0a;--pass-fg:#a7d8ad;--pass-bg:#173c29;--fail-fg:#f1a3a3;--fail-bg:#4a2226;--not-tested-fg:#cbd5e1;--not-tested-bg:#26313d;--agent-yes-fg:#8dddd5;--agent-yes-bg:#123d40;--agent-no-fg:#cbd5e1;--agent-no-bg:#26313d;--shortlisted-fg:#062f37;--shortlisted-bg:#54abc2;--eligible-fg:#54c4ca;--eligible-bg:transparent;--not-eligible-fg:#f1a3a3;--not-eligible-bg:transparent;--heat-neutral:#26313d;--heat-count-outline:#0f172a;--heat-low:#173c29;--heat-medium:#4a3d17;--heat-high:#4a2226;--heat-unacceptable:#450a0a;--gated-stroke:#f1a3a3;--flow-stage-fill:#1b2530;--flow-stage-stroke:#64748b;--flow-gate-fill:#4a3d17;--flow-gate-stroke:#f1d28a;--flow-shortlist-fill:#123d40;--flow-shortlist-stroke:#54c4ca;--flow-ne-fill:#4a2226;--flow-ne-stroke:#f1a3a3;--flow-gov-fill:#1b2530;--flow-gov-stroke:#54c4ca;--flow-arrow:#a6b1bd;--hero-start:#062f37;--hero-end:#0b4f5c}}
*{box-sizing:border-box}html,body{margin:0;width:100%;max-width:100%;background:var(--bg);color:var(--fg)}body{font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{width:100%;max-width:1200px;margin:0 auto;padding:0 16px 36px}.hero{width:100%;padding:28px 0 60px;background:linear-gradient(135deg,var(--hero-start) 0%,var(--hero-end) 100%);color:#fff}.hero-inner{width:100%;max-width:1200px;margin:0 auto;padding:0 16px}.hero-pill{display:inline-block;font-size:11px;letter-spacing:.02em;padding:3px 10px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35)}.hero h1{font-size:30px;line-height:1.2;font-weight:700;margin:12px 0 6px}.hero-question{font-size:16px;line-height:1.4;opacity:.9;max-width:680px;margin:0}.hero-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.hero-chip{display:inline-block;font-size:12px;padding:3px 9px;border-radius:999px;background:rgba(255,255,255,.12);white-space:nowrap}.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.hero-button{display:inline-flex;align-items:center;justify-content:center;font-size:13px;padding:8px 14px;border-radius:6px;font-weight:600;text-decoration:none}.hero-button.primary{background:#fff;color:#0b4f5c}.hero-button.outline{background:transparent;border:1px solid #fff;color:#fff}h1{font-size:28px;line-height:1.25;margin:24px 0 8px}h2{font-size:20px;line-height:1.3;margin:36px 0 10px}h3{font-size:16px;line-height:1.35;margin:0}h4{font-size:16px;margin:18px 0 6px}p{margin:8px 0 12px}a{color:var(--link);overflow-wrap:break-word}.topline{font-weight:650}.scenario-line{font-weight:600}.site-links{display:flex;flex-wrap:wrap;gap:6px 16px;margin:12px 0 20px}.context p{margin:4px 0}.how-to-read{display:grid;box-sizing:border-box;width:100%;max-width:1200px;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:28px 0}.read-card{box-sizing:border-box;min-width:0;padding:12px 14px;border-left:3px solid #0f766e;background:var(--surface);border-radius:8px;font-size:13px;line-height:1.45}.read-card-heading{display:flex;align-items:center;gap:8px}.step-badge{display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;width:22px;height:22px;flex:0 0 22px;border-radius:50%;background:#0f766e;color:#fff;font-size:12px;font-weight:700}.read-card-heading strong{font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}.read-card p{margin:8px 0 0}.kpis{display:flex;align-items:stretch;box-sizing:border-box;width:100%;max-width:880px;margin:-40px 0 0;gap:12px;position:relative;z-index:1}.kpi{box-sizing:border-box;flex:1 1 0;min-width:0;background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--kpi-border,var(--border));border-radius:10px;padding:12px 16px;box-shadow:0 6px 20px rgba(0,0,0,.08)}.kpi-assessed{--kpi-border:var(--kpi-assessed)}.kpi-eligible{--kpi-border:var(--kpi-eligible)}.kpi-shortlisted{--kpi-border:var(--kpi-shortlisted)}.kpi-ineligible{--kpi-border:var(--kpi-ineligible)}.kpi-main{display:flex;align-items:baseline;gap:8px;min-width:0}.kpi strong{font-size:24px;font-weight:700;line-height:1.2}.kpi-label{display:block;font-size:13px;min-width:0;white-space:nowrap}.kpi-caption{display:block;font-size:11px;color:var(--muted);margin-top:3px}.scroll{width:100%;max-width:100%;overflow-x:visible;margin:10px 0 18px;border:1px solid var(--border);border-radius:7px}table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:14px;line-height:1.35}th,td{text-align:left;vertical-align:top;padding:6px 3px;border-bottom:1px solid var(--border);overflow-wrap:break-word}th{background:var(--surface);font-weight:700}th.id-cell,td.id-cell,th.num,td.num,.chip,.date{white-space:nowrap}th.num,td.num{text-align:center;font-variant-numeric:tabular-nums}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:color-mix(in srgb,var(--surface) 55%,transparent)}.date{font-size:12px}.status{font-size:10px;padding:2px 3px}.chip{display:inline-block;font-size:12px;padding:2px 7px;border-radius:999px;line-height:1.35;vertical-align:middle;border:1px solid transparent}.tier-low{color:var(--tier-low-fg);background:var(--tier-low-bg)}.tier-medium{color:var(--tier-medium-fg);background:var(--tier-medium-bg)}.tier-high{color:var(--tier-high-fg);background:var(--tier-high-bg)}.tier-unacceptable{color:var(--tier-unacceptable-fg);background:var(--tier-unacceptable-bg)}.result-pass{color:var(--pass-fg);background:var(--pass-bg)}.result-fail{color:var(--fail-fg);background:var(--fail-bg)}.result-not-tested{color:var(--not-tested-fg);background:var(--not-tested-bg)}.agent-yes{color:var(--agent-yes-fg);background:var(--agent-yes-bg)}.agent-no{color:var(--agent-no-fg);background:var(--agent-no-bg)}.status-shortlisted{color:var(--shortlisted-fg);background:var(--shortlisted-bg)}.status-eligible{color:var(--eligible-fg);background:var(--eligible-bg);border-color:var(--eligible-fg)}.status-not-eligible{color:var(--not-eligible-fg);background:var(--not-eligible-bg);border-color:var(--not-eligible-fg)}.family-chip{font-size:11px;margin-top:3px}.evidence-description{display:block;font-size:12px;line-height:1.3;margin-top:4px}.result-detail{display:block;white-space:normal;overflow-wrap:break-word;font-size:12px;margin-top:6px;line-height:1.4}.log-field{font:12px/1.3 ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}.control-requirement{font-size:14px}.control-description{font-size:13px;margin-top:4px}.stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.governance-card{border:1px solid var(--border);border-radius:12px;padding:20px;margin:0 0 24px}.card-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px}.card-heading h3{flex:1 1 240px}.matrix-wrap{width:100%;max-width:600px;margin:0 auto}.chart{display:block;width:100%;height:auto}.chart text{fill:var(--fg);font:12px system-ui,sans-serif}.chart .axis-title{font-size:12px;font-weight:700}.chart .matrix-label{font-size:11px}.chart .gridline{stroke:var(--grid);stroke-width:1}.chart .axis{stroke:var(--muted);stroke-width:1}.chart .shortlisted-point{fill:var(--accent);stroke:var(--accent);stroke-width:2}.chart .eligible-point{fill:var(--matrix-eligible);stroke:var(--accent);stroke-width:2}.chart .gated-point{fill:transparent;stroke:var(--gated-stroke);stroke-width:2;stroke-dasharray:4 3}.heatmap-wrap{width:100%;max-width:520px;margin:0 auto}.heatmap-chart{display:block;width:100%;height:auto}.chart .heat-low{--heat-tier:var(--heat-low)}.chart .heat-medium{--heat-tier:var(--heat-medium)}.chart .heat-high{--heat-tier:var(--heat-high)}.chart .heat-unacceptable{--heat-tier:var(--heat-unacceptable)}.chart .heat-cell{stroke:var(--border);stroke-width:1}.chart .heat-cell.heat-c0{fill:var(--heat-neutral);fill-opacity:1}.chart .heat-cell.heat-c1{fill:var(--heat-tier);fill-opacity:.35}.chart .heat-cell.heat-c2{fill:var(--heat-tier);fill-opacity:.6}.chart .heat-cell.heat-c3{fill:var(--heat-tier);fill-opacity:.85}.chart .heat-count{font-size:18px;font-weight:700}.chart .heat-count.heat-c0{fill:var(--muted)}.chart .heat-count.heat-c1,.chart .heat-count.heat-c2{fill:var(--fg)}.chart .heat-count.heat-c3{fill:#fff;stroke:var(--heat-count-outline);stroke-width:1px;paint-order:stroke}.chart .heat-header{font-size:13px;font-weight:700}.chart .appetite-line{stroke:var(--muted);stroke-width:2;stroke-dasharray:5 4}.chart .appetite-label{font-size:12px;font-weight:700}.chart .heat-text-low{fill:var(--tier-low-fg)}.chart .heat-text-medium{fill:var(--tier-medium-fg)}.chart .heat-text-high{fill:var(--tier-high-fg)}.chart .heat-text-unacceptable{fill:var(--tier-unacceptable-fg)}.chart .appetite-line{stroke:var(--muted);stroke-width:2;stroke-dasharray:5 4}.matrix-legend{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:8px 16px;font-size:12px;margin:2px auto 6px}.legend-item{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}.legend-mark{display:inline-block;width:12px;height:12px;border-radius:50%;background:var(--accent)}.legend-mark.eligible{background:var(--bg);border:1.5px solid var(--accent)}.legend-mark.gated{background:transparent;border:1.5px dashed var(--gated-stroke)}.diagram{display:block;width:100%;max-width:720px;height:auto;margin:0 auto}.chart-figure{margin:10px 0 18px}figcaption{color:var(--muted);font-size:14px}.formula{border:1px solid var(--border);background:var(--surface);padding:12px 14px;border-radius:8px;font:14px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:break-word}footer{border-top:1px solid var(--border);margin-top:30px;padding-top:12px;color:var(--muted)}
 .explorer-panel{box-sizing:border-box;padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--surface);margin:12px 0}.explorer-panel h3{margin:0}.explorer-hint{font-size:13px;color:var(--muted);margin:4px 0 12px}.explorer-controls{display:grid;box-sizing:border-box;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.weight-control{box-sizing:border-box;min-width:0}.weight-label-row{display:flex;justify-content:space-between;gap:8px;font-size:13px}.weight-label-row output{font-variant-numeric:tabular-nums}.weight-control input[type=range]{display:block;width:100%;margin:8px 0 0;accent-color:#0f766e}.risk-fieldset{box-sizing:border-box;min-width:0;margin:0;padding:0;border:0}.risk-fieldset legend{font-size:13px;margin-bottom:6px}.appetite-options{display:flex;gap:6px}.appetite-option{position:relative;flex:1 1 0;min-width:0;text-align:center;font-size:13px}.appetite-option input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}.appetite-option span{display:block;padding:5px 8px;border:1px solid var(--border);border-radius:6px;cursor:pointer}.appetite-option input:checked+span{background:#0f766e;color:#fff;border-color:#0f766e}.appetite-option input:focus-visible+span{outline:2px solid #0b4f5c;outline-offset:2px}.explorer-actions{display:flex;align-items:center;gap:12px;margin-top:12px}.stage-filters{display:flex;flex-wrap:wrap;gap:6px}.stage-chip,.reset-ranking{font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;border:1px solid var(--border);border-radius:999px;padding:5px 10px;background:var(--bg);color:var(--fg);cursor:pointer}.stage-chip{white-space:nowrap}.stage-chip[aria-pressed=true]{background:#0f766e;color:#fff;border-color:#0f766e}.reset-ranking{margin-left:auto;white-space:nowrap}.explorer-formula{margin-top:12px}.weight-error{color:#b71c1c;font-size:13px;margin:6px 0 0}.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.row-detail{box-sizing:border-box;margin:12px 0 0;padding:16px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}.detail-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.detail-heading h3{margin:0}.detail-close{border:1px solid var(--border);border-radius:6px;padding:4px 10px;background:var(--bg);color:var(--fg);cursor:pointer}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px;margin-top:12px}.detail-field{min-width:0;font-size:13px;overflow-wrap:break-word}.detail-field strong{display:block;font-size:12px;color:var(--muted)}.detail-rationales{margin-top:12px}.detail-rationales p{font-size:13px;margin:6px 0}.detail-governance{font-size:13px;margin-top:12px}.ranked-table tr.is-selected td,.ineligible-table tr.is-selected td{background:color-mix(in srgb,#0f766e 10%,var(--surface))}.ranked-table tr.is-selected td:first-child,.ineligible-table tr.is-selected td:first-child{border-left:3px solid #0f766e}.formula-error{color:#b71c1c}
@media(min-width:1100px){.explorer-controls{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:640px) and (max-width:1099px){.explorer-controls{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:639px){.explorer-controls{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}}
@media(max-width:759px){.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.how-to-read{grid-template-columns:1fr}.scroll{overflow-x:auto}}
@media(max-width:419px){.kpis{grid-template-columns:1fr}}
@media(max-width:759px){.hero h1{font-size:24px}}
.value-chain-flow .box-title{font:700 13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:var(--fg)}
.value-chain-flow .box-detail{font:12px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:var(--fg)}
.value-chain-flow .stage rect{fill:var(--flow-stage-fill);stroke:var(--flow-stage-stroke);stroke-width:1.4}
.value-chain-flow .gate rect{fill:var(--flow-gate-fill);stroke:var(--flow-gate-stroke);stroke-width:1.6}
.value-chain-flow .shortlist rect{fill:var(--flow-shortlist-fill);stroke:var(--flow-shortlist-stroke);stroke-width:1.6}
.value-chain-flow .ne rect{fill:var(--flow-ne-fill);stroke:var(--flow-ne-stroke);stroke-width:1.6;stroke-dasharray:5 3}
.value-chain-flow .gov rect{fill:var(--flow-gov-fill);stroke:var(--flow-gov-stroke);stroke-width:1.6}
.value-chain-flow .flow-arrow{fill:none;stroke:var(--flow-arrow);stroke-width:1.5}
.value-chain-flow .flow-arrow.dashed{stroke-dasharray:5 4}
.value-chain-flow .arrowhead{fill:var(--flow-arrow)}
body:not(.cs-page) #value-chain .flow-figure{margin:16px 0 24px;max-width:720px}
.chart-figure{box-sizing:border-box;width:100%;max-width:720px;margin:24px auto;border-top:1px solid var(--border);padding-top:12px}
.chart-figure .fig-title,.chart-figure figcaption{box-sizing:border-box;width:100%;max-width:var(--figure-chart-width,720px);margin-left:auto;margin-right:auto;text-align:left}
.fig-title{font-size:14px;font-weight:700;margin-bottom:8px}
.chart-figure figcaption{color:var(--muted);font-size:12px;max-width:var(--figure-chart-width,720px);margin-top:8px}
.flow-figure{--figure-chart-width:720px}
.matrix-figure{--figure-chart-width:600px}
.heatmap-figure{--figure-chart-width:520px}
</style>"""


def _case_study_css() -> str:
    styles = _css()
    dashboard_selectors = (
        "main", ".hero-button.primary", ".hero-button.outline", ".hero-question", ".hero-actions",
        ".hero-chips", ".hero-inner", ".hero-button", ".hero-pill", ".hero h1", ".hero-chip", ".hero",
    )
    for selector in dashboard_selectors:
        styles = styles.replace(f"{selector}{{", f"body:not(.cs-page) {selector}{{")
    extra = """body.cs-page{font-size:15px;line-height:1.6}body.cs-page .hero{width:100%;padding:20px 0 28px;background:linear-gradient(135deg,var(--hero-start) 0%,var(--hero-end) 100%);color:#fff}body.cs-page .cs-wrap{box-sizing:border-box;width:100%;max-width:880px;margin-left:auto;margin-right:auto;padding-left:24px;padding-right:24px}body.cs-page .hero-pill{display:inline-block;font-size:11px;letter-spacing:.02em;padding:3px 10px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35)}body.cs-page .hero h1{font-size:26px;line-height:1.2;font-weight:700;margin:12px 0 6px}body.cs-page .hero-question{font-size:16px;line-height:1.4;opacity:.9;max-width:680px;margin:0}body.cs-page .hero-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}body.cs-page .hero-chip{display:inline-block;font-size:12px;padding:3px 9px;border-radius:999px;background:rgba(255,255,255,.12);white-space:nowrap}body.cs-page .hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}body.cs-page .hero-button{display:inline-flex;align-items:center;justify-content:center;font-size:13px;padding:8px 14px;border-radius:6px;font-weight:600;text-decoration:none}body.cs-page .hero-button.primary{background:#fff;color:#0b4f5c}body.cs-page .hero-button.outline{background:transparent;border:1px solid #fff;color:#fff}.cs-page .case-study-hero .hero-inner{max-width:880px}.cs-page .article-main{padding-top:28px;padding-bottom:36px}.cs-page .article-main>.case-study-section:first-child h2{margin-top:0}.cs-page .article-main h2{font-size:20px}.cs-page .article-main h3{font-size:16px}.cs-page .case-study-section{box-sizing:border-box;width:100%;max-width:100%;margin:0 0 28px}.cs-page .case-study-section .how-to-read{box-sizing:border-box;width:100%;max-width:100%;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 18px}.cs-page .read-card{box-sizing:border-box;min-width:0}.cs-page .case-study-card{box-sizing:border-box;width:100%;max-width:100%;border:1px solid var(--border);border-radius:12px;padding:18px;margin:18px 0}.cs-page .case-study-card h3{margin:0}.cs-page .permission-list,.cs-page .finding-list{padding-left:22px}.cs-page .permission-list li,.cs-page .finding-list li{margin:5px 0}.cs-page .two-columns{display:grid;box-sizing:border-box;width:100%;max-width:100%;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.cs-page .two-columns>div{box-sizing:border-box;min-width:0;padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:10px}.cs-page figure{box-sizing:border-box;width:100%;max-width:100%;margin:16px 0 24px}.cs-page .flow-figure{max-width:100%}.cs-page .chart-figure .fig-title,.cs-page .chart-figure figcaption{margin-left:0;margin-right:0}.cs-page .diagram{max-width:100%;margin-left:0;margin-right:0}.cs-page .case-study-footer{margin-top:36px}@media(max-width:759px){body.cs-page .hero h1{font-size:22px}.cs-page .case-study-section .how-to-read,.cs-page .two-columns{grid-template-columns:1fr}}"""
    return styles.replace("</style>", extra + "</style>")


def _case_study_html_content() -> str:
    config, scenario, cases, _, medium_ineligible = _ranked_data()
    controls, actions = load_controls(), load_actions()
    high_ranked, _ = rank(cases, config["default_weights"], "high")
    medium_ranked, _ = rank(cases, config["default_weights"], "medium")
    case_by_id = {case["use_case_id"]: case for case in cases}
    high_by_id = {case["use_case_id"]: case for case in high_ranked}
    medium_top = medium_ranked[0]
    high_top = high_ranked[0]
    shortlisted_agents = [row for row in medium_ranked if row["shortlisted"] and case_by_id[row["use_case_id"]]["worked_governance"]]
    shortlisted_controls = sum(len(_controls_for(row["use_case_id"], controls)) for row in shortlisted_agents)
    outcome = (
        f'{len(cases)} use cases assessed · the risk gate removed {len(medium_ineligible)}, including the top-scoring idea at High appetite '
        f'({_esc(high_top["use_case_id"])}) · {len(shortlisted_agents)} shortlisted agents carry {shortlisted_controls} traced controls.'
    )
    hero_chips = "".join(
        f'<span class="hero-chip">{_esc(value)}</span>'
        for value in (scenario["market"], scenario["currency"], *scenario["lines"])
    )
    hero = (
        '<header class="hero case-study-hero"><div class="hero-inner cs-wrap">'
        '<span class="hero-pill">Case study · simulated scenario · synthetic data · illustrative, not legal advice</span>'
        '<h1>Life and protection AI: which use cases go forward, under what controls</h1>'
        f'<p class="hero-question case-study-outcome">{outcome}</p><div class="hero-chips">{hero_chips}</div>'
        '<div class="hero-actions"><a class="hero-button primary" href="../">Open the live dashboard</a>'
        '<a class="hero-button outline" href="https://github.com/kakali-bandyopadhyay/life-ai-value-chain">Code</a></div>'
        '</div></header>'
    )

    problem = (
        '<section class="case-study-section" id="problem"><h2>The problem</h2>'
        '<p>A life and protection insurer has more candidate AI use cases than it can deliver. '
        'The highest-value ideas are often the ones that act on customers, through pricing, acceptance or claims, '
        'where an error harms people. Governance is often added after a build instead of deciding whether it should be built.</p></section>'
    )

    present_stages = [stage for stage in STAGES if any(case["value_chain_stage"] == stage for case in cases)]
    stage_names = [STAGE_LABELS[stage].lower() for stage in present_stages]
    stage_summary = ", ".join(stage_names[:-1]) + (f" and {stage_names[-1]}" if len(stage_names) > 1 else (stage_names[0] if stage_names else "no value-chain stages"))
    worked_count = sum(case["worked_governance"] for case in cases)
    count_words = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    approach = (
        '<section class="case-study-section" id="approach"><h2>The approach</h2>'
        + f'{_approach_strip(len(cases), stage_summary, count_words.get(worked_count, str(worked_count)))}'
        + _chart_figure(1, FLOW_FIGURE_TITLE, _value_chain_svg(), _flow_figure_caption(), "flow-figure")
        + '</section>'
    )

    high_ids = sorted(case["use_case_id"] for case in medium_ineligible if case["risk_tier"] == "high")
    unacceptable_ids = sorted(case["use_case_id"] for case in medium_ineligible if case["risk_tier"] == "unacceptable")
    tier_groups = []
    if high_ids:
        tier_groups.append(f'{_esc(", ".join(high_ids))} high')
    if unacceptable_ids:
        tier_groups.append(f'{_esc(", ".join(unacceptable_ids))} unacceptable')
    tier_summary = "; ".join(tier_groups)
    gate_paragraph = (
        f'<p>At Medium appetite, {len(cases) - len(medium_ineligible)} of {len(cases)} use cases are eligible. '
        f'The gate removes {len(medium_ineligible)}: {tier_summary}. At High appetite the top-ranked use case would be '
        f'{_esc(high_top["use_case_id"])} ({high_top["score"]:.1f}); at Medium it is not eligible, so no weighting can bring it back.</p>'
    )
    gate_rows = []
    gate_ids = [case["use_case_id"] for case in sorted(medium_ineligible, key=lambda row: row["use_case_id"])] + [medium_top["use_case_id"]]
    for use_case_id in gate_ids:
        case = case_by_id[use_case_id]
        high_case = high_by_id.get(use_case_id)
        score_value = f'{high_case["score"]:.1f}' if high_case else "Not eligible at any appetite"
        status = "Ranked #1 at Medium" if use_case_id == medium_top["use_case_id"] else "Not eligible"
        gate_rows.append([
            f'<strong>{_esc(use_case_id)}</strong><br>{_esc(case["name"])}',
            _risk_html(case["risk_tier"]),
            _esc(score_value),
            _esc(status),
        ])
    gate_table = _html_table(
        ["Use case", "Internal AI risk tier", "Score at High appetite", "Status at Medium"],
        gate_rows,
        widths=(14, 26, 25, 35),
        classes="gate-table",
    )
    gate = f'<section class="case-study-section" id="gate"><h2>What the gate changed</h2>{gate_paragraph}{gate_table}</section>'

    agent_cards = []
    for case in sorted((row for row in cases if row["worked_governance"]), key=lambda row: row["use_case_id"]):
        use_case_id = case["use_case_id"]
        case_controls = _controls_for(use_case_id, controls)
        case_actions = _actions_for(use_case_id, actions)
        permitted = [row for row in case_actions if row["agent_allowed"] == "yes"]
        prohibited = [row for row in case_actions if row["agent_allowed"] != "yes"]
        permission_list = lambda rows: "".join(
            f'<li><strong>{_esc(row["action"].title())}:</strong> {_esc(row["tool_permissions"])} '
            f'(accountable role: {_esc(row["accountable_human_role"])})</li>'
            for row in rows
        )
        findings = []
        for control in case_controls:
            if control["test_result"] == "fail":
                findings.append(
                    f'<li><strong>{_esc(control["control_id"])}</strong> — {_esc(control["requirement"])} '
                    f'<span>Remediation: {_esc(control["remediation_note"])}</span></li>'
                )
            if control.get("exception_id"):
                findings.append(
                    f'<li><strong>{_esc(control["exception_id"])}</strong> — {_esc(control["exception_reason"])}</li>'
                )
        open_findings = "".join(findings) or "<li>No open findings.</li>"
        agent_cards.append(
            f'<article class="case-study-card" id="worked-{_esc(use_case_id)}">'
            f'<div class="card-heading"><span class="chip">{_esc(use_case_id)}</span><h3>{_esc(case["name"])}</h3>'
            f'{_risk_html(case["risk_tier"])}</div>'
            f'<p><strong>What it does:</strong> {_esc(case["description"])}</p>'
            f'<h4>The agent may</h4><ul class="permission-list">{permission_list(permitted)}</ul>'
            f'<h4>The agent may not</h4><ul class="permission-list">{permission_list(prohibited)}</ul>'
            f'{_stats_html(case_controls)}<h4>Open findings</h4><ul class="finding-list">{open_findings}</ul>'
            f'<p><a href="../#{_esc(use_case_id)}">Full controls trace and accountability</a></p></article>'
        )
    governance = '<section class="case-study-section" id="worked-agents"><h2>The two worked agents</h2>' + "".join(agent_cards) + "</section>"

    reality = (
        '<section class="case-study-section" id="real-and-simulated"><h2>What is real and what is simulated</h2>'
        '<div class="two-columns"><div><h3>Real</h3><ul>'
        '<li>The gate-then-rank logic and its tests.</li>'
        '<li>The browser ranking checked against the Python reference by a parity test.</li>'
        '<li>A reproducible build: the same inputs produce identical files.</li>'
        '</ul></div><div><h3>Simulated</h3><ul>'
        '<li>The insurer, use cases, scores, controls, test results and evidence.</li>'
        '<li>Evidence items are labelled “Design record” or “Simulated evidence”.</li>'
        '</ul></div></div></section>'
    )
    limits = (
        '<section class="case-study-section" id="limits"><h2>Limits and next steps</h2><ul>'
        '<li>The internal AI risk tier is an appetite measure, not a regulatory classification.</li>'
        '<li>No law or regulator is interpreted.</li>'
        '<li>No live model outputs were evaluated.</li>'
        '<li>Next: map controls to applicable requirements with Legal/Compliance, evaluate real model outputs for the two shortlisted agents, and extend to further lines.</li>'
        '</ul></section>'
    )
    source_links = " · ".join(f'<a href="{_repo_url(path)}">{_esc(label)}</a>' for label, path in _links())
    footer = f'<footer class="case-study-footer"><p>{_esc(BOUNDARY)}</p><p>MIT licence</p><p>Source data: {source_links}</p></footer>'
    return hero + f'<main class="article-main cs-wrap">{problem}{approach}{gate}{governance}{reality}{limits}{footer}</main>'


def _approach_strip(case_count: int, stage_summary: str, worked_count_text: str) -> str:
    return (
        '<section id="context" class="how-to-read" aria-label="How to read this page">'
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">1</span><strong>Assess</strong></div>'
        f'<p>{case_count} AI use cases across {_esc(stage_summary)}.</p></article>'
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">2</span><strong>Gate</strong></div>'
        "<p>Each must pass the insurer's internal AI risk tier – its own appetite measure, not a regulatory classification.</p></article>"
        '<article class="read-card"><div class="read-card-heading"><span class="step-badge">3</span><strong>Prioritise and govern</strong></div>'
        f'<p>Eligible use cases are ranked by weighted score; {worked_count_text} shortlisted ones carry worked controls and agent accountability.</p></article>'
        '</section>'
    )


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
    chart = '<div class="matrix-wrap">' + "".join(pieces) + "</div>" + legend
    caption = (
        "Bubble size shows data readiness; dashed bubbles are blocked by the risk gate at "
        f'<span id="matrix-caption-appetite">{_esc(RISK_LABELS[appetite])}</span> appetite, whatever their score. '
        "Source: data/use_cases.json · synthetic data."
    )
    figure = _chart_figure(2, "Priority matrix: value against feasibility", chart, caption, "matrix-figure")
    return '<section id="matrix"><h2>Priority matrix</h2>' + figure + "</section>"


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
    caption = (
        "Cells right of the dashed line are above the "
        f'<span id="heatmap-caption-appetite">{_esc(RISK_LABELS[appetite])}</span> appetite and cannot be ranked. '
        "Source: data/use_cases.json · synthetic data."
    )
    figure = _chart_figure(3, "Use cases by value-chain stage and internal AI risk tier", "".join(pieces), caption, "heatmap-figure")
    return '<section id="heatmap"><h2>Risk heatmap</h2>' + figure + "</section>"


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
        '<a class="hero-button outline" href="#governance">Worked governance</a>'
        '<a class="hero-button outline" href="case-study/">Read the case study</a></div>'
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
    body.append(_approach_strip(len(cases), stage_summary, worked_count_text))
    body.append(f'<section id="value-chain"><h2>Value chain</h2>{_chart_figure(1, FLOW_FIGURE_TITLE, _value_chain_svg(), _flow_figure_caption(), "flow-figure")}</section>')
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
    html_path, markdown_path = target_dir / "index.html", target_dir / "ASSESSMENT.md"
    case_study_path = target_dir / "case-study" / "index.html"
    case_study_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_bytes(_html_content().replace("\r\n", "\n").encode("utf-8"))
    markdown_path.write_bytes(_markdown_content().replace("\r\n", "\n").encode("utf-8"))
    case_study_html = CASE_STUDY_PAGE_TEMPLATE.format(
        title="Life and protection AI: which use cases go forward, under what controls",
        styles=_case_study_css(),
        content=_case_study_html_content(),
    )
    case_study_path.write_bytes(case_study_html.replace("\r\n", "\n").encode("utf-8"))
    return html_path, markdown_path
