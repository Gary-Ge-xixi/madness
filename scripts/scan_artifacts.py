#!/usr/bin/env python3
"""Scan project directory for new/modified files since last review."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


SKIP_DIRS = {".git", ".retro", "node_modules", "__pycache__", ".venv", "venv", ".env", ".claude"}

TYPE_MAP = {
    "reports": {".md", ".txt", ".pdf"},
    "data": {".json", ".jsonl", ".csv", ".xlsx", ".yaml", ".yml"},
    "visualization": {".png", ".jpg", ".jpeg", ".svg", ".html"},
    "tools": {".py", ".js", ".ts", ".sh", ".bash"},
    "docs": {".doc", ".docx", ".pptx"},
}

TYPE_LABELS = {
    "reports": "\u62a5\u544a",
    "data": "\u6570\u636e",
    "visualization": "\u53ef\u89c6\u5316",
    "tools": "\u5de5\u5177",
    "docs": "\u6587\u6863",
}


def classify_file(ext: str) -> str:
    ext = ext.lower()
    for key, exts in TYPE_MAP.items():
        if ext in exts:
            return TYPE_LABELS.get(key, key)
    return "\u5176\u4ed6"


def human_readable_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"+{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"+{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"+{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"+{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def scan(project_dir: str, last_review_at: str) -> dict:
    try:
        cutoff_dt = datetime.strptime(last_review_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        cutoff_ts = cutoff_dt.timestamp()
    except ValueError:
        print(f"Error: Invalid date format '{last_review_at}'. Expected YYYY-MM-DD.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(project_dir):
        print(f"Error: Directory '{project_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    new_files = []
    # Note: We cannot reliably distinguish "new" vs "modified" files across platforms.
    # All files with mtime > cutoff are reported in new_files.
    # modified_files is kept for API compatibility but will be empty.
    modified_files = []
    by_type: dict[str, int] = {}
    total_size = 0

    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                st = os.stat(fpath)
            except OSError as e:
                print(f"Warning: Cannot stat '{fpath}': {e}", file=sys.stderr)
                continue

            if st.st_mtime > cutoff_ts:
                rel = os.path.relpath(fpath, project_dir)
                new_files.append(rel)
                total_size += st.st_size

                _, ext = os.path.splitext(fname)
                category = classify_file(ext)
                by_type[category] = by_type.get(category, 0) + 1

    # Sort for deterministic output
    new_files.sort()

    result = {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "last_review_at": last_review_at,
        "new_files": new_files,
        "modified_files": modified_files,
        "by_type": by_type,
        "total_count": len(new_files) + len(modified_files),
        "total_size_delta": human_readable_size(total_size),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Scan project directory for new/modified files since last review.")
    parser.add_argument("--project-dir", required=True, help="Project directory to scan")
    parser.add_argument("--last-review-at", required=True, help="Date of last review (YYYY-MM-DD)")
    args = parser.parse_args()

    result = scan(args.project_dir, args.last_review_at)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()  # trailing newline


if __name__ == "__main__":
    main()
