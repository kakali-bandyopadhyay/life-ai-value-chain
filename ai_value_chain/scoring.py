"""Risk-gated scoring and ranking for assessment use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


RISK_ORDER = ("low", "medium", "high", "unacceptable")
ALLOWED_APPETITES = ("low", "medium", "high")
SHORTLIST_SIZE = 5
WEIGHT_KEYS = ("value", "feasibility", "data_readiness")


def _weights(weights: Mapping[str, int] | Sequence[int]) -> tuple[int, int, int]:
    if isinstance(weights, Mapping):
        values = tuple(weights.get(key, 0) for key in WEIGHT_KEYS)
    else:
        values = tuple(weights)
    if len(values) != 3:
        raise ValueError("Weights must contain value, feasibility, and data_readiness")
    if any(isinstance(weight, bool) or not isinstance(weight, int) or not 0 <= weight <= 10 for weight in values):
        raise ValueError("Weights must be integers from 0 to 10")
    if sum(values) == 0:
        raise ValueError("Set at least one weight above 0")
    return values  # type: ignore[return-value]


def _appetite_index(appetite: str) -> int:
    if appetite not in ALLOWED_APPETITES:
        raise ValueError(f"Invalid appetite: {appetite}")
    return RISK_ORDER.index(appetite)


def eligible(row: Mapping[str, Any], appetite: str) -> bool:
    """Return whether a row is within the selected risk appetite."""
    appetite_index = _appetite_index(appetite)
    risk_tier = row.get("risk_tier")
    if risk_tier not in RISK_ORDER:
        raise ValueError(f"Invalid risk_tier: {risk_tier}")
    return risk_tier != "unacceptable" and RISK_ORDER.index(risk_tier) <= appetite_index


def score(row: Mapping[str, Any], weights: Mapping[str, int] | Sequence[int]) -> float:
    """Calculate the weighted score on a 0–100 scale."""
    value_weight, feasibility_weight, readiness_weight = _weights(weights)
    numerator = (
        value_weight * row["value"]
        + feasibility_weight * row["feasibility"]
        + readiness_weight * row["data_readiness"]
    )
    return round(100 * numerator / (5 * (value_weight + feasibility_weight + readiness_weight)), 1)


def rank(
    rows: Sequence[Mapping[str, Any]],
    weights: Mapping[str, int] | Sequence[int],
    appetite: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ranked eligible rows and below-appetite rows with status text."""
    checked_weights = _weights(weights)
    appetite_index = _appetite_index(appetite)
    ranked: list[dict[str, Any]] = []
    ineligible_rows: list[dict[str, Any]] = []
    for row in rows:
        row_appetite = row.get("risk_tier")
        # Validate even rows that will be ineligible so bad input is never silently ranked.
        if row_appetite not in RISK_ORDER:
            raise ValueError(f"Invalid risk_tier: {row_appetite}")
        if row_appetite == "unacceptable":
            entry = dict(row)
            entry.pop("score", None)
            entry["status"] = "Not eligible – ruled unacceptable"
            ineligible_rows.append(entry)
        elif RISK_ORDER.index(row_appetite) > appetite_index:
            entry = dict(row)
            entry.pop("score", None)
            entry["status"] = "Not eligible – internal risk tier above appetite"
            ineligible_rows.append(entry)
        else:
            entry = dict(row)
            entry["score"] = score(row, checked_weights)
            ranked.append(entry)

    ranked.sort(key=lambda row: (-row["score"], -row["value"], -row["data_readiness"], row["use_case_id"]))
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position
        row["shortlisted"] = position <= SHORTLIST_SIZE
    return ranked, ineligible_rows
