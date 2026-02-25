#!/usr/bin/env python3
"""Gene validation protocol: match assets against facets, compute compliance and confidence deltas."""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from lib import INJECTABLE_STATUSES, load_all_assets

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


def match_facet_to_asset(facet: dict, asset: dict) -> str:
    """Score facet-asset match using weighted conditions. Returns 'high'|'medium'|'low'|'none'."""
    score = 0

    # Condition 1: goal_category matches asset domain (+2)
    goal_cat = facet.get("goal_category", "")
    domains = asset.get("domain", [])
    if isinstance(domains, str):
        domains = [domains]
    if goal_cat and any(goal_cat.lower() in d.lower() or d.lower() in goal_cat.lower() for d in domains):
        score += 2

    # Condition 2: friction keywords match trigger (+2)
    trigger_kw = extract_keywords(asset.get("trigger", ""))
    frictions = facet.get("friction", [])
    if isinstance(frictions, str):
        frictions = [frictions]
    for friction in frictions:
        if trigger_kw & extract_keywords(friction):
            score += 2
            break

    # Condition 3: goal/title keyword overlap (each +1, max 3)
    title_kw = extract_keywords(asset.get("title", ""))
    goal_kw = extract_keywords(facet.get("goal", ""))
    if title_kw and goal_kw:
        overlap_count = len(title_kw & goal_kw)
        score += min(overlap_count, 3)

    # Condition 4: learning/key_decision match trigger (+1)
    if trigger_kw:
        learning_kw = extract_keywords(facet.get("learning", ""))
        decision_kw = extract_keywords(facet.get("key_decision", ""))
        if (learning_kw & trigger_kw) or (decision_kw & trigger_kw):
            score += 1

    # Scoring thresholds
    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    elif score >= 1:
        return "low"
    else:
        return "none"


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
    validated_highlights = []
    summary = {"validated": 0, "weak_validated": 0, "ineffective": 0, "no_match": 0, "over_scoped": 0}

    for asset in assets:
        aid = asset.get("id", "unknown")
        atype = asset.get("asset_type", "gene")
        atitle = asset.get("title", "")
        astatus = asset.get("status", "provisional")
        current_conf = float(asset.get("confidence", 0.5))

        # Step 1: Scene matching with three-level scoring
        high_facets = []
        medium_facets = []
        for f in facets:
            level = match_facet_to_asset(f, asset)
            if level == "high":
                high_facets.append(f)
            elif level == "medium":
                medium_facets.append(f)

        matched_facets = high_facets + medium_facets
        needs_semantic_review = len(high_facets) == 0 and len(medium_facets) > 0

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

        # Exploration mode exemption
        explore_count = sum(1 for f in matched_facets if f.get("goal_category") == "explore_learn")
        exploration_exempt = False
        if explore_count > len(matched_facets) / 2 and compliance == "non_compliant":
            compliance = "exploration_exempt"
            judgment = "exploration_exempt"
            delta = 0.0
            exploration_exempt = True

        new_conf = clamp(round(current_conf + delta, 4))

        result_entry = {
            "asset_id": aid, "asset_type": atype, "asset_title": atitle,
            "match_status": "matched", "matched_sessions": matched_ids,
            "compliance": compliance, "judgment": judgment,
            "suggested_delta": delta,
            "current_confidence": current_conf, "new_confidence": new_conf,
            "evidence_sessions": matched_ids[:5],
            "exploration_exempt": exploration_exempt,
        }
        if needs_semantic_review:
            result_entry["needs_semantic_review"] = True

        # Add suggested_fix for negative judgments
        if judgment == "ineffective":
            result_entry["suggested_fix"] = (
                f"Gene '{atitle}' was complied with but didn't achieve expected outcome. "
                f"Suggestion: check if trigger is too broad (matched {len(matched_facets)} facets), "
                f"or if method steps need refinement."
            )
        elif judgment == "over_scoped":
            result_entry["suggested_fix"] = (
                f"Gene '{atitle}' was not complied with but session still succeeded. "
                f"Suggestion: narrow trigger conditions, add skip_when to exempt this scenario."
            )

        results.append(result_entry)

        # Collect validated_highlights
        # Type 1: promotion_candidate — provisional asset validated with confidence increase
        if astatus == "provisional" and new_conf > current_conf:
            validated_highlights.append({
                "type": "promotion_candidate",
                "asset_id": aid,
                "asset_title": atitle,
                "old_confidence": current_conf,
                "new_confidence": new_conf,
            })

        # Type 2: compliance_success — active asset complied with, outcome fully_achieved
        if astatus == "active" and compliance == "compliant" and outcome == "fully_achieved":
            validated_highlights.append({
                "type": "compliance_success",
                "asset_id": aid,
                "asset_title": atitle,
                "evidence_session": matched_ids[0] if matched_ids else "",
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

    # Count needs_attention
    summary["needs_attention"] = sum(
        1 for r in results
        if r.get("suggested_fix") or r.get("alert")
    )

    return {
        "validated_at": date.today().isoformat(),
        "total_assets": len(assets),
        "results": results,
        "validated_highlights": validated_highlights,
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

    assets = load_all_assets(str(memory_dir), statuses=INJECTABLE_STATUSES)
    if not assets:
        print("Warning: no active/provisional assets found", file=sys.stderr)

    facets = load_facets(retro_dir, args.since)
    if not facets:
        print("Warning: no facets found", file=sys.stderr)

    report = validate(assets, facets)

    # Post-process: check consecutive failures from evolution.jsonl
    evolution_path = Path(args.memory_dir) / "evolution.jsonl"
    if evolution_path.exists():
        try:
            events = []
            with open(evolution_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))

            for r in report["results"]:
                aid = r["asset_id"]
                # Count consecutive validate failures (working backwards)
                consecutive = 0
                for ev in reversed(events):
                    if ev.get("asset_id") == aid and ev.get("event") == "validate":
                        details = ev.get("details", {})
                        if details.get("judgment") in ("ineffective", "over_scoped"):
                            consecutive += 1
                        else:
                            break
                    elif ev.get("asset_id") == aid:
                        break

                if consecutive >= 3:
                    r["alert"] = (
                        f"WARNING: Gene '{r.get('asset_title', aid)}' has {consecutive} "
                        f"consecutive validation failures. Consider deprecating or rewriting trigger/method."
                    )
        except (json.JSONDecodeError, OSError):
            pass

    # Recount needs_attention after post-processing
    report["summary"]["needs_attention"] = sum(
        1 for r in report["results"]
        if r.get("suggested_fix") or r.get("alert")
    )

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
