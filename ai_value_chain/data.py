"""Load and validate the synthetic assessment data files."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPO_ROOT = DATA_DIR.parent
AS_OF_DATE = date(2026, 11, 13)

STAGES = {"distribution", "underwriting", "policy_admin", "servicing", "claims"}
LINES = {"individual life", "group life & disability", "income protection", "annuities", "all"}
AI_PATTERNS = {
    "document extraction", "RAG knowledge", "classification/triage",
    "agentic workflow", "generative drafting", "analytics/prediction",
}
RISK_TIERS = {"low", "medium", "high", "unacceptable"}
REQUIREMENT_FAMILIES = {
    "data protection", "model risk", "operational resilience", "access control",
    "record keeping", "change management", "customer outcomes",
}
TEST_RESULTS = {"pass", "fail", "not tested"}
ACCOUNTABILITY_ACTIONS = {"recommend", "approve", "execute", "override", "stop"}
GITHUB_BLOB_PREFIX = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/"


def _load(filename: str) -> dict[str, Any]:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def load_use_cases() -> list[dict[str, Any]]:
    """Load use case rows without changing their source file."""
    return _load("use_cases.json")["use_cases"]


def load_controls() -> list[dict[str, Any]]:
    """Load controls trace rows without changing their source file."""
    return _load("controls_trace.json")["controls"]


def load_actions() -> list[dict[str, Any]]:
    """Load agent accountability rows without changing their source file."""
    return _load("agent_accountability.json")["actions"]


def load_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load use cases, controls and accountability actions."""
    return load_use_cases(), load_controls(), load_actions()


