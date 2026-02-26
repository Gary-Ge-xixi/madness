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
    """Extract text from a section whose heading contains any of the keywords.

    Includes sub-headings (deeper level) as part of the section content.
    Only stops at same-level or higher-level headings.
    """
    lines = text.split("\n")
    result_lines = []
    capturing = False
    capture_level = 0
    for line in lines:
        m = re.match(r"^(#{1,4})\s", line)
        if m:
            level = len(m.group(1))
            if capturing:
                if level <= capture_level:
                    break  # same or higher level heading → end of section
                # sub-heading → include as part of this section
                result_lines.append(line)
                continue
            if any(kw in line for kw in keywords):
                capturing = True
                capture_level = level
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
    section = find_section(text, ["\u6700\u4f73\u5b9e\u8df5", "\u6210\u529f\u6a21\u5f0f", "\u505a\u5f97\u597d", "规律总结"])
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


# ===========================================================================
# GRAI 评分函数 — Goal / Result / Analysis / Insight 四维度评分
# ===========================================================================


def _extract_grai_section(text: str, marker: str) -> str:
    """提取 <!-- grai:xxx start --> 到 <!-- grai:xxx end --> 之间的内容。"""
    pattern = rf"<!--\s*grai:{re.escape(marker)}\s+start\s*-->(.*?)<!--\s*grai:{re.escape(marker)}\s+end\s*-->"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 回退：兼容无 start/end 的旧格式
    pattern_legacy = rf"<!--\s*grai:{re.escape(marker)}\s*-->(.*?)(?=<!--\s*grai:|$)"
    m = re.search(pattern_legacy, text, re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------- G 维度（满分 20 分）----------


def check_g1_goal_completeness(text: str, state_path: str = None) -> dict:
    """G1: 检测报告中是否有目标回顾 section，goals 是否逐条列出，是否有 success_criteria（6分）"""
    section = _extract_grai_section(text, "goal-review")
    if not section:
        # 回退：查找中文标题
        section = find_section(text, ["目标回顾", "目标复盘", "目标对照"])

    if not section.strip():
        return {"score": 0, "max": 6, "detail": "未找到 grai:goal-review section 或目标回顾章节"}

    # 检测逐条列出的目标
    goal_items = re.findall(r"^[-*]\s+.+|^\d+[\.\uff0e\)]\s+.+", section, re.MULTILINE)
    item_score = min(3, len(goal_items))  # 最多 3 分

    # 检测 success_criteria 关键词
    criteria_pattern = re.compile(
        r"success_criteria|成功标准|验收标准|达成条件|完成标志|判定标准"
    )
    has_criteria = bool(criteria_pattern.search(section))
    criteria_score = 3 if has_criteria else 0

    score = item_score + criteria_score
    detail = f"列出 {len(goal_items)} 条目标（{item_score}/3）；success_criteria {'存在' if has_criteria else '缺失'}（{criteria_score}/3）"
    return {"score": score, "max": 6, "detail": detail}


def check_g2_goal_review_exists(text: str) -> dict:
    """G2: 检测目标回顾 section 是否存在且非空（6分）"""
    section = _extract_grai_section(text, "goal-review")
    if not section:
        section = find_section(text, ["目标回顾", "目标复盘", "目标对照"])

    if not section.strip():
        return {"score": 0, "max": 6, "detail": "目标回顾 section 不存在"}

    # 内容丰富度检查
    word_count = len(section)
    if word_count < 50:
        return {"score": 2, "max": 6, "detail": f"目标回顾 section 存在但内容过短（{word_count} 字）"}
    elif word_count < 150:
        return {"score": 4, "max": 6, "detail": f"目标回顾 section 存在，内容一般（{word_count} 字）"}
    else:
        return {"score": 6, "max": 6, "detail": f"目标回顾 section 完整（{word_count} 字）"}


def check_g3_goal_change_tracking(text: str) -> dict:
    """G3: 检测是否有目标变更说明（4分）"""
    # 检测变更说明标记
    change_patterns = re.compile(
        r"目标变更|目标调整|目标修订|goal_history|目标演进|变更说明|调整原因"
    )
    has_change_section = bool(change_patterns.search(text))

    # 如果没有变更也没有声明"目标未变更"
    no_change_pattern = re.compile(r"目标未变更|无目标变更|目标保持不变|未调整")
    has_no_change_declaration = bool(no_change_pattern.search(text))

    if has_change_section:
        # 检测变更是否有原因说明
        reason_pattern = re.compile(r"原因|因为|由于|背景")
        section = find_section(text, ["目标变更", "目标调整", "目标修订"])
        has_reason = bool(reason_pattern.search(section)) if section else False
        score = 4 if has_reason else 2
        detail = f"有目标变更说明；变更原因 {'有' if has_reason else '缺失'}"
    elif has_no_change_declaration:
        score = 4
        detail = "已声明目标未变更"
    else:
        score = 0
        detail = "缺少目标变更说明或「目标未变更」声明"

    return {"score": score, "max": 4, "detail": detail}


def check_g4_goal_measurability(text: str) -> dict:
    """G4: 检测目标描述中是否有量化指标（4分）"""
    section = _extract_grai_section(text, "goal-review")
    if not section:
        section = find_section(text, ["目标回顾", "目标复盘", "目标对照", "目标"])

    if not section.strip():
        return {"score": 0, "max": 4, "detail": "未找到目标 section"}

    # 检测量化指标：数字、百分比、时间量词
    quantitative_patterns = [
        r"\d+%",                    # 百分比
        r"\d+\s*[次个条项天小时分钟秒]",  # 数量+量词
        r"[<>≤≥]\s*\d+",           # 比较
        r"\d+\.\d+",               # 小数
        r"\d+\s*[-~到至]\s*\d+",    # 范围
    ]
    total_matches = 0
    for pat in quantitative_patterns:
        total_matches += len(re.findall(pat, section))

    if total_matches >= 3:
        score = 4
    elif total_matches >= 1:
        score = 2
    else:
        score = 0

    detail = f"目标描述中检测到 {total_matches} 处量化指标"
    return {"score": score, "max": 4, "detail": detail}


# ---------- R 维度（满分 25 分）----------


def check_r1_result_goal_mapping(text: str) -> dict:
    """R1: 检测每个目标是否有对应结果映射（8分）"""
    section = _extract_grai_section(text, "result-comparison")
    if not section:
        section = find_section(text, ["结果对照", "结果比对", "目标结果", "完成情况", "达成情况"])

    if not section.strip():
        return {"score": 0, "max": 8, "detail": "未找到 grai:result-comparison section 或结果对照章节"}

    # 检测目标-结果对
    goal_result_pairs = re.findall(
        r"目标.*?结果|预期.*?实际|计划.*?完成|expected.*?actual",
        section, re.IGNORECASE | re.DOTALL
    )
    # 也检测表格行（|目标|结果|格式）
    table_rows = re.findall(r"\|[^|]+\|[^|]+\|", section)
    # 也检测列表项中的对照
    list_comparisons = re.findall(
        r"^[-*]\s+.*(?:→|->|=>|：|:).*(?:完成|达成|未达|部分)",
        section, re.MULTILINE
    )

    pair_count = len(goal_result_pairs) + len(table_rows) + len(list_comparisons)
    if pair_count >= 4:
        score = 8
    elif pair_count >= 2:
        score = 5
    elif pair_count >= 1:
        score = 3
    else:
        score = 0

    detail = f"检测到 {pair_count} 组目标-结果对照（关键词对 {len(goal_result_pairs)}，表格行 {len(table_rows)}，列表对照 {len(list_comparisons)}）"
    return {"score": score, "max": 8, "detail": detail}


def check_r2_gap_quantification(text: str) -> dict:
    """R2: 检测差距描述是否有量化或可观测的表述（6分）"""
    section = _extract_grai_section(text, "result-comparison")
    if not section:
        section = find_section(text, ["结果对照", "结果比对", "差距", "gap", "完成情况"])

    if not section.strip():
        return {"score": 0, "max": 6, "detail": "未找到结果对照 section"}

    # 量化差距模式
    gap_patterns = [
        r"差距\s*[:：]?\s*\d+",         # 差距: 数字
        r"完成率\s*[:：]?\s*\d+%",       # 完成率百分比
        r"缺口\s*[:：]?\s*\d+",         # 缺口数字
        r"偏差\s*[:：]?\s*\d+",         # 偏差数字
        r"\d+%.*(?:未达|差距|缺口)",     # 百分比+未达
        r"(?:超出|低于|高于)\s*\d+",     # 超出/低于+数字
        r"(?:延迟|提前)\s*\d+",         # 时间偏差
    ]
    total_matches = 0
    for pat in gap_patterns:
        total_matches += len(re.findall(pat, section))

    # 也检测可观测表述（具体事件）
    observable_patterns = re.compile(
        r"例如|比如|具体表现|实际.*发生|导致.*?(?:了|过)"
    )
    observable_count = len(observable_patterns.findall(section))

    combined = total_matches + observable_count
    if combined >= 3:
        score = 6
    elif combined >= 1:
        score = 3
    else:
        score = 0

    detail = f"量化差距 {total_matches} 处，可观测表述 {observable_count} 处"
    return {"score": score, "max": 6, "detail": detail}


def check_r3_highlight_evidence(text: str) -> dict:
    """R3: 检测亮点是否带有 session 证据引用（5分）"""
    # 查找亮点相关 section
    section = find_section(text, ["亮点", "做得好", "成功", "highlight"])
    if not section.strip():
        return {"score": 0, "max": 5, "detail": "未找到亮点 section"}

    # 检测 session 引用
    session_refs = re.findall(
        r"session|会话|第.*?轮|S\d+|\d{1,2}-\d{1,2}|会话\s*\d+",
        section, re.IGNORECASE
    )
    # 检测引号引用
    quote_patterns = re.findall(r"\u300c[^\u300d]+\u300d", section)
    quote_patterns += re.findall(r"\u201c[^\u201d]+\u201d", section)
    quote_patterns += re.findall(r'"[^"]{2,}"', section)

    evidence_count = len(session_refs) + len(quote_patterns)
    if evidence_count >= 3:
        score = 5
    elif evidence_count >= 1:
        score = 3
    else:
        score = 0

    detail = f"亮点中 session 引用 {len(session_refs)} 处，引号引用 {len(quote_patterns)} 处"
    return {"score": score, "max": 5, "detail": detail}


def check_r4_weakness_evidence(text: str) -> dict:
    """R4: 检测不足是否带有用户原话引用（6分）"""
    section = find_section(text, ["不足", "问题", "摩擦", "卡住", "weakness"])
    if not section.strip():
        return {"score": 0, "max": 6, "detail": "未找到不足/问题 section"}

    # 检测用户原话引用（各种引号格式）
    quote_patterns = re.findall(r"\u300c[^\u300d]+\u300d", section)
    quote_patterns += re.findall(r"\u201c[^\u201d]+\u201d", section)
    quote_patterns += re.findall(r'"[^"]{2,}"', section)
    # 检测 session 证据
    session_refs = re.findall(
        r"session|会话|第.*?轮|S\d+|\d{1,2}-\d{1,2}",
        section, re.IGNORECASE
    )

    quote_count = len(quote_patterns)
    if quote_count >= 3:
        score = 6
    elif quote_count >= 1:
        score = 3
    else:
        score = 0

    # session 引用加分
    if session_refs and score < 6:
        score = min(6, score + 1)

    detail = f"不足 section 中用户原话引用 {quote_count} 处，session 引用 {len(session_refs)} 处"
    return {"score": score, "max": 6, "detail": detail}


# ---------- A 维度（满分 35 分）----------


def check_a1_two_phase_structure(text: str) -> dict:
    """A1: 复用/增强 Rule 5，检测两阶段分析结构（7分）"""
    legacy = check_two_phase_analysis(text)
    # legacy score 满分 13，映射到 7 分
    if legacy["passed"]:
        score = 7
    elif legacy["score"] >= 6:
        score = 4
    else:
        score = 0

    return {"score": score, "max": 7, "detail": f"两阶段结构：{legacy['detail']}"}


def check_a2_evidence_quotes(text: str) -> dict:
    """A2: 复用/增强 Rule 1，检测分析中的证据引用（8分）"""
    legacy = check_evidence_quotes(text)
    # legacy score 满分 15，映射到 8 分
    ratio = legacy["score"] / 15 if legacy["score"] > 0 else 0
    score = min(8, round(8 * ratio))

    return {"score": score, "max": 8, "detail": f"证据引用：{legacy['detail']}"}


def check_a3_subjective_objective_split(text: str) -> dict:
    """A3: 检测分析中是否有主观/客观两个子板块（6分）"""
    section = _extract_grai_section(text, "analysis")
    if not section:
        section = find_section(text, ["分析", "归因", "原因分析"])

    if not section.strip():
        return {"score": 0, "max": 6, "detail": "未找到 grai:analysis section 或分析章节"}

    # 检测主观/客观分类
    subjective_markers = re.compile(r"主观|人为因素|态度|习惯|意识|认知")
    objective_markers = re.compile(r"客观|外部因素|工具|环境|流程|制度|技术限制")

    has_subjective = bool(subjective_markers.search(section))
    has_objective = bool(objective_markers.search(section))

    if has_subjective and has_objective:
        score = 6
        detail = "分析中同时包含主观和客观两个维度"
    elif has_subjective or has_objective:
        score = 3
        which = "主观" if has_subjective else "客观"
        detail = f"分析中仅包含{which}维度，缺少另一维度"
    else:
        score = 0
        detail = "分析中未发现主观/客观分类标记"

    return {"score": score, "max": 6, "detail": detail}


def check_a4_root_cause_depth(text: str) -> dict:
    """A4: 检测是否有嵌套因果链（8分）"""
    section = _extract_grai_section(text, "analysis")
    if not section:
        section = find_section(text, ["分析", "归因", "原因分析", "根因"])

    if not section.strip():
        return {"score": 0, "max": 8, "detail": "未找到分析 section"}

    # 检测嵌套因果链模式
    causal_chain_patterns = [
        r"因为.*?而.*?是因为",           # 因为X，而X是因为Y
        r"根本原因.*?是.*?导致",         # 根本原因分析
        r"表面.*?深层",                  # 表面-深层
        r"直接原因.*?根本原因",          # 直接-根本
        r"→.*?→",                       # 箭头链
        r"->.*?->",                     # 箭头链（ASCII）
        r"why.*?why|为什么.*?为什么",    # 连续 why
        r"第一层.*?第二层|层.*?层",      # 分层分析
    ]
    chain_count = 0
    for pat in causal_chain_patterns:
        chain_count += len(re.findall(pat, section, re.DOTALL | re.IGNORECASE))

    # 也检测因果关键词密度
    causal_keywords = re.findall(
        r"因为|所以|导致|造成|引发|源于|根因|归因",
        section
    )
    keyword_density = len(causal_keywords)

    if chain_count >= 2:
        score = 8
    elif chain_count >= 1:
        score = 5
    elif keyword_density >= 4:
        score = 3
    else:
        score = 0

    detail = f"嵌套因果链 {chain_count} 条，因果关键词 {keyword_density} 个"
    return {"score": score, "max": 8, "detail": detail}


def check_a5_attribution_balance(text: str) -> dict:
    """A5: 检测成功原因和失败原因是否都有分析（6分）"""
    # 检测成功归因
    success_section = find_section(text, ["亮点", "做得好", "成功原因", "成功因素"])
    success_analysis = find_section(text, ["成功归因", "正面分析"])
    success_markers = re.findall(
        r"成功.*?(?:因为|原因|归因)|做得好.*?(?:因为|原因)",
        text, re.DOTALL
    )

    # 检测失败归因
    failure_section = find_section(text, ["不足", "问题", "失败原因", "改进"])
    failure_analysis = find_section(text, ["失败归因", "负面分析"])
    failure_markers = re.findall(
        r"(?:不足|问题|失败).*?(?:因为|原因|归因)",
        text, re.DOTALL
    )

    has_success = bool(success_section.strip() or success_analysis.strip() or success_markers)
    has_failure = bool(failure_section.strip() or failure_analysis.strip() or failure_markers)

    if has_success and has_failure:
        score = 6
        detail = "成功原因和失败原因均有分析，归因平衡"
    elif has_success or has_failure:
        score = 3
        which = "成功" if has_success else "失败"
        detail = f"仅分析了{which}原因，归因不平衡"
    else:
        score = 0
        detail = "缺少成功和失败的归因分析"

    return {"score": score, "max": 6, "detail": detail}


# ---------- I 维度（满分 20 分）----------


def check_i1_insight_section_exists(text: str) -> dict:
    """I1: 检测洞察 section 是否存在（5分）"""
    section = _extract_grai_section(text, "insight")
    if not section:
        section = find_section(text, ["洞察", "启发", "认知升级", "规律总结", "最佳实践"])

    if not section.strip():
        return {"score": 0, "max": 5, "detail": "未找到 grai:insight section 或洞察章节"}

    word_count = len(section)
    if word_count < 50:
        return {"score": 2, "max": 5, "detail": f"洞察 section 存在但内容过短（{word_count} 字）"}
    elif word_count < 200:
        return {"score": 3, "max": 5, "detail": f"洞察 section 存在，内容一般（{word_count} 字）"}
    else:
        return {"score": 5, "max": 5, "detail": f"洞察 section 完整（{word_count} 字）"}


def check_i2_generalization(text: str) -> dict:
    """I2: 复用/增强 Rule 3，检测是否从多场景归纳（6分）"""
    legacy = check_best_practice_scope(text)
    # legacy score 满分 15，映射到 6 分
    ratio = legacy["score"] / 15 if legacy["score"] > 0 else 0
    score = min(6, round(6 * ratio))

    return {"score": score, "max": 6, "detail": f"多场景归纳：{legacy['detail']}"}


def check_i3_actionability(text: str) -> dict:
    """I3: 复用/增强 Rule 2，检测 IF/THEN 结构（5分）"""
    legacy = check_actionable_steps(text)
    # legacy score 满分 15，映射到 5 分
    ratio = legacy["score"] / 15 if legacy["score"] > 0 else 0
    base_score = min(4, round(4 * ratio))

    # 额外检测 IF/THEN 或 条件-动作 结构
    ifthen_patterns = re.findall(
        r"IF\s+.+?\s+THEN|如果.*?(?:则|就|那么)|当.*?(?:则|就|应该)",
        text, re.IGNORECASE
    )
    bonus = 1 if len(ifthen_patterns) >= 1 else 0

    score = min(5, base_score + bonus)
    detail = f"可执行性：{legacy['detail']}；IF/THEN 结构 {len(ifthen_patterns)} 处"
    return {"score": score, "max": 5, "detail": detail}


def check_i4_gene_candidate_output(text: str) -> dict:
    """I4: 检测是否有 Gene 候选表或显式说明无需新 Gene（4分）"""
    # 检测 Gene 候选
    gene_candidate_pattern = re.compile(
        r"Gene\s*候选|gene.*?candidate|新增\s*Gene|Gene\s*提取|gene_candidates",
        re.IGNORECASE
    )
    has_gene_candidate = bool(gene_candidate_pattern.search(text))

    # 检测"无需新 Gene"的声明
    no_gene_pattern = re.compile(
        r"无需.*?Gene|不需要.*?Gene|无新.*?Gene|没有.*?新.*?Gene|暂无.*?Gene",
        re.IGNORECASE
    )
    has_no_gene = bool(no_gene_pattern.search(text))

    if has_gene_candidate:
        # 检查是否有具体列表
        gene_section = find_section(text, ["Gene 候选", "Gene候选", "gene_candidates", "Gene 提取"])
        items = re.findall(r"^[-*]\s+.+|^\d+[\.\uff0e\)]\s+.+", gene_section, re.MULTILINE) if gene_section else []
        if len(items) >= 1:
            score = 4
            detail = f"Gene 候选表存在，包含 {len(items)} 条候选"
        else:
            score = 2
            detail = "提及 Gene 候选但未列出具体条目"
    elif has_no_gene:
        score = 4
        detail = "已显式说明无需新 Gene"
    else:
        score = 0
        detail = "缺少 Gene 候选表或「无需新 Gene」声明"

    return {"score": score, "max": 4, "detail": detail}


# ===========================================================================
# GRAI 综合评分计算
# ===========================================================================


def calculate_grai_score(text: str, state_path: str = None) -> dict:
    """计算 GRAI 四维度综合分数，返回结构化结果。"""
    grai_checks = {
        "G1": check_g1_goal_completeness(text, state_path),
        "G2": check_g2_goal_review_exists(text),
        "G3": check_g3_goal_change_tracking(text),
        "G4": check_g4_goal_measurability(text),
        "R1": check_r1_result_goal_mapping(text),
        "R2": check_r2_gap_quantification(text),
        "R3": check_r3_highlight_evidence(text),
        "R4": check_r4_weakness_evidence(text),
        "A1": check_a1_two_phase_structure(text),
        "A2": check_a2_evidence_quotes(text),
        "A3": check_a3_subjective_objective_split(text),
        "A4": check_a4_root_cause_depth(text),
        "A5": check_a5_attribution_balance(text),
        "I1": check_i1_insight_section_exists(text),
        "I2": check_i2_generalization(text),
        "I3": check_i3_actionability(text),
        "I4": check_i4_gene_candidate_output(text),
    }

    # 按维度汇总
    goal_score = sum(grai_checks[k]["score"] for k in ["G1", "G2", "G3", "G4"])
    result_score = sum(grai_checks[k]["score"] for k in ["R1", "R2", "R3", "R4"])
    analysis_score = sum(grai_checks[k]["score"] for k in ["A1", "A2", "A3", "A4", "A5"])
    insight_score = sum(grai_checks[k]["score"] for k in ["I1", "I2", "I3", "I4"])

    total = goal_score + result_score + analysis_score + insight_score

    return {
        "total": total,
        "goal": goal_score,
        "result": result_score,
        "analysis": analysis_score,
        "insight": insight_score,
        "details": grai_checks,
    }


# ===========================================================================
# CLAUDE.md 质量检查
# ===========================================================================


def check_claudemd_quality(claudemd_path: str) -> dict:
    """检查 CLAUDE.md 注入后的质量，6 维度评分（满分 100）。

    返回:
        {"total": int, "details": dict, "warnings": list[str]}
    """
    try:
        with open(claudemd_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, OSError) as e:
        return {
            "total": 0,
            "details": {},
            "warnings": [f"无法读取 CLAUDE.md: {e}"],
        }

    import os
    project_dir = os.path.dirname(claudemd_path)
    warnings = []
    details = {}

    # 1. commands_workflows（20分）— 是否有 build/test/dev 命令
    cmd_patterns = re.findall(
        r"```[^\n]*\n[^`]*(?:npm|yarn|pnpm|python|pip|cargo|go|make|docker|gradle|mvn)\s+\S+[^`]*```",
        content, re.DOTALL
    )
    inline_cmds = re.findall(r"`[^`]*(?:npm|yarn|python|cargo|go|make)\s+\S+[^`]*`", content)
    cmd_count = len(cmd_patterns) + len(inline_cmds)
    if cmd_count >= 3:
        cmd_score = 20
    elif cmd_count >= 1:
        cmd_score = 12
    else:
        cmd_score = 0
        warnings.append("CLAUDE.md 缺少 build/test/dev 命令")
    details["commands_workflows"] = {"score": cmd_score, "max": 20,
                                     "detail": f"检测到 {cmd_count} 条可执行命令"}

    # 2. architecture_clarity（20分）— 是否有目录结构说明
    has_tree = bool(re.search(r"[├└│─]", content))  # 目录树字符
    has_dir_desc = bool(re.search(r"(?:目录|结构|架构|src/|lib/|app/)", content))
    if has_tree:
        arch_score = 20
    elif has_dir_desc:
        arch_score = 12
    else:
        arch_score = 0
        warnings.append("CLAUDE.md 缺少项目目录结构说明")
    details["architecture_clarity"] = {"score": arch_score, "max": 20,
                                       "detail": f"目录树: {'有' if has_tree else '无'}，目录描述: {'有' if has_dir_desc else '无'}"}

    # 3. non_obvious_patterns（15分）— 是否有 gotcha/坑的记录
    gotcha_patterns = re.compile(
        r"注意|坑|gotcha|caveat|特殊|陷阱|小心|不要|避免|NEVER|IMPORTANT|WARNING",
        re.IGNORECASE
    )
    gotcha_matches = gotcha_patterns.findall(content)
    if len(gotcha_matches) >= 3:
        gotcha_score = 15
    elif len(gotcha_matches) >= 1:
        gotcha_score = 8
    else:
        gotcha_score = 0
        warnings.append("CLAUDE.md 缺少注意事项/坑的记录")
    details["non_obvious_patterns"] = {"score": gotcha_score, "max": 15,
                                       "detail": f"检测到 {len(gotcha_matches)} 处注意事项标记"}

    # 4. conciseness（15分）— 是否精简（行数/信息密度）
    lines = content.split("\n")
    line_count = len(lines)
    non_empty_lines = len([l for l in lines if l.strip()])
    density = non_empty_lines / line_count if line_count > 0 else 0
    if line_count <= 200 and density >= 0.5:
        concise_score = 15
    elif line_count <= 500:
        concise_score = 10
    else:
        concise_score = 5
        warnings.append(f"CLAUDE.md 行数过多（{line_count} 行），建议精简")
    details["conciseness"] = {"score": concise_score, "max": 15,
                              "detail": f"{line_count} 行，信息密度 {density:.0%}"}

    # 5. currency（15分）— 引用的文件路径是否存在
    file_refs = re.findall(r"`([^`]*(?:/[^`]+\.\w+))`", content)
    existing = 0
    missing = []
    for ref in file_refs:
        full_path = os.path.join(project_dir, ref) if not os.path.isabs(ref) else ref
        if os.path.exists(full_path):
            existing += 1
        else:
            missing.append(ref)
    total_refs = len(file_refs)
    if total_refs == 0:
        currency_score = 10  # 没有路径引用，给中等分
    elif missing:
        ratio = existing / total_refs
        currency_score = int(15 * ratio)
        warnings.append(f"CLAUDE.md 中 {len(missing)} 个文件路径不存在: {', '.join(missing[:3])}")
    else:
        currency_score = 15
    details["currency"] = {"score": currency_score, "max": 15,
                           "detail": f"引用路径 {existing}/{total_refs} 存在"}

    # 6. actionability（15分）— 命令是否可复制执行
    code_blocks = re.findall(r"```(?:sh|bash|shell|zsh)?\n([^`]+)```", content, re.DOTALL)
    executable_cmds = 0
    for block in code_blocks:
        cmds = [l.strip() for l in block.split("\n") if l.strip() and not l.strip().startswith("#")]
        executable_cmds += len(cmds)
    if executable_cmds >= 3:
        action_score = 15
    elif executable_cmds >= 1:
        action_score = 8
    else:
        action_score = 3
    details["actionability"] = {"score": action_score, "max": 15,
                                "detail": f"检测到 {executable_cmds} 条可复制执行的命令"}

    total = sum(d["score"] for d in details.values())
    if total < 70:
        warnings.insert(0, f"⚠ CLAUDE.md 质量评分 {total}/100，低于 70 分阈值，建议优化")

    return {"total": total, "details": details, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(
        description="Quality check a retrospective report against red-line rules.")
    parser.add_argument("--file", default=None,
                        help="Path to report file (reads stdin if omitted)")
    parser.add_argument("--state-path", default=None,
                        help="Path to state.json for goal alignment check")
    parser.add_argument("--claudemd", default=None,
                        help="Path to CLAUDE.md for quality check (独立模式)")
    args = parser.parse_args()

    # 独立 CLAUDE.md 检查模式
    if args.claudemd:
        claudemd_result = check_claudemd_quality(args.claudemd)
        json.dump(claudemd_result, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    text = read_report(args.file)
    if not text.strip():
        print("Error: Report is empty.", file=sys.stderr)
        sys.exit(1)

    # --- Legacy 7 条规则评分（保持不变）---
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

    # --- GRAI 四维度评分（新增）---
    grai = calculate_grai_score(text, args.state_path)

    result = {
        "score": total_score,
        "grai_score": grai,
        "checks": output_checks,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
