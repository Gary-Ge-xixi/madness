#!/usr/bin/env python3
"""Quality check a retrospective report against red-line rules."""

import argparse
import json
import re
import sys


def read_report(file_path: str | None) -> str:
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Error: Cannot read '{file_path}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            print("Reading report from stdin (Ctrl+D to end)...", file=sys.stderr)
        return sys.stdin.read()


def find_section(text: str, keywords: list[str]) -> str:
    """Extract text from a section whose heading contains any of the keywords."""
    lines = text.split("\n")
    result_lines = []
    capturing = False
    for line in lines:
        if re.match(r"^#{1,4}\s", line):
            if capturing:
                break  # hit next section heading
            if any(kw in line for kw in keywords):
                capturing = True
                continue
        if capturing:
            result_lines.append(line)
    return "\n".join(result_lines)


def check_evidence_quotes(text: str) -> dict:
    """Rule 1: Friction/problem sections should contain content-validated user quotes."""
    section = find_section(text, ["\u5361\u4f4f", "\u6469\u64e6", "\u5faa\u73af", "\u95ee\u9898"])
    if not section.strip():
        return {"rule": "evidence_quotes", "passed": False, "score": 0,
                "detail": "\u672a\u627e\u5230\u201c\u5361\u4f4f/\u6469\u64e6/\u95ee\u9898\u201d\u76f8\u5173\u7ae0\u8282"}

    quote_patterns = re.findall(r"\u300c[^\u300d]+\u300d", section)
    quote_patterns += re.findall(r"\u201c[^\u201d]+\u201d", section)
    quote_patterns += re.findall(r'"[^"]{2,}"', section)
    quote_count = len(quote_patterns)

    problem_items = re.findall(r"^-\s+\*\*(\u73b0\u8c61|\u95ee\u9898)", section, re.MULTILINE)
    numbered_items = re.findall(r"^\d+[\.\uff0e\)]\s", section, re.MULTILINE)
    problem_count = max(len(problem_items) + len(numbered_items), 1)

    ratio = quote_count / problem_count if problem_count else 0
    base_score = min(10, int(10 * min(ratio, 1.0)))

    # Check if quotes contain date/session identifiers
    session_date_pattern = re.compile(
        r"\u4f1a\u8bdd|session|\d{1,2}-\d{1,2}|\u7b2c.*\u8f6e"
    )
    quotes_with_id = sum(1 for q in quote_patterns if session_date_pattern.search(q))
    id_ratio = quotes_with_id / len(quote_patterns) if quote_patterns else 0
    bonus = 5 if id_ratio >= 0.5 else 0

    score = min(15, base_score + bonus)
    passed = quote_count >= problem_count
    detail = (f"Found {quote_count} quotes for {problem_count} friction items; "
              f"{quotes_with_id}/{len(quote_patterns)} quotes have session/date identifiers")
    return {"rule": "evidence_quotes", "passed": passed, "score": score, "detail": detail}


def check_actionable_steps(text: str) -> dict:
    """Rule 2: Improvement items should contain action verbs and checkpoints."""
    section = find_section(text, ["\u6539\u8fdb", "SOP", "\u884c\u52a8", "\u5efa\u8bae", "\u4e0b\u4e00\u6b65"])
    if not section.strip():
        return {"rule": "actionable_steps", "passed": False, "score": 0,
                "detail": "\u672a\u627e\u5230\u201c\u6539\u8fdb/\u884c\u52a8/\u5efa\u8bae\u201d\u76f8\u5173\u7ae0\u8282"}

    items = re.findall(r"^[-*]\s+.+", section, re.MULTILINE)
    if not items:
        items = re.findall(r"^\d+[\.\uff0e\)]\s+.+", section, re.MULTILINE)
    if not items:
        return {"rule": "actionable_steps", "passed": False, "score": 5,
                "detail": "No improvement items found in section"}

    action_verb_pattern = re.compile(
        r"\u5b9a\u4e49|\u9a8c\u8bc1|\u8fd0\u884c|\u8f93\u51fa|\u68c0\u67e5|\u521b\u5efa|\u5220\u9664|\u4fee\u6539|\u6d4b\u8bd5|\u914d\u7f6e|\u90e8\u7f72|\u8fc1\u79fb|\u91cd\u6784|\u6dfb\u52a0|\u79fb\u9664|\u66f4\u65b0|\u786e\u8ba4|\u5ba1\u67e5"
    )
    checkpoint_pattern = re.compile(
        r"\u68c0\u67e5\u70b9|\u9884\u671f\u6548\u679c|\u9a8c\u6536\u6807\u51c6|\u5224\u65ad\u6807\u51c6|\u5b8c\u6210\u6807\u5fd7"
    )

    with_action_verbs = 0
    with_checkpoints = 0
    for item in items:
        verb_matches = action_verb_pattern.findall(item)
        if len(verb_matches) >= 2:
            with_action_verbs += 1
        if checkpoint_pattern.search(item):
            with_checkpoints += 1

    total = len(items)
    verb_ratio = with_action_verbs / total if total else 0
    base_score = min(10, int(10 * min(verb_ratio / 0.8, 1.0)))

    checkpoint_ratio = with_checkpoints / total if total else 0
    bonus = 5 if checkpoint_ratio >= 0.5 else 0

    score = min(15, base_score + bonus)
    passed = verb_ratio >= 0.8
    detail = (f"{with_action_verbs}/{total} items have >=2 action verbs; "
              f"{with_checkpoints}/{total} items have checkpoint keywords")
    return {"rule": "actionable_steps", "passed": passed, "score": score, "detail": detail}


