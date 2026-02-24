#!/usr/bin/env python3
"""Append event entries to memory/evolution.jsonl."""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

VALID_EVENTS = [
    "create",
    "update",
    "deprecate",
    "merge",
    "absorb",
    "validate",
    "no_match",
    "inject_reflection",
]


def main():
    parser = argparse.ArgumentParser(description="Log evolution events to memory/evolution.jsonl")
    parser.add_argument(
        "--event",
        required=True,
        choices=VALID_EVENTS,
        help="Event type",
    )
    parser.add_argument("--asset-id", required=True, help="Asset identifier")
    parser.add_argument("--details", default=None, help="JSON string with extra details")
    parser.add_argument("--memory-dir", default="./memory", help="Memory directory (default: ./memory)")
    args = parser.parse_args()

    # Parse details
    details = {}
    if args.details:
        try:
            details = json.loads(args.details)
            if not isinstance(details, dict):
                print("Error: --details must be a JSON object", file=sys.stderr)
                sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in --details: {e}", file=sys.stderr)
            sys.exit(1)

    # Build event
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": args.event,
        "asset_id": args.asset_id,
        "review_period": date.today().isoformat(),
        "details": details,
    }

    # Ensure directory and file exist
    memory_dir = Path(args.memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    evolution_file = memory_dir / "evolution.jsonl"

    try:
        with open(evolution_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Error: could not write to {evolution_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Output the written event to stdout
    json.dump(event, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
