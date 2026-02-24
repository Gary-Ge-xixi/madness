#!/usr/bin/env python3
"""Initialize the memory/ directory structure for asset management."""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Initialize memory/ directory structure")
    parser.add_argument("--project-dir", default=".", help="Project root directory (default: .)")
    args = parser.parse_args()

    memory_dir = os.path.join(os.path.abspath(args.project_dir), "memory")

    if os.path.exists(memory_dir):
        print("memory/ already exists, skipping init", file=sys.stderr)
        sys.exit(0)

    try:
        os.makedirs(memory_dir, exist_ok=True)
        os.makedirs(os.path.join(memory_dir, "views"), exist_ok=True)
        os.makedirs(os.path.join(memory_dir, "exports"), exist_ok=True)

        files = {
            "index.json": json.dumps(
                {"schema_version": "1.0", "assets": {"genes": 0, "sops": 0, "prefs": 0}, "last_updated": ""},
                ensure_ascii=False, indent=2,
            ),
            "INDEX.md": "# Memory \u8d44\u4ea7\u7d22\u5f15\n\n> \u81ea\u52a8\u751f\u6210\uff0c\u8bf7\u52ff\u624b\u52a8\u7f16\u8f91\n\n\u6682\u65e0\u8d44\u4ea7\u3002\n",
            "genes.json": "[]",
            "sops.json": "[]",
            "prefs.json": "[]",
            "evolution.jsonl": "",
        }

        for filename, content in files.items():
            filepath = os.path.join(memory_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        result = {"initialized": True, "path": memory_dir}
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except OSError as e:
        print(f"Error initializing memory directory: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