def check_best_practice_scope(text: str) -> dict:
    """Rule 3: Best practices should contain derivation process and scope boundaries."""
    section = find_section(text, ["\u6700\u4f73\u5b9e\u8df5", "\u6210\u529f\u6a21\u5f0f", "\u505a\u5f97\u597d"])
    if not section.strip():
        return {"rule": "best_practice_scope", "passed": False, "score": 0,
                "detail": "\u672a\u627e\u5230\u201c\u6700\u4f73\u5b9e\u8df5/\u6210\u529f\u6a21\u5f0f\u201d\u76f8\u5173\u7ae0\u8282"}

    # Check for derivation process
    derivation_pattern = re.compile(
        r"\u4ece.*\u5b66\u5230|\u56e0\u6b64|\u6240\u4ee5|\u63a8\u5bfc|\u56e0\u4e3a.*\u6240\u4ee5|\u6839\u636e.*\u5f97\u51fa"
    )
    derivation_matches = derivation_pattern.findall(section)
    derivation_score = min(8, len(derivation_matches) * 2)

    # Check for scope boundary
    scope_pattern = re.compile(
        r"\u9002\u7528|\u4e0d\u9002\u7528|\u4f55\u65f6\u7528|\u4f55\u65f6\u4e0d\u7528|\u573a\u666f|\u8fb9\u754c"
    )
    scope_matches = scope_pattern.findall(section)
    scope_score = min(7, len(scope_matches) * 2)

    score = derivation_score + scope_score
    passed = derivation_score >= 4 and scope_score >= 4
    detail = (f"Derivation: {len(derivation_matches)} markers ({derivation_score}/8 pts); "
              f"Scope: {len(scope_matches)} markers ({scope_score}/7 pts)")
    return {"rule": "best_practice_scope", "passed": passed, "score": score, "detail": detail}


def check_no_vague_language(text: str) -> dict:
    """Rule 4: No vague/empty phrases."""
    vague_phrases = [
        "\u663e\u8457\u63d0\u5347", "\u4e0d\u591f\u5f7b\u5e95", "\u8fdb\u4e00\u6b65\u4f18\u5316",
        "\u6709\u5f85\u63d0\u9ad8", "\u9700\u8981\u52a0\u5f3a", "\u6548\u679c\u660e\u663e",
        "\u6574\u4f53\u63d0\u5347", "\u5927\u5e45\u6539\u5584",
    ]
    violations = []
    for phrase in vague_phrases:
        occurrences = len(re.findall(re.escape(phrase), text))
        if occurrences > 0:
            violations.append(f"'{phrase}' x{occurrences}")

    total_violations = sum(int(v.split("x")[1]) for v in violations)
    passed = total_violations == 0
    score = max(0, 15 - total_violations * 3)
    if passed:
        detail = "No vague phrases detected"
    else:
        detail = f"{total_violations} vague phrases found: {', '.join(violations)}"
    return {"rule": "no_vague_language", "passed": passed, "score": score, "detail": detail}


