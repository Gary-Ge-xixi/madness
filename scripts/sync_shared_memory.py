#!/usr/bin/env python3
"""Bidirectional sync between project memory/ and shared-memory/.

Scans for differences between project Gene assets and shared-memory rules,
outputs a sync report for user confirmation.

Usage:
  python3 "$MADNESS_DIR"/scripts/sync_shared_memory.py \
    --shared-memory-dir ../shared-memory \
    --project-memory-dir ./memory \
    --direction both  # up/down/both
"""

import argparse
import json
import os
import sys

from lib import load_all_assets, read_json, today_iso


def load_shared_meta(shared_dir):
    """Load META.json from shared-memory."""
    path = os.path.join(shared_dir, "META.json")
    return read_json(path)


def find_push_candidates(project_assets, meta):
    """Find project assets that could be pushed to shared-memory."""
    existing_ids = {r["id"] for r in meta.get("rules", [])} if meta else set()
    candidates = []

    for asset in project_assets:
        asset_id = asset.get("id", "")
        confidence = asset.get("confidence", 0)
        status = asset.get("status", "")
        validated_count = asset.get("validated_count", 0)
        promoted = asset.get("promoted_to_shared", False)

        if promoted:
            continue  # Already pushed

        if asset_id in existing_ids:
            # Check for version/confidence updates
            existing = next(
                (r for r in meta["rules"] if r["id"] == asset_id), None
            )
            if existing and confidence > existing.get("confidence", 0):
                candidates.append({
                    "action": "update",
                    "asset_id": asset_id,
                    "reason": f"confidence improved: {existing['confidence']} -> {confidence}",
                    "auto": False,
                    "asset": asset,
                })
            continue

        # New candidate for push
        if status == "active" and confidence >= 0.85 and validated_count >= 2:
            candidates.append({
                "action": "push_auto",
                "asset_id": asset_id,
                "reason": f"active, confidence={confidence}, validated={validated_count}",
                "auto": True,
                "asset": asset,
            })
        elif status in ("active", "provisional") and confidence >= 0.70:
            candidates.append({
                "action": "push_manual",
                "asset_id": asset_id,
                "reason": f"{status}, confidence={confidence}, validated={validated_count}",
                "auto": False,
                "asset": asset,
            })

    return candidates


def find_pull_candidates(project_assets, meta):
    """Find shared-memory rules that should be pulled to project."""
    if not meta:
        return []

    project_ids = {a.get("id", "") for a in project_assets}
    candidates = []

    for rule in meta.get("rules", []):
        rule_id = rule["id"]
        if rule.get("status") == "deprecated":
            continue
        if rule_id not in project_ids:
            candidates.append({
                "action": "pull",
                "rule_id": rule_id,
                "file": rule.get("file", ""),
                "section": rule.get("section", ""),
                "confidence": rule.get("confidence", 0.70),
                "source_project": rule.get("source_project", ""),
                "status": rule.get("status", "provisional"),
            })

    return candidates


def find_conflicts(project_assets, meta):
    """Find conflicts between project assets and shared-memory rules."""
    if not meta:
        return []

    conflicts = []
    shared_map = {r["id"]: r for r in meta.get("rules", [])}

    for asset in project_assets:
        asset_id = asset.get("id", "")
        if asset_id not in shared_map:
            continue

        shared_rule = shared_map[asset_id]

        # Check deprecation from project side
        if asset.get("status") == "deprecated" and shared_rule.get("status") != "deprecated":
            conflicts.append({
                "type": "deprecation_candidate",
                "asset_id": asset_id,
                "reason": f"Project marks as deprecated, shared-memory is {shared_rule['status']}",
                "project_status": asset.get("status"),
                "shared_status": shared_rule.get("status"),
                "shared_deprecated_by": shared_rule.get("deprecated_by", []),
            })

        # Check confidence divergence
        p_conf = asset.get("confidence", 0)
        s_conf = shared_rule.get("confidence", 0)
        if abs(p_conf - s_conf) > 0.20:
            conflicts.append({
                "type": "confidence_divergence",
                "asset_id": asset_id,
                "reason": f"project={p_conf}, shared={s_conf} (diff={abs(p_conf - s_conf):.2f})",
                "project_confidence": p_conf,
                "shared_confidence": s_conf,
            })

    return conflicts


def generate_report(push_candidates, pull_candidates, conflicts, direction):
    """Generate sync report."""
    report = {
        "generated_at": today_iso(),
        "direction": direction,
        "summary": {
            "push_candidates": len(push_candidates) if direction in ("up", "both") else 0,
            "pull_candidates": len(pull_candidates) if direction in ("down", "both") else 0,
            "conflicts": len(conflicts),
        },
    }

    if direction in ("up", "both"):
        report["push"] = push_candidates
    if direction in ("down", "both"):
        report["pull"] = pull_candidates
    if conflicts:
        report["conflicts"] = conflicts

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Bidirectional sync between project memory and shared-memory"
    )
    parser.add_argument(
        "--shared-memory-dir", required=True,
        help="Path to shared-memory directory"
    )
    parser.add_argument(
        "--project-memory-dir", required=True,
        help="Path to project memory directory"
    )
    parser.add_argument(
        "--direction", choices=["up", "down", "both"], default="both",
        help="Sync direction: up (project→shared), down (shared→project), both"
    )

    args = parser.parse_args()

    # Validate directories
    if not os.path.isdir(args.shared_memory_dir):
        print(json.dumps({
            "error": f"shared-memory directory not found: {args.shared_memory_dir}"
        }))
        sys.exit(1)

    if not os.path.isdir(args.project_memory_dir):
        print(json.dumps({
            "error": f"project memory directory not found: {args.project_memory_dir}",
            "hint": "Run manage_assets.py init first to create memory/ directory"
        }))
        sys.exit(1)

    # Load data
    meta = load_shared_meta(args.shared_memory_dir)
    if not meta:
        print(json.dumps({
            "error": "META.json not found in shared-memory directory",
            "hint": "Create META.json first to enable sync"
        }))
        sys.exit(1)

    project_assets = load_all_assets(args.project_memory_dir)

    # Scan
    push_candidates = find_push_candidates(project_assets, meta) if args.direction in ("up", "both") else []
    pull_candidates = find_pull_candidates(project_assets, meta) if args.direction in ("down", "both") else []
    conflicts = find_conflicts(project_assets, meta)

    # Report
    report = generate_report(push_candidates, pull_candidates, conflicts, args.direction)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
