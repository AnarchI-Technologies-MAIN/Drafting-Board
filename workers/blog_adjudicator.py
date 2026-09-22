"""Interactive command-line entry point for Blogger human adjudication."""

from __future__ import annotations

import argparse
import json

from blog_loop.human_adjudication import (
    adjudicate,
    inspect_job,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blogger human adjudication gate"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("job_id", type=int)

    decision_parser = sub.add_parser("decide")
    decision_parser.add_argument("job_id", type=int)
    decision_parser.add_argument(
        "--decision",
        required=True,
        choices=("APPROVED", "REJECTED"),
    )
    decision_parser.add_argument(
        "--reviewer",
        required=True,
    )
    decision_parser.add_argument(
        "--reason",
        default="",
    )

    args = parser.parse_args()

    if args.command == "inspect":
        result = inspect_job(args.job_id)
    else:
        result = adjudicate(
            args.job_id,
            decision=args.decision,
            reviewer=args.reviewer,
            reason=args.reason,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
