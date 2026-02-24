#!/usr/bin/env python3
"""Inject memory rules into CLAUDE.md's madness:memory-inject section."""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path


MARKER_START = "<!-- madness:memory-inject start -->"
MARKER_END = "<!-- madness:memory-inject end -->"
RULE_PATTERN = re.compile(r"^#\s*R\d+\s*\[(\w+):(.+?),\s*c:([\d.]+),\s*v:(\d+)\]")


def load_assets(memory_dir: Path) -> list[dict]:
    """Load and merge assets from genes.json, sops.json, prefs.json."""
    assets = []
    for filename, asset_type in [("genes.json", "gene"), ("sops.json", "sop"), ("prefs.json", "pref")]:
        filepath = memory_dir / filename
        if not filepath.exists():
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("items", data.get("assets", []))
            for item in items:
                item.setdefault("asset_type", asset_type)
                assets.append(item)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {filepath}: {e}", file=sys.stderr)
    return assets


def filter_assets(assets: list[dict]) -> list[dict]:
    """Filter by status and confidence, sort by confidence descending."""
    valid_statuses = {"active", "provisional"}
    filtered = [
        a for a in assets
        if a.get("status") in valid_statuses and float(a.get("confidence", 0)) >= 0.50
    ]
    filtered.sort(key=lambda a: float(a.get("confidence", 0)), reverse=True)
    return filtered


def parse_existing_rules(section_content: str) -> dict[str, dict]:
    """Parse existing rules from the inject section, keyed by asset id."""
    rules = {}
    for line in section_content.splitlines():
        m = RULE_PATTERN.match(line.strip())
        if m:
            rules[m.group(2).strip()] = {
                "type": m.group(1),
                "id": m.group(2).strip(),
                "confidence": float(m.group(3)),
                "version": int(m.group(4)),
            }
    return rules


def summarize_method(steps) -> str:
    """Summarize method/steps array into <=2 lines of pseudocode."""
    if not steps or not isinstance(steps, list):
        return "    APPLY standard_procedure"
    lines = []
    for i, step in enumerate(steps[:2]):
        text = step if isinstance(step, str) else step.get("action", step.get("description", str(step)))
        lines.append(f"    {text}")
    if len(steps) > 2:
        lines[-1] += f"  # ...and {len(steps) - 2} more steps"
    return "\n".join(lines)


def generate_rule_block(index: int, asset: dict, version: int, confidence: float) -> str:
    """Generate a single rule block."""
    asset_type = asset.get("asset_type", "gene")
    asset_id = asset.get("id", f"unknown_{index}")
    trigger = asset.get("trigger", "condition_unspecified")
    skip_when = asset.get("skip_when", "")
    outcome = asset.get("expected_outcome", asset.get("checkpoint", ""))

    if asset_type == "gene":
        body = summarize_method(asset.get("method"))
    elif asset_type == "sop":
        body = summarize_method(asset.get("steps"))
    else:
        rationale = asset.get("rationale", "apply_preference")
        body = f"    PREFER {asset.get('preferred', 'option_a')}: {rationale}"

    block = f"# R{index} [{asset_type}:{asset_id}, c:{confidence:.2f}, v:{version}]\n"
    block += f"IF {trigger}:\n"
    block += f"{body}\n"
    if skip_when:
        block += f"# skip_when: {skip_when}\n"
    if outcome:
        block += f"# {outcome}\n"
    return block


