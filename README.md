# Life and protection AI value-chain assessment

Simulated scenario · synthetic data · illustrative, not legal advice

## What it is

This repository describes a simulated UK life and protection insurer assessing 14 candidate AI use cases across distribution, underwriting, policy admin, servicing and claims. An internal AI risk gate is applied before eligible use cases are ranked. Two shortlisted use cases carry worked governance packs with a controls trace and agent accountability. Live page: [https://kakali-bandyopadhyay.github.io/life-ai-value-chain/](https://kakali-bandyopadhyay.github.io/life-ai-value-chain/).

## How the assessment works

A use case is eligible only when its internal AI risk tier is at or below the selected appetite; Unacceptable is never eligible, and changing weights cannot change eligibility. The score is `round(100 × (5·value + 3·feasibility + 2·data readiness) ÷ (5 × (5 + 3 + 2)), 1)` with the default weights of value 5, feasibility 3 and data readiness 2. At build time, the default appetite (Medium), weights, allowed appetite settings and shortlist size (5) are read from [data/scoring_config.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/scoring_config.json). Ties are broken by value descending, then data readiness descending, then use case ID ascending; the top five eligible use cases are shortlisted. The browser panel uses the same rules; a [parity test](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/tests/test_parity.py) checks the JavaScript ranking against the [Python reference](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/ai_value_chain/scoring.py).

## Worked governance

- **VC-01 — Underwriting Evidence Summariser:** It may prepare a cited evidence summary for the underwriter, but may not accept or decline an application or set terms, exclusions or premium. Its controls record 9 pass, 1 fail, 2 not tested and 1 exception.
- **VC-05 — Policy-Admin Data Exception Agent:** It may identify policy data exceptions and recommend evidence-backed corrections, but may not approve or write corrections to policy administration records. Its controls record 8 pass, 2 fail, 2 not tested and 1 exception.

“Design record” links point to [data/agent_accountability.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json). Other evidence is labelled “Simulated evidence”; controls with no evidence retain the “No evidence – exception” label.

## Quickstart

Run these commands in PowerShell from the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest
python -m ai_value_chain validate
python -m ai_value_chain assess --appetite high --weights 5,3,2
python -m ai_value_chain build
```

## File map

- [data/](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/tree/main/data/) contains five JSON files:
  - [use_cases.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/use_cases.json) — candidate use cases and scoring inputs.
  - [scoring_config.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/scoring_config.json) — default weights, appetite and shortlist settings.
  - [scenario.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/scenario.json) — scenario title, insurer description, market, currency and lines.
  - [controls_trace.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/controls_trace.json) — worked-use-case control requirements, evidence and results.
  - [agent_accountability.json](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) — permitted actions, tool boundaries and accountable roles.
- [ai_value_chain/](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/tree/main/ai_value_chain/) contains [data.py](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/ai_value_chain/data.py), [scoring.py](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/ai_value_chain/scoring.py), [render.py](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/ai_value_chain/render.py) and [__main__.py](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/ai_value_chain/__main__.py).
- [docs/](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/tree/main/docs/) contains the [live dashboard source](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/docs/index.html), [assessment report](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/docs/ASSESSMENT.md), [browser ranking functions](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/docs/rank.js) and [interactive panel](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/docs/app.js).
- [tests/](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/tree/main/tests/) contains the rendering, scoring, data validation and JavaScript parity tests, plus the Node parity runner.

## Boundaries

The data and policies are synthetic and illustrative. The internal AI risk tier is the simulated insurer’s own appetite measure, not a regulatory classification. No law or regulator is named or interpreted. The material needs Legal/Compliance validation before any real use, is not production-ready, and is not any firm’s policy or method.

## Licence

MIT: [LICENSE](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/LICENSE).