def _is_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(
    use_cases: list[dict[str, Any]] | None = None,
    controls: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Return validation errors for supplied rows or the repository's data files."""
    if use_cases is None or controls is None or actions is None:
        loaded_cases, loaded_controls, loaded_actions = load_data()
        use_cases = loaded_cases if use_cases is None else use_cases
        controls = loaded_controls if controls is None else controls
        actions = loaded_actions if actions is None else actions

    errors: list[str] = []
    case_ids = [row.get("use_case_id") for row in use_cases]
    case_id_set = set(case_ids)
    if len(case_id_set) != len(case_ids):
        errors.append("Use case IDs must be unique")

    for row in use_cases:
        use_case_id = row.get("use_case_id", "<missing>")
        if row.get("value_chain_stage") not in STAGES:
            errors.append(f"{use_case_id}: invalid value_chain_stage")
        if row.get("line_of_business") not in LINES:
            errors.append(f"{use_case_id}: invalid line_of_business")
        if row.get("ai_pattern") not in AI_PATTERNS:
            errors.append(f"{use_case_id}: invalid ai_pattern")
        if row.get("risk_tier") not in RISK_TIERS:
            errors.append(f"{use_case_id}: invalid risk_tier")
        if not isinstance(row.get("worked_governance"), bool):
            errors.append(f"{use_case_id}: worked_governance must be a boolean")
        if row.get("evidence_label") != "synthetic":
            errors.append(f"{use_case_id}: evidence_label must be synthetic")
        if row.get("market") != "UK":
            errors.append(f"{use_case_id}: market must be UK")
        for field in ("value", "feasibility", "data_readiness"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
                errors.append(f"{use_case_id}: {field} must be an integer from 1 to 5")

    stage_counts = {stage: sum(row.get("value_chain_stage") == stage for row in use_cases) for stage in STAGES}
    for stage, count in stage_counts.items():
        if count < 2:
            errors.append(f"At least two use cases are required for stage {stage}")

    worked_ids = {
        row.get("use_case_id") for row in use_cases if row.get("worked_governance") is True
    }
    if len(worked_ids) != 2:
        errors.append("Exactly two use cases must have worked_governance true")

    control_ids = [row.get("control_id") for row in controls]
    if len(set(control_ids)) != len(control_ids):
        errors.append("Control IDs must be unique")

    exception_ids: list[str] = []
    for row in controls:
        control_id = row.get("control_id", "<missing>")
        use_case_id = row.get("use_case_id")
        if use_case_id not in worked_ids:
            errors.append(f"{control_id}: control use_case_id must be a worked use case")
        family = row.get("requirement_family")
        if family not in REQUIREMENT_FAMILIES:
            errors.append(f"{control_id}: invalid requirement_family")
        test_result = row.get("test_result")
        if test_result not in TEST_RESULTS:
            errors.append(f"{control_id}: invalid test_result")

        evidence_ref = row.get("evidence_ref")
        exception_id = row.get("exception_id")
        if _is_nonempty(exception_id):
            exception_ids.append(exception_id)
        if evidence_ref == "none" and not _is_nonempty(exception_id):
            errors.append(f"{control_id}: evidence_ref none requires exception_id")
        elif evidence_ref == "simulated":
            description = row.get("evidence_description")
            if not _is_nonempty(description) or not description.strip().endswith("(simulated)"):
                errors.append(f"{control_id}: simulated evidence requires evidence_description ending with (simulated)")
        elif isinstance(evidence_ref, str) and evidence_ref.startswith("http"):
            if not evidence_ref.startswith(GITHUB_BLOB_PREFIX):
                errors.append(f"{control_id}: evidence URL must use the repository GitHub blob prefix")
            else:
                relative_path = evidence_ref[len(GITHUB_BLOB_PREFIX):].split("#", 1)[0].split("?", 1)[0]
                target = (REPO_ROOT / Path(relative_path)).resolve()
                try:
                    target.relative_to(REPO_ROOT.resolve())
                    exists = target.is_file()
                except ValueError:
                    exists = False
                if not exists:
                    errors.append(f"{control_id}: evidence URL path does not exist in this repository")
        elif evidence_ref not in {"none", "simulated"}:
            errors.append(f"{control_id}: evidence_ref must be none, simulated, or a repository URL")

        if test_result == "fail" and not (_is_nonempty(exception_id) or _is_nonempty(row.get("remediation_note"))):
            errors.append(f"{control_id}: failed control requires exception_id or remediation_note")
        review_date = row.get("review_date")
        if isinstance(review_date, str):
            try:
                parsed_date = date.fromisoformat(review_date)
            except ValueError:
                errors.append(f"{control_id}: review_date must be an ISO date")
            else:
                if parsed_date > AS_OF_DATE and test_result != "not tested":
                    errors.append(f"{control_id}: future review_date requires test_result not tested")
        else:
            errors.append(f"{control_id}: review_date must be an ISO date")

    if len(exception_ids) != 2 or len(set(exception_ids)) != 2:
        errors.append("Exactly two unique exception IDs are required")

    actions_by_case: dict[Any, list[dict[str, Any]]] = {}
    for index, row in enumerate(actions, start=1):
        action = row.get("action")
        use_case_id = row.get("use_case_id")
        if use_case_id not in worked_ids:
            errors.append(f"Action {index}: action use_case_id must be a worked use case")
        actions_by_case.setdefault(use_case_id, []).append(row)
        if action not in ACCOUNTABILITY_ACTIONS:
            errors.append(f"Action {index}: invalid action")
        if row.get("agent_allowed") not in {"yes", "no"}:
            errors.append(f"Action {index}: agent_allowed must be yes or no")
        if action in {"approve", "execute"} and row.get("agent_allowed") != "no":
            errors.append(f"Action {index}: {action} agent_allowed must be no")
        if not _is_nonempty(row.get("accountable_human_role")):
            errors.append(f"Action {index}: accountable_human_role is required")
    for use_case_id in worked_ids:
        count = len(actions_by_case.get(use_case_id, []))
        if count != 5:
            errors.append(f"{use_case_id}: exactly five accountability actions are required")

    return errors
