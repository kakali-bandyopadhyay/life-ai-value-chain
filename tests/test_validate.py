"""Validation tests using in-memory copies of the checked-in data."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ai_value_chain.data import load_data, validate


@pytest.fixture
def data_rows():
    return deepcopy(load_data())


def errors_after(data_rows, mutate):
    use_cases, controls, actions = data_rows
    mutate(use_cases, controls, actions)
    return validate(use_cases, controls, actions)


def test_real_data_validates():
    assert validate() == []


def test_duplicate_use_case_id(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[1].update(use_case_id=cases[0]["use_case_id"]))
    assert any("Use case IDs must be unique" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("value_chain_stage", "other", "invalid value_chain_stage"),
        ("line_of_business", "other", "invalid line_of_business"),
        ("ai_pattern", "other", "invalid ai_pattern"),
        ("risk_tier", "other", "invalid risk_tier"),
    ],
)
def test_use_case_enum_rules(data_rows, field, value, message):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[0].update({field: value}))
    assert any(message in error for error in errors)


def test_minimum_two_use_cases_per_stage(data_rows):
    errors = errors_after(
        data_rows,
        lambda cases, controls, actions: [row.update(value_chain_stage="claims") for row in cases if row["value_chain_stage"] == "distribution"],
    )
    assert any("At least two use cases are required for stage distribution" in error for error in errors)


def test_exactly_two_worked_use_cases(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: next(row for row in cases if row["use_case_id"] == "VC-02").update(worked_governance=True))
    assert any("Exactly two use cases" in error for error in errors)


def test_worked_governance_must_be_boolean(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[0].update(worked_governance="true"))
    assert any("worked_governance must be a boolean" in error for error in errors)


def test_evidence_label_must_be_synthetic(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[0].update(evidence_label="real"))
    assert any("evidence_label must be synthetic" in error for error in errors)


@pytest.mark.parametrize("bad_value", [0, 6, 1.5, True, "3"])
@pytest.mark.parametrize("field", ["value", "feasibility", "data_readiness"])
def test_score_fields_must_be_integer_one_to_five(data_rows, field, bad_value):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[0].update({field: bad_value}))
    assert any(f"{field} must be an integer from 1 to 5" in error for error in errors)


def test_market_must_be_uk(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: cases[0].update(market="US"))
    assert any("market must be UK" in error for error in errors)


def test_duplicate_control_id(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[1].update(control_id=controls[0]["control_id"]))
    assert any("Control IDs must be unique" in error for error in errors)


def test_control_must_belong_to_worked_use_case(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(use_case_id="VC-02"))
    assert any("control use_case_id must be a worked use case" in error for error in errors)


def test_requirement_family_enum(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(requirement_family="other"))
    assert any("invalid requirement_family" in error for error in errors)


def test_test_result_enum(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(test_result="unknown"))
    assert any("invalid test_result" in error for error in errors)


def test_none_evidence_requires_exception(data_rows):
    errors = errors_after(
        data_rows,
        lambda cases, controls, actions: (controls[0].update(evidence_ref="none", exception_id=""), controls[1].update(exception_id="EX-OTHER")),
    )
    assert any("evidence_ref none requires exception_id" in error for error in errors)


def test_simulated_evidence_description_must_end_with_marker(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(evidence_ref="simulated", evidence_description="Simulated evidence"))
    assert any("ending with (simulated)" in error for error in errors)


def test_evidence_url_must_use_repository_prefix(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(evidence_ref="https://example.com/design.md"))
    assert any("repository GitHub blob prefix" in error for error in errors)


def test_evidence_url_path_must_exist(data_rows):
    url = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/not-a-real-file.md"
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(evidence_ref=url))
    assert any("evidence URL path does not exist" in error for error in errors)


def test_evidence_reference_must_be_supported(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(evidence_ref="unknown"))
    assert any("evidence_ref must be none, simulated, or a repository URL" in error for error in errors)


def test_failed_control_requires_exception_or_remediation(data_rows):
    failed = next(row for row in data_rows[1] if row["test_result"] == "fail")

    def mutate(cases, controls, actions):
        failed_row = next(row for row in controls if row["control_id"] == failed["control_id"])
        failed_row.update(exception_id="", remediation_note="")
        for row in controls:
            row["exception_id"] = ""
        eligible_rows = [row for row in controls if row["control_id"] != failed["control_id"]]
        eligible_rows[0].update(exception_id="EX-ONE")
        eligible_rows[1].update(exception_id="EX-TWO")

    errors = errors_after(data_rows, mutate)
    assert any("failed control requires exception_id or remediation_note" in error for error in errors)


def test_future_review_date_requires_not_tested(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(review_date="2027-01-01", test_result="pass"))
    assert any("future review_date requires test_result not tested" in error for error in errors)


def test_review_date_must_be_iso_date(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: controls[0].update(review_date="not-a-date"))
    assert any("review_date must be an ISO date" in error for error in errors)


def test_exception_ids_must_be_exactly_two_and_unique(data_rows):
    def mutate(cases, controls, actions):
        exception_rows = [row for row in controls if row["exception_id"]]
        exception_rows[1]["exception_id"] = exception_rows[0]["exception_id"]

    errors = errors_after(data_rows, mutate)
    assert any("Exactly two unique exception IDs" in error for error in errors)


def test_action_must_belong_to_worked_use_case(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: actions[0].update(use_case_id="VC-02"))
    assert any("action use_case_id must be a worked use case" in error for error in errors)


def test_accountability_action_enum(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: actions[0].update(action="other"))
    assert any("invalid action" in error for error in errors)


def test_agent_allowed_enum(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: actions[0].update(agent_allowed="sometimes"))
    assert any("agent_allowed must be yes or no" in error for error in errors)


@pytest.mark.parametrize("action", ["approve", "execute"])
def test_agent_cannot_approve_or_execute(action, data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: next(row for row in actions if row["action"] == action).update(agent_allowed="yes"))
    assert any(f"{action} agent_allowed must be no" in error for error in errors)


def test_accountable_human_role_required(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: actions[0].update(accountable_human_role=" "))
    assert any("accountable_human_role is required" in error for error in errors)


def test_exactly_five_actions_per_worked_use_case(data_rows):
    errors = errors_after(data_rows, lambda cases, controls, actions: actions.pop())
    assert any("exactly five accountability actions" in error for error in errors)