def merge_rules(existing: dict, new_assets: list[dict], max_rules: int) -> tuple[list[dict], list[dict]]:
    """Merge new assets with existing rules, return (merged_assets, actions)."""
    actions = []
    merged = []
    seen_ids = set()

    for asset in new_assets:
        aid = asset.get("id", "")
        if aid in seen_ids:
            continue
        seen_ids.add(aid)

        if aid in existing:
            old = existing[aid]
            new_version = old["version"] + 1
            new_conf = max(float(asset.get("confidence", 0)), old["confidence"])
            asset["_version"] = new_version
            asset["_confidence"] = new_conf
            actions.append({
                "type": "merge", "asset_id": aid,
                "old_version": old["version"], "new_version": new_version
            })
        else:
            asset["_version"] = 1
            asset["_confidence"] = float(asset.get("confidence", 0))
            actions.append({"type": "new", "asset_id": aid, "position": len(merged) + 1})
        merged.append(asset)

    # Sort by confidence, trim to max_rules
    merged.sort(key=lambda a: a["_confidence"], reverse=True)
    if len(merged) > max_rules:
        dropped = merged[max_rules:]
        merged = merged[:max_rules]
        for d in dropped:
            actions.append({"type": "replace", "asset_id": d.get("id", ""), "replaced_id": d.get("id", "")})

    return merged, actions


def build_section(merged: list[dict]) -> str:
    """Build the full inject section content."""
    today = date.today().isoformat()
    max_ver = max((a["_version"] for a in merged), default=1)
    lines = [MARKER_START, f"## \u590d\u76d8\u6c89\u6dc0\u89c4\u5219\u96c6\uff08v{max_ver}, {today}\uff09", ""]
    for i, asset in enumerate(merged, 1):
        block = generate_rule_block(i, asset, asset["_version"], asset["_confidence"])
        lines.append(block)
    lines.append(MARKER_END)
    return "\n".join(lines)


def inject(claudemd_path: Path, section: str) -> str:
    """Inject section into CLAUDE.md content, return new content."""
    if not claudemd_path.exists():
        return section + "\n"
    content = claudemd_path.read_text(encoding="utf-8")

    start_idx = content.find(MARKER_START)
    end_idx = content.find(MARKER_END)

    if start_idx != -1 and end_idx != -1:
        end_idx += len(MARKER_END)
        return content[:start_idx] + section + content[end_idx:]
    else:
        return content.rstrip() + "\n\n" + section + "\n"


def main():
    parser = argparse.ArgumentParser(description="Inject memory rules into CLAUDE.md")
    parser.add_argument("--claudemd", required=True, help="Path to CLAUDE.md")
    parser.add_argument("--memory-dir", default="memory", help="Directory containing gene/sop/pref JSON files")
    parser.add_argument("--max-rules", type=int, default=10, help="Maximum rules to inject")
    parser.add_argument("--backup", action="store_true", help="Create .bak backup before modifying")
    args = parser.parse_args()

    claudemd_path = Path(args.claudemd)
    memory_dir = Path(args.memory_dir)

    if not memory_dir.is_dir():
        print(f"Error: memory directory not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)

    # Step 1-3: Load, filter, sort assets
    assets = load_assets(memory_dir)
    filtered = filter_assets(assets)
    top_assets = filtered[:args.max_rules * 2]  # load extra for merge headroom

    # Step 5-6: Read CLAUDE.md, backup if requested
    if args.backup and claudemd_path.exists():
        shutil.copy2(claudemd_path, str(claudemd_path) + ".bak")

    # Step 7-8: Parse existing rules and merge
    existing_rules = {}
    if claudemd_path.exists():
        content = claudemd_path.read_text(encoding="utf-8")
        start_idx = content.find(MARKER_START)
        end_idx = content.find(MARKER_END)
        if start_idx != -1 and end_idx != -1:
            section_text = content[start_idx:end_idx]
            existing_rules = parse_existing_rules(section_text)

    merged, actions = merge_rules(existing_rules, top_assets, args.max_rules)

    # Step 9-11: Build section, inject, write atomically
    section = build_section(merged)
    new_content = inject(claudemd_path, section)

    tmp_path = str(claudemd_path) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, str(claudemd_path))
    except OSError as e:
        print(f"Error: failed to write {claudemd_path}: {e}", file=sys.stderr)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        sys.exit(1)

    # Step 12: Output change log
    rule_ids = [a.get("id", "") for a in merged]
    report = {
        "actions": actions,
        "total_rules": len(merged),
        "rules": rule_ids,
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
