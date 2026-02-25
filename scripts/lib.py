#!/usr/bin/env python3
"""Shared utilities for madness scripts.

Centralizes JSON I/O, asset loading, constants, date helpers,
state CRUD, and evolution logging used across all madness scripts.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSET_FILES = {"gene": "genes.json", "sop": "sops.json", "pref": "prefs.json"}

VALID_ASSET_TYPES = {"gene", "sop", "pref"}

VALID_STATUSES = {"active", "provisional", "deprecated"}

INJECTABLE_STATUSES = {"active", "provisional"}

VALID_EVENTS = [
    "create",
    "update",
    "deprecate",
    "merge",
    "absorb",
    "validate",
    "no_match",
    "inject_reflection",
    "promoted_to_active",
    "compliance_highlight",
]

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def today_iso() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def utc_now_iso() -> str:
    """Return current UTC datetime in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def utc_today_iso() -> str:
    """Return today's UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def read_json(path):
    """Read a JSON file. Return None if the file does not exist."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_json_list(path):
    """Read a JSON file expected to contain a list. Return [] if missing."""
    data = read_json(path)
    if data is None:
        return []
    return data


def write_json_atomic(path, data):
    """Write *data* as JSON to *path* atomically via tempfile + os.replace."""
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------


def load_all_assets(memory_dir, statuses=None):
    """Load Gene/SOP/Pref assets from *memory_dir*.

    Each item gets an ``asset_type`` field set if not already present.
    If *statuses* is given (a set of strings), only items whose status
    is in that set are returned.
    """
    assets = []
    for asset_type, filename in ASSET_FILES.items():
        filepath = os.path.join(memory_dir, filename)
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("items", data.get("assets", []))
            for item in items:
                item.setdefault("asset_type", asset_type)
                if statuses is None or item.get("status") in statuses:
                    assets.append(item)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {filepath}: {e}", file=sys.stderr)
    return assets


def type_to_filename(asset_type):
    """Map an asset type string to its JSON filename."""
    return ASSET_FILES.get(asset_type, f"{asset_type}s.json")


# ---------------------------------------------------------------------------
# State management (absorbed from manage_state.py)
# ---------------------------------------------------------------------------


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
    """Write state.json atomically via write_json_atomic."""
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


# ---------------------------------------------------------------------------
# Evolution logging (absorbed from log_evolution.py)
# ---------------------------------------------------------------------------


def append_evolution(memory_dir, entry):
    """Append an event entry to memory/evolution.jsonl."""
    filepath = os.path.join(memory_dir, "evolution.jsonl")
    os.makedirs(memory_dir, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# CLI: state subcommands
# ---------------------------------------------------------------------------


def cmd_state_init(args):
    project_dir = os.path.abspath(args.project_dir)
    rd = retro_dir(project_dir)

    if rd.exists():
        print(f"Warning: .retro/ already exists at {rd}. Not overwriting.", file=sys.stderr)
        sys.exit(1)

    # Create directory structure
    rd.mkdir(parents=True)
    (rd / "facets").mkdir()
    (rd / "reviews").mkdir()

    # Parse goals
    goals = []
    if args.goals:
        try:
            goals = json.loads(args.goals)
            if not isinstance(goals, list):
                print("Error: --goals must be a JSON array", file=sys.stderr)
                sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in --goals: {e}", file=sys.stderr)
            sys.exit(1)

    state = {
        "project_name": args.project_name,
        "project_dir": project_dir,
        "created_at": today_iso(),
        "review_interval_days": args.interval,
        "last_review_at": today_iso(),
        "sessions_analyzed_up_to": "",
        "total_sessions": 0,
        "total_facets_cached": 0,
        "goals": goals,
        "reviews": [],
    }

    write_state_atomic(project_dir, state)
    json.dump(state, sys.stdout, indent=2)
    print()


def cmd_state_update(args):
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
            "date": today_iso(),
            "file": f"reviews/{today_iso()}-{review_type}.md",
        }
        state.setdefault("reviews", []).append(review_entry)

    if args.goals is not None:
        try:
            state["goals"] = json.loads(args.goals)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in --goals: {e}", file=sys.stderr)
            sys.exit(1)

    # Ensure goals field exists for backward compatibility
    state.setdefault("goals", [])

    # Recount totals
    state["total_sessions"] = count_sessions(state.get("project_dir", project_dir))
    state["total_facets_cached"] = count_facets(project_dir)

    write_state_atomic(project_dir, state)
    json.dump(state, sys.stdout, indent=2)
    print()


def cmd_state_read(args):
    project_dir = os.path.abspath(args.project_dir or ".")
    state = read_state(project_dir)
    # Ensure goals field exists for backward compatibility
    state.setdefault("goals", [])
    json.dump(state, sys.stdout, indent=2)
    print()


# ---------------------------------------------------------------------------
# CLI: evolution subcommand
# ---------------------------------------------------------------------------


def cmd_evolution(args):
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

    append_evolution(args.memory_dir, event)

    # Output the written event to stdout
    json.dump(event, sys.stdout, indent=2)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Madness shared library — state management + evolution logging"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- state ---
    p_state = subparsers.add_parser("state", help="Manage .retro/state.json")
    state_sub = p_state.add_subparsers(dest="state_command", required=True)

    p_init = state_sub.add_parser("init", help="Initialize .retro/ directory structure")
    p_init.add_argument("--project-name", required=True, help="Project name")
    p_init.add_argument("--interval", type=int, required=True, help="Review interval in days")
    p_init.add_argument("--project-dir", required=True, help="Project directory path")
    p_init.add_argument("--goals", default=None, help="JSON array of project goals")
    p_init.set_defaults(func=cmd_state_init)

    p_update = state_sub.add_parser("update", help="Update state.json fields")
    p_update.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")
    p_update.add_argument("--last-review-at", default=None, help="Set last_review_at date")
    p_update.add_argument("--sessions-up-to", default=None, help="Set sessions_analyzed_up_to")
    p_update.add_argument("--add-review", default=None, metavar="TYPE", help="Append a review entry")
    p_update.add_argument("--goals", default=None, help="JSON array to replace goals")
    p_update.set_defaults(func=cmd_state_update)

    p_read = state_sub.add_parser("read", help="Read and output state.json")
    p_read.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")
    p_read.set_defaults(func=cmd_state_read)

    # --- evolution ---
    p_evo = subparsers.add_parser("evolution", help="Log evolution events to memory/evolution.jsonl")
    p_evo.add_argument(
        "--event",
        required=True,
        choices=VALID_EVENTS,
        help="Event type",
    )
    p_evo.add_argument("--asset-id", required=True, help="Asset identifier")
    p_evo.add_argument("--details", default=None, help="JSON string with extra details")
    p_evo.add_argument("--memory-dir", default="./memory", help="Memory directory (default: ./memory)")
    p_evo.set_defaults(func=cmd_evolution)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
