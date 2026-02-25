#!/usr/bin/env python3
"""CRUD operations for Gene/SOP/Pref assets in memory/."""

import argparse
import json
import os
import re
import sys

from lib import (
    VALID_ASSET_TYPES,
    VALID_STATUSES,
    read_json_list,
    type_to_filename,
    utc_now_iso,
    utc_today_iso,
    write_json_atomic,
)

VALID_TYPES = tuple(sorted(VALID_ASSET_TYPES))


def append_evolution(memory_dir, entry):
    filepath = os.path.join(memory_dir, "evolution.jsonl")
    os.makedirs(memory_dir, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def title_to_id(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    slug = slug.strip("-")
    return slug or "asset"


def deduplicate_id(existing_ids, base_id):
    if base_id not in existing_ids:
        return base_id
    counter = 2
    while f"{base_id}-{counter}" in existing_ids:
        counter += 1
    return f"{base_id}-{counter}"


def confidence_to_status(confidence):
    if confidence >= 0.85:
        return "active"
    if confidence >= 0.50:
        return "provisional"
    return "deprecated"


def cmd_create(args):
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in --data: {e}", file=sys.stderr)
        sys.exit(1)

    if "title" not in data:
        print("Error: --data must contain at least a 'title' field", file=sys.stderr)
        sys.exit(1)

    today = utc_today_iso()
    filepath = os.path.join(args.memory_dir, type_to_filename(args.type))
    existing = read_json_list(filepath)
    existing_ids = {a["id"] for a in existing}

    base_id = title_to_id(data["title"])
    asset_id = deduplicate_id(existing_ids, base_id)

    asset = {
        "id": asset_id,
        "title": data.get("title", ""),
        "domain": data.get("domain", ""),
        "trigger": data.get("trigger", ""),
        "version": 1,
        "confidence": 0.70,
        "status": "provisional",
        "validated_count": 1,
        "failed_count": 0,
        "created_at": today,
        "last_validated": today,
        "last_failed": None,
        "tags": data.get("tags", []),
        "skip_when": data.get("skip_when", ""),
        "checkpoint": data.get("checkpoint", ""),
        "expected_outcome": data.get("expected_outcome", ""),
        "evidence": data.get("evidence", []),
        "created_from": data.get("created_from", ""),
    }

    if args.type == "sop":
        asset["steps"] = data.get("steps", [])
    elif args.type == "pref":
        asset["rationale"] = data.get("rationale", "")
        asset["tradeoff"] = data.get("tradeoff", "")
    else:
        asset["method"] = data.get("method", "")

    existing.append(asset)
    write_json_atomic(filepath, existing)

    append_evolution(args.memory_dir, {
        "ts": utc_now_iso(),
        "event": "create",
        "asset_type": args.type,
        "asset_id": asset_id,
        "confidence": asset["confidence"],
    })

    print(json.dumps(asset, ensure_ascii=False, indent=2))


def cmd_update(args):
    found_file = None
    found_index = None
    found_asset = None
    found_assets_list = None

    for asset_type in VALID_TYPES:
        filepath = os.path.join(args.memory_dir, type_to_filename(asset_type))
        assets = read_json_list(filepath)
        for i, a in enumerate(assets):
            if a.get("id") == args.id:
                found_file = filepath
                found_index = i
                found_asset = a
                found_assets_list = assets
                break
        if found_asset:
            break

    if found_asset is None:
        print(f"Error: asset '{args.id}' not found in any file", file=sys.stderr)
        sys.exit(1)

    changes = {}

    if args.confidence is not None:
        changes["confidence"] = {"from": found_asset.get("confidence"), "to": args.confidence}
        found_asset["confidence"] = args.confidence

    if args.status is not None:
        if args.status not in VALID_STATUSES:
            print(f"Error: invalid status '{args.status}', must be one of {VALID_STATUSES}", file=sys.stderr)
            sys.exit(1)
        changes["status"] = {"from": found_asset.get("status"), "to": args.status}
        found_asset["status"] = args.status

    new_status = confidence_to_status(found_asset.get("confidence", 0.70))
    if found_asset.get("status") != new_status:
        changes["status_auto"] = {"from": found_asset.get("status"), "to": new_status}
        found_asset["status"] = new_status

    found_asset["version"] = found_asset.get("version", 1) + 1
    changes["version"] = found_asset["version"]

    found_assets_list[found_index] = found_asset
    write_json_atomic(found_file, found_assets_list)

    append_evolution(args.memory_dir, {
        "ts": utc_now_iso(),
        "event": "update",
        "asset_id": args.id,
        "changes": changes,
    })

    print(json.dumps(found_asset, ensure_ascii=False, indent=2))


def cmd_list(args):
    filepath = os.path.join(args.memory_dir, type_to_filename(args.type))
    assets = read_json_list(filepath)

    if args.status:
        if args.status not in VALID_STATUSES:
            print(f"Error: invalid status '{args.status}', must be one of {VALID_STATUSES}", file=sys.stderr)
            sys.exit(1)
        assets = [a for a in assets if a.get("status") == args.status]

    summary = [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "type": args.type,
            "confidence": a.get("confidence"),
            "status": a.get("status"),
            "validated_count": a.get("validated_count"),
        }
        for a in assets
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_export_portable(args):
    min_conf = args.min_confidence
    result_assets = {"genes": [], "sops": [], "prefs": []}

    for asset_type in VALID_TYPES:
        filepath = os.path.join(args.memory_dir, type_to_filename(asset_type))
        assets = read_json_list(filepath)
        key = f"{asset_type}s"
        for a in assets:
            if a.get("status") == "active" and a.get("confidence", 0) >= min_conf:
                a["original_confidence"] = a["confidence"]
                a["confidence"] = 0.60
                a["status"] = "provisional"
                result_assets[key].append(a)

    source_project = "unknown"
    state_path = os.path.join(os.path.dirname(args.memory_dir), ".retro", "state.json")
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            source_project = state.get("project_name", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    portable = {
        "schema_version": "1.0",
        "exported_at": utc_today_iso(),
        "exported_by": "\u5927\u9505",
        "source_project": source_project,
        "assets": result_assets,
    }

    export_dir = os.path.join(args.memory_dir, "exports")
    os.makedirs(export_dir, exist_ok=True)
    write_json_atomic(os.path.join(export_dir, "portable.json"), portable)

    print(json.dumps(portable, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="CRUD operations for Gene/SOP/Pref assets")
    parser.add_argument("--memory-dir", default="./memory", help="Path to memory directory (default: ./memory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create a new asset")
    p_create.add_argument("--type", required=True, choices=VALID_TYPES, help="Asset type")
    p_create.add_argument("--data", required=True, help="JSON object with asset data")

    p_update = sub.add_parser("update", help="Update an existing asset")
    p_update.add_argument("--id", required=True, help="Asset ID to update")
    p_update.add_argument("--confidence", type=float, help="New confidence value")
    p_update.add_argument("--status", help="New status (active, provisional, deprecated)")

    p_list = sub.add_parser("list", help="List assets by type")
    p_list.add_argument("--type", required=True, choices=VALID_TYPES, help="Asset type to list")
    p_list.add_argument("--status", help="Filter by status (active, provisional, deprecated)")

    p_export = sub.add_parser("export-portable", help="Export portable assets")
    p_export.add_argument("--min-confidence", type=float, default=0.70, help="Minimum confidence (default: 0.70)")

    args = parser.parse_args()

    if not os.path.isdir(args.memory_dir):
        print(f"Error: memory directory '{args.memory_dir}' does not exist. Run init_memory.py first.", file=sys.stderr)
        sys.exit(1)

    dispatch = {
        "create": cmd_create,
        "update": cmd_update,
        "list": cmd_list,
        "export-portable": cmd_export_portable,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
