"""Risk-gated scoring tests rebased on the checked-in life data."""

from copy import deepcopy

import pytest

from ai_value_chain.data import load_use_cases
from ai_value_chain.scoring import eligible, rank, score


DEFAULT_WEIGHTS = {"value": 5, "feasibility": 3, "data_readiness": 2}


def rows_by_id():
    return {row["use_case_id"]: row for row in load_use_cases()}


def test_default_ranking_snapshot_and_shortlist():
    ranked, ineligible = rank(load_use_cases(), DEFAULT_WEIGHTS, "medium")
    assert [(row["use_case_id"], row["score"]) for row in ranked] == [
        ("VC-01", 76.0), ("VC-09", 76.0), ("VC-13", 72.0),
        ("VC-05", 70.0), ("VC-11", 70.0), ("VC-07", 66.0),
        ("VC-06", 66.0), ("VC-10", 64.0), ("VC-12", 60.0),
        ("VC-04", 60.0), ("VC-08", 56.0),
    ]
    assert [row["use_case_id"] for row in ranked if row["shortlisted"]] == [
        "VC-01", "VC-09", "VC-13", "VC-05", "VC-11",
    ]
    assert [(row["use_case_id"], row["status"]) for row in ineligible] == [
        ("VC-02", "Not eligible – internal risk tier above appetite"),
        ("VC-03", "Not eligible – ruled unacceptable"),
        ("VC-14", "Not eligible – internal risk tier above appetite"),
    ]


def test_high_appetite_places_high_risk_use_cases_first():
    ranked, _ = rank(load_use_cases(), DEFAULT_WEIGHTS, "high")
    assert [(row["use_case_id"], row["score"]) for row in ranked[:3]] == [
        ("VC-02", 90.0), ("VC-14", 84.0), ("VC-01", 76.0),
    ]


@pytest.mark.parametrize(
    ("first", "second"),
    [("VC-01", "VC-09"), ("VC-05", "VC-11"), ("VC-07", "VC-06"), ("VC-12", "VC-04")],
)
def test_required_default_tie_breaks(first, second):
    ranked, _ = rank(load_use_cases(), DEFAULT_WEIGHTS, "medium")
    positions = {row["use_case_id"]: index for index, row in enumerate(ranked)}
    assert positions[first] < positions[second]


@pytest.mark.parametrize("appetite", ["low", "medium", "high"])
def test_unacceptable_gate_cannot_be_overridden_by_maximum_scores(appetite):
    row = deepcopy(rows_by_id()["VC-03"])
    row.update(value=5, feasibility=5, data_readiness=5)
    ranked, ineligible = rank([row], [10, 0, 0], appetite)
    assert ranked == []
    assert ineligible[0]["use_case_id"] == "VC-03"
    assert ineligible[0]["status"] == "Not eligible – ruled unacceptable"


@pytest.mark.parametrize("weights", [[10, 0, 0], [0, 10, 0], [0, 0, 10]])
def test_high_risk_use_cases_are_ineligible_at_medium_for_any_weights(weights):
    for use_case_id in ("VC-02", "VC-14"):
        ranked, ineligible = rank([rows_by_id()[use_case_id]], weights, "medium")
        assert ranked == []
        assert ineligible[0]["use_case_id"] == use_case_id
        assert ineligible[0]["status"] == "Not eligible – internal risk tier above appetite"


def test_zero_weights_raise_and_score_formula():
    with pytest.raises(ValueError, match="Set at least one weight above 0"):
        score(rows_by_id()["VC-01"], [0, 0, 0])
    assert score(rows_by_id()["VC-01"], DEFAULT_WEIGHTS) == 76.0


def test_unacceptable_appetite_is_not_selectable():
    with pytest.raises(ValueError):
        eligible(rows_by_id()["VC-03"], "unacceptable")


def test_tie_break_value_then_readiness_then_id():
    rows = [
        {"use_case_id": "VC-03", "risk_tier": "low", "value": 4, "feasibility": 4, "data_readiness": 3},
        {"use_case_id": "VC-02", "risk_tier": "low", "value": 4, "feasibility": 3, "data_readiness": 4},
        {"use_case_id": "VC-04", "risk_tier": "low", "value": 4, "feasibility": 2, "data_readiness": 5},
        {"use_case_id": "VC-01", "risk_tier": "low", "value": 3, "feasibility": 4, "data_readiness": 4},
    ]
    ranked, _ = rank(rows, [1, 1, 1], "low")
    assert [row["use_case_id"] for row in ranked] == ["VC-04", "VC-02", "VC-03", "VC-01"]
