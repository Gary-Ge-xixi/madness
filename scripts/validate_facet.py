#!/usr/bin/env python3
"""Validate facet schema and manage facet cache."""

import argparse
import json
import os
import re
import sys

REQUIRED_FIELDS = {
    "session_id": str,
    "date": str,
    "duration_min": (int, float),
    "goal": str,
    "goal_category": str,
    "outcome": str,
    "friction": list,
    "loop_detected": bool,
    "loop_detail": str,
    "key_decision": str,
    "learning": str,
    "tools_used": list,
    "files_changed": (int, float),
}

GOAL_CATEGORIES = {
    "implement", "refine_methodology", "debug_fix", "explore_learn",
    "review_calibrate", "plan_design", "visualize_report",
}

OUTCOMES = {"fully_achieved", "partially_achieved", "not_achieved"}

FRICTION_ENUM = {
    "prompt_too_long", "classification_ambiguity", "serial_bottleneck",
    "data_architecture_mismatch", "scope_creep", "tool_misuse",
    "context_limit", "domain_knowledge_gap", "rework_from_poor_planning",
    "ai_dependency", "other",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_facet(data):
    """Validate a facet dict. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if not isinstance(data, dict):
        return ["Input must be a JSON object"], []

    # Required fields and type checks
    for field, expected in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: {field}")
            continue
        if isinstance(expected, tuple):
            if not isinstance(data[field], expected):
                errors.append(f"Field '{field}' must be {' or '.join(t.__name__ for t in expected)}, got {type(data[field]).__name__}")
        else:
            if not isinstance(data[field], expected):
                errors.append(f"Field '{field}' must be {expected.__name__}, got {type(data[field]).__name__}")

    # date pattern
    if "date" in data and isinstance(data.get("date"), str):
        if not DATE_RE.match(data["date"]):
            errors.append(f"Field 'date' must match YYYY-MM-DD, got '{data['date']}'")

    # goal_category enum
    if "goal_category" in data and isinstance(data.get("goal_category"), str):
        if data["goal_category"] not in GOAL_CATEGORIES:
            errors.append(f"Invalid goal_category '{data['goal_category']}'. Must be one of: {sorted(GOAL_CATEGORIES)}")

    # outcome enum
    if "outcome" in data and isinstance(data.get("outcome"), str):
        if data["outcome"] not in OUTCOMES:
            errors.append(f"Invalid outcome '{data['outcome']}'. Must be one of: {sorted(OUTCOMES)}")

    # friction enum values
    if "friction" in data and isinstance(data.get("friction"), list):
        for i, v in enumerate(data["friction"]):
            if not isinstance(v, str):
                errors.append(f"friction[{i}] must be a string, got {type(v).__name__}")
            elif v not in FRICTION_ENUM:
                errors.append(f"Invalid friction value '{v}'. Must be one of: {sorted(FRICTION_ENUM)}")

    # ai_collab
    if "ai_collab" not in data:
        errors.append("Missing required field: ai_collab")
    elif not isinstance(data["ai_collab"], dict):
        errors.append("Field 'ai_collab' must be a dict")
    else:
        # Core 3 keys are required
        for key in ("sycophancy", "logic_leap", "lazy_prompting"):
            if key not in data["ai_collab"]:
                errors.append(f"ai_collab missing key: {key}")
            elif not isinstance(data["ai_collab"][key], str):
                errors.append(f"ai_collab.{key} must be a string")
        # Extended 2 keys are optional (backward compatible: warn if missing)
        for key in ("automation_surrender", "anchoring_effect"):
            if key not in data["ai_collab"]:
                warnings.append(f"ai_collab missing optional key: {key} (recommended for v2)")
            elif not isinstance(data["ai_collab"][key], str):
                errors.append(f"ai_collab.{key} must be a string")

    # extraction_confidence (optional, warn if missing)
    if "extraction_confidence" in data:
        ec = data["extraction_confidence"]
        if not isinstance(ec, (int, float)):
            errors.append("Field 'extraction_confidence' must be a number")
        elif not (0.0 <= ec <= 1.0):
            errors.append(f"Field 'extraction_confidence' must be between 0.0 and 1.0, got {ec}")
    else:
        warnings.append("Missing optional field: extraction_confidence (recommended for quality tracking)")

    # domain_knowledge_gained
    if "domain_knowledge_gained" not in data:
        errors.append("Missing required field: domain_knowledge_gained")
    elif not isinstance(data["domain_knowledge_gained"], str):
        errors.append("Field 'domain_knowledge_gained' must be a string")

    # Warnings for empty optional-ish fields
    if isinstance(data.get("learning"), str) and data["learning"] == "":
        warnings.append("'learning' is empty")
    if isinstance(data.get("key_decision"), str) and data["key_decision"] == "":
        warnings.append("'key_decision' is empty")
    if isinstance(data.get("domain_knowledge_gained"), str) and data["domain_knowledge_gained"] == "":
        warnings.append("'domain_knowledge_gained' is empty")

    return errors, warnings


def read_input(input_arg):
    """Read JSON from file path or stdin."""
    if input_arg is None or input_arg == "-":
        return json.load(sys.stdin)
    with open(input_arg, "r") as f:
        return json.load(f)


def get_facets_dir(retro_dir):
    return os.path.join(retro_dir, "facets")


def cmd_validate(args):
    try:
        data = read_input(args.input)
    except (json.JSONDecodeError, OSError) as e:
        print(json.dumps({"valid": False, "errors": [str(e)], "warnings": []}))
        sys.exit(1)

    errors, warnings = validate_facet(data)
    result = {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_cache(args):
    try:
        data = read_input(args.input)
    except (json.JSONDecodeError, OSError) as e:
        print(json.dumps({"cached": False, "errors": [str(e)]}))
        sys.exit(1)

    errors, _ = validate_facet(data)
    if errors:
        print(json.dumps({"cached": False, "errors": errors}))
        sys.exit(1)

    facets_dir = get_facets_dir(args.retro_dir)
    os.makedirs(facets_dir, exist_ok=True)

    session_id = args.session_id
    path = os.path.join(facets_dir, f"{session_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(json.dumps({"cached": True, "path": path}))


def cmd_list_cached(args):
    facets_dir = get_facets_dir(args.retro_dir)
    if not os.path.isdir(facets_dir):
        print(json.dumps([]))
        return
    ids = sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(facets_dir)
        if f.endswith(".json")
    )
    print(json.dumps(ids, indent=2))


def cmd_list_uncached(args):
    try:
        sessions = json.loads(args.sessions)
    except json.JSONDecodeError as e:
        print(f"Error parsing --sessions JSON: {e}", file=sys.stderr)
        sys.exit(1)

    facets_dir = get_facets_dir(args.retro_dir)
    cached = set()
    if os.path.isdir(facets_dir):
        cached = {
            os.path.splitext(f)[0]
            for f in os.listdir(facets_dir)
            if f.endswith(".json")
        }

    uncached = [s for s in sessions if s.get("session_id") not in cached]
    print(json.dumps(uncached, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Validate facet schema and manage facet cache")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate a facet JSON")
    p_val.add_argument("--input", default="-", help="Input file or - for stdin (default: stdin)")
    p_val.set_defaults(func=cmd_validate)

    p_cache = sub.add_parser("cache", help="Validate and cache a facet")
    p_cache.add_argument("--session-id", required=True, help="Session ID for cache filename")
    p_cache.add_argument("--input", default="-", help="Input file or - for stdin (default: stdin)")
    p_cache.add_argument("--retro-dir", default=".retro", help="Retro directory (default: .retro)")
    p_cache.set_defaults(func=cmd_cache)

    p_list = sub.add_parser("list-cached", help="List cached facet session IDs")
    p_list.add_argument("--retro-dir", default=".retro", help="Retro directory (default: .retro)")
    p_list.set_defaults(func=cmd_list_cached)

    p_unc = sub.add_parser("list-uncached", help="List sessions not yet cached")
    p_unc.add_argument("--sessions", required=True, help="JSON array of session objects")
    p_unc.add_argument("--retro-dir", default=".retro", help="Retro directory (default: .retro)")
    p_unc.set_defaults(func=cmd_list_uncached)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