def check_two_phase_analysis(text: str) -> dict:
    """Rule 5: Report should show two-phase analysis structure."""
    phase_a = bool(re.search(r"\u9636\u6bb5\s*A|\u7ed3\u6784\u5316\u63d0\u53d6|Phase\s*A|\u9636\u6bb5A", text))
    phase_b = bool(re.search(r"\u9636\u6bb5\s*B|\u6df1\u5ea6\u5f52\u56e0|Phase\s*B|\u9636\u6bb5B", text))
    group_ab = bool(re.search(r"\u5206\u6790\u7ec4\s*A", text) and re.search(r"\u5206\u6790\u7ec4\s*B", text))
    gene_verify = bool(re.search(r"Gene\s*\u9a8c\u8bc1\u62a5\u544a", text))

    passed = (phase_a and phase_b) or group_ab or gene_verify

    if phase_a and phase_b:
        detail = "Found \u9636\u6bb5 A and \u9636\u6bb5 B markers"
    elif group_ab:
        detail = "Found \u5206\u6790\u7ec4 A and \u5206\u6790\u7ec4 B markers"
    elif gene_verify:
        detail = "Found Gene \u9a8c\u8bc1\u62a5\u544a marker (A.0 indicator)"
    else:
        indicators = []
        if phase_a:
            indicators.append("\u9636\u6bb5 A")
        if phase_b:
            indicators.append("\u9636\u6bb5 B")
        detail = f"Missing two-phase indicators. Found: {', '.join(indicators) or 'none'}"

    score = 13 if passed else (6 if phase_a or phase_b else 0)
    return {"rule": "two_phase_analysis", "passed": passed, "score": score, "detail": detail}


def check_summary_detail_split(text: str) -> dict:
    """Rule 6: Report should have summary/detail two-layer structure."""
    has_summary = bool(re.search(r"摘要", text)) and bool(
        re.search(r"一句话诊断|一句话总结", text)
    )
    has_detail = bool(re.search(r"详情|完整报告|展开详情", text))

    if has_summary and has_detail:
        return {"rule": "summary_detail_split", "passed": True, "score": 12,
                "detail": "Found both summary and detail markers"}
    elif has_summary:
        return {"rule": "summary_detail_split", "passed": False, "score": 6,
                "detail": "Found summary markers but missing detail markers"}
    else:
        return {"rule": "summary_detail_split", "passed": False, "score": 0,
                "detail": "Missing summary/detail split markers"}


def check_goal_alignment(text: str, state_path: str = None) -> dict:
    """Rule 7: Report should reference project goals if available."""
    # Try to read state.json to get goals
    goals = []
    if state_path:
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            goals = state.get("goals", [])
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    if not goals:
        # No goals defined — auto pass
        return {"rule": "goal_alignment", "passed": True, "score": 15,
                "detail": "No goals defined in state.json — auto pass"}

    mentioned = 0
    for g in goals:
        goal_text = g.get("goal", "") if isinstance(g, dict) else str(g)
        # Extract keywords from goal (>=2 char words)
        keywords = re.findall(r"[\w\u4e00-\u9fff]{2,}", goal_text.lower())
        # Check if any keyword appears in the report
        for kw in keywords:
            if kw in text.lower():
                mentioned += 1
                break

    total = len(goals)
    ratio = mentioned / total if total else 0
    passed = ratio >= 0.5
    score = int(15 * min(ratio / 0.5, 1.0)) if not passed else 15
    detail = f"{mentioned}/{total} project goals referenced in report"
    return {"rule": "goal_alignment", "passed": passed, "score": score, "detail": detail}


def main():
    parser = argparse.ArgumentParser(description="Quality check a retrospective report against red-line rules.")
    parser.add_argument("--file", default=None, help="Path to report file (reads stdin if omitted)")
    parser.add_argument("--state-path", default=None, help="Path to state.json for goal alignment check")
    args = parser.parse_args()

    text = read_report(args.file)
    if not text.strip():
        print("Error: Report is empty.", file=sys.stderr)
        sys.exit(1)

    checks = [
        check_evidence_quotes(text),
        check_actionable_steps(text),
        check_best_practice_scope(text),
        check_no_vague_language(text),
        check_two_phase_analysis(text),
        check_summary_detail_split(text),
        check_goal_alignment(text, args.state_path),
    ]

    total_score = sum(c["score"] for c in checks)

    output_checks = []
    for c in checks:
        output_checks.append({
            "rule": c["rule"],
            "passed": c["passed"],
            "score": c["score"],
            "detail": c["detail"],
        })

    result = {
        "score": total_score,
        "checks": output_checks,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
