"""Command line entry point for the AI value chain package."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .data import load_use_cases, validate
from .render import build as build_report
from .scoring import WEIGHT_KEYS, rank


def _parse_weights(value: str) -> dict[str, int]:
    try:
        parsed = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("weights must be three comma-separated integers") from error
    if len(parsed) != 3 or any(not 0 <= weight <= 10 for weight in parsed):
        raise argparse.ArgumentTypeError("weights must be three comma-separated integers from 0 to 10")
    return dict(zip(WEIGHT_KEYS, parsed))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ai_value_chain")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    assess_parser = subparsers.add_parser("assess")
    assess_parser.add_argument("--appetite", choices=("low", "medium", "high"), default="medium")
    assess_parser.add_argument("--weights", type=_parse_weights, default=_parse_weights("5,3,2"))
    subparsers.add_parser("build")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        errors = validate()
        if errors:
            print("\n".join(errors))
            return 1
        print("OK")
        return 0

    if args.command == "assess":
        ranked, ineligible = rank(load_use_cases(), args.weights, args.appetite)
        payload = {
            "appetite": args.appetite,
            "weights": args.weights,
            "ranked": [
                {
                    "rank": row["rank"],
                    "use_case_id": row["use_case_id"],
                    "name": row["name"],
                    "score": row["score"],
                    "shortlisted": row["shortlisted"],
                }
                for row in ranked
            ],
            "ineligible": [
                {"use_case_id": row["use_case_id"], "name": row["name"], "status": row["status"]}
                for row in ineligible
            ],
        }
        print(json.dumps(payload))
        return 0

    build_report()
    print("Built docs/index.html and docs/ASSESSMENT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
