#!/usr/bin/env python3
"""Gene validation protocol: match assets against facets, compute compliance and confidence deltas."""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


VALID_STATUSES = {"active", "provisional"}

JUDGMENT_MATRIX = {
    ("compliant", "fully_achieved"):     ("validated",         +0.05),
    ("compliant", "partially_achieved"): ("weak_validate",     +0.02),
    ("compliant", "not_achieved"):       ("ineffective",       -0.15),
    ("partial", "fully_achieved"):       ("partial_validate",  +0.02),
    ("partial", "partially_achieved"):   ("inconclusive",       0.00),
    ("partial", "not_achieved"):         ("inconclusive",       0.00),
    ("non_compliant", "fully_achieved"): ("over_scoped",       -0.10),
    ("non_compliant", "partially_achieved"): ("inconclusive",   0.00),
    ("non_compliant", "not_achieved"):   ("unrelated",          0.00),
}


def load_assets(memory_dir: Path) -> list[dict]:
    """Load active/provisional assets from genes.json, sops.json, prefs.json."""
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
                if item.get("status") in VALID_STATUSES:
                    assets.append(item)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {filepath}: {e}", file=sys.stderr)
    return assets


def load_facets(retro_dir: Path, since: str | None) -> list[dict]:
    """Load facets from retro_dir/facets/*.json, optionally filtered by date."""
    facets_dir = retro_dir / "facets"
    if not facets_dir.is_dir():
        print(f"Warning: facets directory not found: {facets_dir}", file=sys.stderr)
        return []

    facets = []
    for fp in sorted(facets_dir.glob("*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else [data]
            for facet in items:
                if since:
                    facet_date = facet.get("date", facet.get("created_at", ""))
                    if facet_date and facet_date < since:
                        continue
                facets.append(facet)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {fp}: {e}", file=sys.stderr)
    return facets


def extract_keywords(text: str) -> set[str]:
    """Extract lowercase keywords (>=2 chars) from text."""
    if not text:
        return set()
    words = re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())
    return set(words)


def match_facet_to_asset(facet: dict, asset: dict) -> bool:
    """Check if a facet matches an asset via keyword overlap."""
    # Condition 1: goal_category matches asset domain tags
    goal_cat = facet.get("goal_category", "")
    domains = asset.get("domain", [])
    if isinstance(domains, str):
        domains = [domains]
    if goal_cat and any(goal_cat.lower() in d.lower() or d.lower() in goal_cat.lower() for d in domains):
        return True

    # Condition 2: friction keywords relate to trigger
    trigger_kw = extract_keywords(asset.get("trigger", ""))
    frictions = facet.get("friction", [])
    if isinstance(frictions, str):
        frictions = [frictions]
    for friction in frictions:
        if trigger_kw & extract_keywords(friction):
            return True

    # Condition 3: goal contains keywords from title
    title_kw = extract_keywords(asset.get("title", ""))
    goal_kw = extract_keywords(facet.get("goal", ""))
    if title_kw and goal_kw and len(title_kw & goal_kw) >= 1:
        return True

    return False


def compute_compliance(asset: dict, matched_facets: list[dict]) -> tuple[str, float]:
    """Compute compliance rate and classification."""
    asset_type = asset.get("asset_type", "gene")

    # Collect all relevant text from matched facets
    facet_text_pool = set()
    for f in matched_facets:
        facet_text_pool |= extract_keywords(f.get("goal", ""))
        facet_text_pool |= extract_keywords(f.get("key_decision", ""))
        facet_text_pool |= extract_keywords(f.get("learning", ""))
        # Also check nested fields
        for key in ("decisions", "learnings", "key_decisions"):
            val = f.get(key, [])
            if isinstance(val, list):
                for item in val:
                    facet_text_pool |= extract_keywords(str(item))

    if not facet_text_pool:
        return "n/a", 0.0

    if asset_type == "gene":
        steps = asset.get("method", [])
    elif asset_type == "sop":
        steps = asset.get("steps", [])
    else:
        # Pref: check if preferred choice appears
        preferred = asset.get("preferred", "")
        rationale = asset.get("rationale", "")
        pref_kw = extract_keywords(preferred) | extract_keywords(rationale)
        if pref_kw & facet_text_pool:
            return "compliant", 1.0
        return "non_compliant", 0.0

    if not steps:
        return "n/a", 0.0

    matched_count = 0
    for step in steps:
        step_text = step if isinstance(step, str) else step.get("action", step.get("description", str(step)))
        step_kw = extract_keywords(step_text)
        if step_kw & facet_text_pool:
            matched_count += 1

    rate = matched_count / len(steps) if steps else 0.0
    if rate >= 0.8:
        return "compliant", rate
    elif rate < 0.5:
        return "non_compliant", rate
    else:
        return "partial", rate


def most_common_outcome(facets: list[dict]) -> str:
    """Return the most common outcome from matched facets."""
    counts: dict[str, int] = {}
    for f in facets:
        outcome = f.get("outcome", "")
        if outcome:
            counts[outcome] = counts.get(outcome, 0) + 1
    if not counts:
        return "not_achieved"
    return max(counts, key=counts.get)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def validate(assets: list[dict], facets: list[dict]) -> dict:
    """Run validation protocol on all assets against facets."""
    results = []
    summary = {"validated": 0, "weak_validated": 0, "ineffective": 0, "no_match": 0, "over_scoped": 0}

    for asset in assets:
        aid = asset.get("id", "unknown")
        atype = asset.get("asset_type", "gene")
        atitle = asset.get("title", "")
        current_conf = float(asset.get("confidence", 0.5))

        # Step 1: Scene matching
        matched_facets = [f for f in facets if match_facet_to_asset(f, asset)]
        matched_ids = list({f.get("session_id", f.get("id", "")) for f in matched_facets if f.get("session_id") or f.get("id")})

        if not matched_facets:
            results.append({
                "asset_id": aid, "asset_type": atype, "asset_title": atitle,
                "match_status": "no_match", "matched_sessions": [],
                "compliance": "n/a", "judgment": "no_match",
                "suggested_delta": 0.0,
                "current_confidence": current_conf, "new_confidence": current_conf,
                "evidence_sessions": [],
            })
            summary["no_match"] += 1
            continue

        # Step 2: Compliance detection
        compliance, _rate = compute_compliance(asset, matched_facets)
        if compliance == "n/a":
            compliance = "partial"

        # Step 3: Effect evaluation
        outcome = most_common_outcome(matched_facets)
        key = (compliance, outcome)
        judgment, delta = JUDGMENT_MATRIX.get(key, ("inconclusive", 0.0))
        new_conf = clamp(round(current_conf + delta, 4))

        results.append({
            "asset_id": aid, "asset_type": atype, "asset_title": atitle,
            "match_status": "matched", "matched_sessions": matched_ids,
            "compliance": compliance, "judgment": judgment,
            "suggested_delta": delta,
            "current_confidence": current_conf, "new_confidence": new_conf,
            "evidence_sessions": matched_ids[:5],
        })

        # Update summary
        if judgment == "validated":
            summary["validated"] += 1
        elif judgment == "weak_validate":
            summary["weak_validated"] += 1
        elif judgment == "ineffective":
            summary["ineffective"] += 1
        elif judgment == "over_scoped":
            summary["over_scoped"] += 1

    return {
        "validated_at": date.today().isoformat(),
        "total_assets": len(assets),
        "results": results,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Gene validation protocol")
    parser.add_argument("--memory-dir", default="memory", help="Directory with genes/sops/prefs JSON files")
    parser.add_argument("--retro-dir", default="retro", help="Directory with facets subdirectory")
    parser.add_argument("--since", default=None, help="Filter facets by date >= DATE (YYYY-MM-DD)")
    args = parser.parse_args()

    memory_dir = Path(args.memory_dir)
    retro_dir = Path(args.retro_dir)

    if not memory_dir.is_dir():
        print(f"Error: memory directory not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)
    if not retro_dir.is_dir():
        print(f"Error: retro directory not found: {retro_dir}", file=sys.stderr)
        sys.exit(1)

    # Validate --since format
    if args.since:
        try:
            datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            print(f"Error: --since must be in YYYY-MM-DD format, got: {args.since}", file=sys.stderr)
            sys.exit(1)

    assets = load_assets(memory_dir)
    if not assets:
        print("Warning: no active/provisional assets found", file=sys.stderr)

    facets = load_facets(retro_dir, args.since)
    if not facets:
        print("Warning: no facets found", file=sys.stderr)

    report = validate(assets, facets)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
