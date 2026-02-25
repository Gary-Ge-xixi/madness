#!/usr/bin/env python3
"""Aggregate statistics from all cached facets."""

import argparse
import json
import os
import sys
from collections import Counter


def load_facets(retro_dir, since=None):
    """Load all facet JSON files, optionally filtering by date."""
    facets_dir = os.path.join(retro_dir, "facets")
    if not os.path.isdir(facets_dir):
        print(f"Facets directory not found: {facets_dir}", file=sys.stderr)
        return []

    facets = []
    for fname in sorted(os.listdir(facets_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(facets_dir, fname)
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: skipping {fname}: {e}", file=sys.stderr)
            continue

        if since and data.get("date", "") < since:
            continue
        facets.append(data)

    return facets


def aggregate(facets):
    """Compute aggregate statistics from a list of facet dicts."""
    total = len(facets)
    if total == 0:
        return {
            "total_sessions": 0,
            "by_goal_category": {},
            "by_outcome": {},
            "by_date": {},
            "friction_top5": [],
            "success_patterns": {},
            "loop_rate": 0.0,
            "loop_sessions": [],
            "ai_collab_summary": {
                "sycophancy_count": 0,
                "logic_leap_count": 0,
                "lazy_prompting_count": 0,
                "automation_surrender_count": 0,
                "anchoring_effect_count": 0,
            },
            "tools_distribution": {},
            "avg_duration_min": 0.0,
            "total_files_changed": 0,
            "avg_extraction_confidence": None,
        }

    by_goal_category = Counter()
    by_outcome = Counter()
    by_date = Counter()
    friction_counter = Counter()
    tools_counter = Counter()
    loop_sessions = []
    sycophancy_count = 0
    logic_leap_count = 0
    lazy_prompting_count = 0
    automation_surrender_count = 0
    anchoring_effect_count = 0
    total_duration = 0.0
    total_files = 0
    extraction_confidence_sum = 0.0
    extraction_confidence_n = 0

    for facet in facets:
        by_goal_category[facet.get("goal_category", "unknown")] += 1
        by_outcome[facet.get("outcome", "unknown")] += 1
        by_date[facet.get("date", "unknown")] += 1

        for fric in facet.get("friction", []):
            friction_counter[fric] += 1

        if facet.get("loop_detected"):
            loop_sessions.append(facet.get("session_id", ""))

        ai = facet.get("ai_collab", {})
        if ai.get("sycophancy", ""):
            sycophancy_count += 1
        if ai.get("logic_leap", ""):
            logic_leap_count += 1
        if ai.get("lazy_prompting", ""):
            lazy_prompting_count += 1
        if ai.get("automation_surrender", ""):
            automation_surrender_count += 1
        if ai.get("anchoring_effect", ""):
            anchoring_effect_count += 1

        ec = facet.get("extraction_confidence")
        if isinstance(ec, (int, float)):
            extraction_confidence_sum += ec
            extraction_confidence_n += 1

        for tool in facet.get("tools_used", []):
            tools_counter[tool] += 1

        total_duration += facet.get("duration_min", 0)
        total_files += facet.get("files_changed", 0)

    friction_top5 = [
        {"type": ftype, "count": count}
        for ftype, count in friction_counter.most_common(5)
    ]

    # Extract success patterns from fully_achieved facets
    success_patterns = {}
    for facet in facets:
        if facet.get("outcome") == "fully_achieved":
            cat = facet.get("goal_category", "unknown")
            success_patterns[cat] = success_patterns.get(cat, 0) + 1

    return {
        "total_sessions": total,
        "by_goal_category": dict(by_goal_category),
        "by_outcome": dict(by_outcome),
        "by_date": dict(by_date),
        "friction_top5": friction_top5,
        "success_patterns": success_patterns,
        "loop_rate": round(len(loop_sessions) / total, 2) if total else 0.0,
        "loop_sessions": loop_sessions,
        "ai_collab_summary": {
            "sycophancy_count": sycophancy_count,
            "logic_leap_count": logic_leap_count,
            "lazy_prompting_count": lazy_prompting_count,
            "automation_surrender_count": automation_surrender_count,
            "anchoring_effect_count": anchoring_effect_count,
        },
        "tools_distribution": dict(tools_counter),
        "avg_duration_min": round(total_duration / total, 1) if total else 0.0,
        "total_files_changed": total_files,
        "avg_extraction_confidence": round(extraction_confidence_sum / extraction_confidence_n, 3) if extraction_confidence_n else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Aggregate statistics from cached facets")
    parser.add_argument("--retro-dir", default=".retro", help="Retro directory (default: .retro)")
    parser.add_argument("--since", default=None, help="Only include facets with date >= DATE (YYYY-MM-DD)")
    parser.add_argument("--output-file", default=None, help="Write output to file instead of stdout (for large project batch processing)")
    args = parser.parse_args()

    facets = load_facets(args.retro_dir, since=args.since)
    result = aggregate(facets)
    output = json.dumps(result, indent=2)

    if args.output_file:
        os.makedirs(os.path.dirname(args.output_file) if os.path.dirname(args.output_file) else ".", exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Aggregation written to {args.output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
