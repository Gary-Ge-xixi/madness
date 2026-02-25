#!/usr/bin/env python3
"""Atomic read/write of .retro/state.json."""

import argparse
import json
import os
import sys
from pathlib import Path

from lib import today_iso as today


def retro_dir(project_dir: str) -> Path:
    return Path(project_dir).resolve() / ".retro"


def state_path(project_dir: str) -> Path:
    return retro_dir(project_dir) / "state.json"


def read_state(project_dir: str) -> dict:
    sp = state_path(project_dir)
    if not sp.exists():
        print(f"Error: state.json not found at {sp}", file=sys.stderr)
        sys.exit(1)
    with open(sp, "r", encoding="utf-8") as f:
        return json.load(f)


def write_state_atomic(project_dir: str, data: dict) -> None:
    """Write state.json atomically via lib.write_json_atomic."""
    from lib import write_json_atomic
    sp = state_path(project_dir)
    sp.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(str(sp), data)


def count_facets(project_dir: str) -> int:
    facets_dir = retro_dir(project_dir) / "facets"
    if not facets_dir.is_dir():
        return 0
    return sum(1 for f in facets_dir.iterdir() if f.is_file())


def count_sessions(project_dir: str) -> int:
    """Count JSONL session files in the Claude projects directory."""
    abs_project = str(Path(project_dir).resolve())
    encoded_name = abs_project.replace("/", "-")
    claude_sessions = Path.home() / ".claude" / "projects" / encoded_name
    if not claude_sessions.is_dir():
        return 0
    return sum(1 for f in claude_sessions.glob("*.jsonl"))


def cmd_init(args):
    project_dir = os.path.abspath(args.project_dir)
    rd = retro_dir(project_dir)

    if rd.exists():
        print(f"Warning: .retro/ already exists at {rd}. Not overwriting.", file=sys.stderr)
        sys.exit(1)

    # Create directory structure
    rd.mkdir(parents=True)
    (rd / "facets").mkdir()
    (rd / "reviews").mkdir()

    state = {
        "project_name": args.project_name,
        "project_dir": project_dir,
        "created_at": today(),
        "review_interval_days": args.interval,
        "last_review_at": today(),
        "sessions_analyzed_up_to": "",
        "total_sessions": 0,
        "total_facets_cached": 0,
        "reviews": [],
    }

    write_state_atomic(project_dir, state)
    json.dump(state, sys.stdout, indent=2)
    print()


def cmd_update(args):
    project_dir = os.path.abspath(args.project_dir or ".")
    state = read_state(project_dir)

    if args.last_review_at:
        state["last_review_at"] = args.last_review_at

    if args.sessions_up_to:
        state["sessions_analyzed_up_to"] = args.sessions_up_to

    if args.add_review:
        review_type = args.add_review
        review_entry = {
            "type": review_type,
            "date": today(),
            "file": f"reviews/{today()}-{review_type}.md",
        }
        state.setdefault("reviews", []).append(review_entry)

    # Recount totals
    state["total_sessions"] = count_sessions(state.get("project_dir", project_dir))
    state["total_facets_cached"] = count_facets(project_dir)

    write_state_atomic(project_dir, state)
    json.dump(state, sys.stdout, indent=2)
    print()


def cmd_read(args):
    project_dir = os.path.abspath(args.project_dir or ".")
    state = read_state(project_dir)
    json.dump(state, sys.stdout, indent=2)
    print()


def main():
    parser = argparse.ArgumentParser(description="Manage .retro/state.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize .retro/ directory structure")
    p_init.add_argument("--project-name", required=True, help="Project name")
    p_init.add_argument("--interval", type=int, required=True, help="Review interval in days")
    p_init.add_argument("--project-dir", required=True, help="Project directory path")
    p_init.set_defaults(func=cmd_init)

    # update
    p_update = subparsers.add_parser("update", help="Update state.json fields")
    p_update.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")
    p_update.add_argument("--last-review-at", default=None, help="Set last_review_at date")
    p_update.add_argument("--sessions-up-to", default=None, help="Set sessions_analyzed_up_to")
    p_update.add_argument("--add-review", default=None, metavar="TYPE", help="Append a review entry")
    p_update.set_defaults(func=cmd_update)

    # read
    p_read = subparsers.add_parser("read", help="Read and output state.json")
    p_read.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")
    p_read.set_defaults(func=cmd_read)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
