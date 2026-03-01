#!/usr/bin/env python3
"""Safely read and preview Claude session JSONL files.

Handles malformed lines, binary content, and oversized files gracefully.
Outputs clean JSON to stdout for downstream consumption.
"""

import argparse
import json
import sys
from pathlib import Path


def read_session(file_path: str, max_messages: int = 0, types: list[str] | None = None) -> dict:
    """Read a session JSONL file, return structured summary.

    Args:
        file_path: Path to .jsonl session file.
        max_messages: Max messages to include (0 = all).
        types: Filter by message type (e.g. ['human', 'user', 'assistant']).
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    size_bytes = path.stat().st_size
    messages = []
    parse_errors = 0
    total_lines = 0

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue

                if types and obj.get("type") not in types:
                    continue

                messages.append(obj)
    except OSError as e:
        return {"error": f"Could not read file: {e}"}

    # Apply max_messages limit
    if max_messages > 0:
        messages = messages[:max_messages]

    # Truncate large message content for preview
    previews = []
    for msg in messages:
        preview = {
            "type": msg.get("type", "unknown"),
        }

        # Extract message content - handle various formats
        content = msg.get("message", msg.get("content", ""))
        if isinstance(content, list):
            # Handle content blocks (e.g. [{"type": "text", "text": "..."}])
            texts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    texts.append(block["text"])
                elif isinstance(block, str):
                    texts.append(block)
            content = "\n".join(texts)
        elif not isinstance(content, str):
            content = str(content)

        # Truncate for preview
        if len(content) > 500:
            preview["content"] = content[:500] + f"... [{len(content)} chars total]"
        else:
            preview["content"] = content

        previews.append(preview)

    return {
        "file": str(path),
        "size_bytes": size_bytes,
        "total_lines": total_lines,
        "parse_errors": parse_errors,
        "total_messages": len(messages) if max_messages == 0 else f"{len(previews)} of {len(messages)}+",
        "messages": previews,
    }


def read_raw(file_path: str, max_chars: int = 50000) -> dict:
    """Read raw session content for facet extraction.

    Returns the full content (up to max_chars) with only valid JSON lines,
    suitable for passing to sub-agents.
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    size_bytes = path.stat().st_size
    valid_lines = []
    char_count = 0
    truncated = False
    parse_errors = 0

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)  # validate
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue

                if max_chars > 0 and char_count + len(line) > max_chars:
                    truncated = True
                    break

                valid_lines.append(line)
                char_count += len(line)
    except OSError as e:
        return {"error": f"Could not read file: {e}"}

    return {
        "file": str(path),
        "size_bytes": size_bytes,
        "char_count": char_count,
        "valid_lines": len(valid_lines),
        "parse_errors": parse_errors,
        "truncated": truncated,
        "content": "\n".join(valid_lines),
    }


def main():
    parser = argparse.ArgumentParser(description="Safely read Claude session JSONL files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # preview command
    preview_parser = subparsers.add_parser("preview", help="Preview session messages")
    preview_parser.add_argument("file", help="Path to .jsonl session file")
    preview_parser.add_argument("--max", type=int, default=10, help="Max messages to show (0=all)")
    preview_parser.add_argument(
        "--types",
        nargs="+",
        default=None,
        help="Filter by message types (e.g. human user assistant)",
    )

    # raw command
    raw_parser = subparsers.add_parser("raw", help="Read raw content for facet extraction")
    raw_parser.add_argument("file", help="Path to .jsonl session file")
    raw_parser.add_argument(
        "--max-chars",
        type=int,
        default=50000,
        help="Max chars to read (0=unlimited)",
    )

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Quick stats without reading full content")
    stats_parser.add_argument("file", help="Path to .jsonl session file")

    args = parser.parse_args()

    if args.command == "preview":
        result = read_session(args.file, max_messages=args.max, types=args.types)
    elif args.command == "raw":
        result = read_raw(args.file, max_chars=args.max_chars)
    elif args.command == "stats":
        result = read_session(args.file, max_messages=0, types=None)
        # Strip messages for stats-only output
        if "messages" in result:
            msg_count = len(result["messages"])
            type_counts = {}
            for m in result["messages"]:
                t = m.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            result["message_count"] = msg_count
            result["type_distribution"] = type_counts
            del result["messages"]

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
