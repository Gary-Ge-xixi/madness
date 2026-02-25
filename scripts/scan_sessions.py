#!/usr/bin/env python3
"""Scan Claude session JSONL files, filter new sessions since last analysis."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def load_state(state_path: str) -> dict:
    """Load state.json, return empty dict on missing/invalid file."""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: state file not found: {state_path}", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: invalid JSON in state file: {e}", file=sys.stderr)
        return {}


def find_project_dir(project_dir: str) -> Path | None:
    """Find the Claude projects subdirectory matching the given project dir."""
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.is_dir():
        print(f"Error: Claude projects directory not found: {claude_projects}", file=sys.stderr)
        return None

    # Convert project dir path to Claude's naming convention:
    # slashes become hyphens, underscores also become hyphens
    abs_project = os.path.abspath(project_dir)
    encoded_name = abs_project.replace("/", "-")

    # Build candidate list: exact match + underscore-to-hyphen variant
    candidates = [claude_projects / encoded_name]
    encoded_name_alt = encoded_name.replace("_", "-")
    if encoded_name_alt != encoded_name:
        candidates.append(claude_projects / encoded_name_alt)

    # Prefer candidate with actual .jsonl files
    for candidate in candidates:
        if candidate.is_dir() and list(candidate.glob("*.jsonl")):
            return candidate

    # Fallback: return first existing directory even if empty
    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    print(f"Error: no matching project directory found for '{abs_project}'", file=sys.stderr)
    for c in candidates:
        print(f"  Tried: {c}", file=sys.stderr)
    return None


def is_subagent_session(file_path: Path) -> bool:
    """Check if session is a sub-agent session by inspecting first few lines."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if "parentSessionId" in obj:
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return False


def count_human_messages(file_path: Path) -> int:
    """Count user messages in a JSONL file.

    Claude Code uses type='user' (not 'human') for user messages.
    We check both for backwards compatibility.
    """
    count = 0
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") in ("human", "user"):
                        count += 1
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        print(f"Warning: could not read {file_path}: {e}", file=sys.stderr)
    return count


def count_total_messages(file_path: Path) -> int:
    """Count total valid JSON lines in a JSONL file."""
    count = 0
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except OSError:
        pass
    return count


def main():
    parser = argparse.ArgumentParser(description="Scan Claude session JSONL files")
    parser.add_argument("--state", required=True, help="Path to state.json")
    parser.add_argument("--project-dir", required=True, help="Project directory path")
    args = parser.parse_args()

    state = load_state(args.state)
    cutoff = state.get("sessions_analyzed_up_to", "") or ""

    project_sessions_dir = find_project_dir(args.project_dir)
    if project_sessions_dir is None:
        json.dump([], sys.stdout)
        sys.exit(0)

    jsonl_files = sorted(project_sessions_dir.glob("*.jsonl"))
    if not jsonl_files:
        print("Info: no session files found", file=sys.stderr)
        json.dump([], sys.stdout)
        sys.exit(0)

    # Determine cutoff mtime if we have a reference session
    cutoff_mtime = 0.0
    if cutoff:
        # Try to find the cutoff file to get its mtime
        cutoff_path = project_sessions_dir / (cutoff if cutoff.endswith(".jsonl") else cutoff + ".jsonl")
        if cutoff_path.exists():
            cutoff_mtime = cutoff_path.stat().st_mtime
        else:
            # Try treating cutoff as a timestamp string (ISO format)
            try:
                dt = datetime.fromisoformat(cutoff)
                cutoff_mtime = dt.timestamp()
            except (ValueError, TypeError):
                print(f"Warning: could not resolve cutoff '{cutoff}', including all sessions", file=sys.stderr)

    results = []
    for fp in jsonl_files:
        stat = fp.stat()
        file_mtime = stat.st_mtime

        # Filter by cutoff
        if cutoff_mtime > 0 and file_mtime <= cutoff_mtime:
            continue

        # Skip sub-agent sessions
        if is_subagent_session(fp):
            continue

        # Count human messages, skip if < 2
        human_count = count_human_messages(fp)
        if human_count < 2:
            continue

        mtime_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")

        results.append({
            "session_id": fp.stem,
            "file_path": str(fp),
            "message_count": count_total_messages(fp),
            "date": mtime_date,
            "size_bytes": stat.st_size,
        })

    # Sort by date ascending
    results.sort(key=lambda x: x["date"])

    json.dump(results, sys.stdout, indent=2)
    print()  # trailing newline


if __name__ == "__main__":
    main()
