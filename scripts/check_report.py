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
    """Rule 1: Friction/problem sections should contain user quotes."""
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

    passed = quote_count >= problem_count
    score = 20 if passed else min(20, int(20 * quote_count / problem_count))
    detail = f"Found {quote_count} quotes for {problem_count} friction items"
    return {"rule": "evidence_quotes", "passed": passed, "score": score, "detail": detail}


def check_actionable_steps(text: str) -> dict:
    """Rule 2: Improvement items should contain step indicators."""
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

    step_pattern = re.compile(
        r"Step\s*\d|"
        r"\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]\u6b65|"
        r"[\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469]|"
        r"\d\.\s"
    )
    with_steps = sum(1 for item in items if step_pattern.search(item))
    total = len(items)
    ratio = with_steps / total if total else 0

    passed = ratio >= 0.8
    score = int(20 * min(ratio / 0.8, 1.0))
    detail = f"{with_steps}/{total} improvements have step indicators"
    return {"rule": "actionable_steps", "passed": passed, "score": score, "detail": detail}


def check_best_practice_scope(text: str) -> dict:
    """Rule 3: Best practices should contain scope info (when to use / when not to use)."""
    section = find_section(text, ["\u6700\u4f73\u5b9e\u8df5", "\u6210\u529f\u6a21\u5f0f", "\u505a\u5f97\u597d"])
    if not section.strip():
        return {"rule": "best_practice_scope", "passed": False, "score": 0,
                "detail": "\u672a\u627e\u5230\u201c\u6700\u4f73\u5b9e\u8df5/\u6210\u529f\u6a21\u5f0f\u201d\u76f8\u5173\u7ae0\u8282"}

    has_applicable = bool(re.search(r"\u9002\u7528|\u4f55\u65f6\u7528|\u573a\u666f", section))
    has_not_applicable = bool(re.search(r"\u4e0d\u9002\u7528|\u4f55\u65f6\u4e0d\u7528", section))

    # Softer check: "场景" appearing at least twice counts
    scene_count = len(re.findall(r"\u573a\u666f", section))

    if has_applicable and has_not_applicable:
        return {"rule": "best_practice_scope", "passed": True, "score": 20,
                "detail": "Found both \u9002\u7528 and \u4e0d\u9002\u7528 scope indicators"}
    elif scene_count >= 2:
        return {"rule": "best_practice_scope", "passed": True, "score": 20,
                "detail": f"Found {scene_count} \u573a\u666f references indicating scope coverage"}
    elif has_applicable:
        return {"rule": "best_practice_scope", "passed": False, "score": 10,
                "detail": "Missing \u2018\u4e0d\u9002\u7528\u573a\u666f\u2019 in best practices section"}
    else:
        return {"rule": "best_practice_scope", "passed": False, "score": 5,
                "detail": "No scope indicators found in best practices section"}


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
    score = max(0, 20 - total_violations * 4)
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

    score = 20 if passed else (10 if phase_a or phase_b else 0)
    return {"rule": "two_phase_analysis", "passed": passed, "score": score, "detail": detail}


def main():
    parser = argparse.ArgumentParser(description="Quality check a retrospective report against red-line rules.")
    parser.add_argument("--file", default=None, help="Path to report file (reads stdin if omitted)")
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
