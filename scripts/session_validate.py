#!/usr/bin/env python3
"""会话结束时的轻量级 Gene 增量验证。

作为 SessionEnd/Stop hook 运行，纯文本匹配，不调用 LLM。
正常情况只输出 JSON 到 stdout，异常时静默退出（exit 0）。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 将 scripts/ 目录加入 sys.path，以便 import lib
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from lib import (
    INJECTABLE_STATUSES,
    append_evolution,
    load_all_assets,
    utc_now_iso,
    utc_today_iso,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 日常验证的 confidence 变化幅度（比复盘时小）
COMPLIANT_DELTA = 0.02
NON_COMPLIANT_DELTA = -0.05

# 触发匹配的关键词命中率阈值
TRIGGER_MATCH_THRESHOLD = 0.50

# 会话内容最小长度（字符数），太短则跳过
MIN_SESSION_LENGTH = 500

# confidence 告警阈值
CONFIDENCE_WARN_THRESHOLD = 0.50

# ---------------------------------------------------------------------------
# 中文分词辅助：提取关键词
# ---------------------------------------------------------------------------

# 中文停用词（常见虚词）
_CN_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "那", "被", "从", "对", "以", "但", "可以", "什么", "如果",
    "能", "还", "吗", "把", "让", "给", "用", "它", "做", "这个",
    "那个", "已经", "或者", "而且", "因为", "所以", "然后", "虽然",
    "但是", "不是", "没有", "可能", "应该", "需要", "进行", "使用",
    "通过", "其他", "这些", "那些", "这样", "那样",
}

# 英文停用词
_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "and",
    "but", "or", "nor", "not", "so", "if", "then", "else", "when",
    "up", "out", "about", "it", "its", "this", "that", "these",
    "those", "each", "every", "all", "any", "both", "few", "more",
    "most", "other", "some", "such", "no", "only", "same", "than",
    "too", "very",
}


def extract_keywords(text: str) -> set[str]:
    """从文本中提取关键词（中英文混合），去除停用词和短词。"""
    if not text:
        return set()
    # 提取中文词（2字以上的连续中文）
    cn_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", text))
    # 提取英文词（2字符以上的连续英文字母/数字/下划线）
    en_words = set(w.lower() for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}", text))
    # 过滤停用词
    cn_words -= _CN_STOPWORDS
    en_words -= _EN_STOPWORDS
    return cn_words | en_words


# ---------------------------------------------------------------------------
# 会话 transcript 读取
# ---------------------------------------------------------------------------


def find_latest_transcript(project_dir: str) -> str | None:
    """查找最近的会话 transcript 文件。

    按 Claude 的 session 存储惯例，扫描 ~/.claude/projects/<encoded>/
    """
    abs_project = str(Path(project_dir).resolve())
    encoded_name = abs_project.replace("/", "-")
    claude_sessions = Path.home() / ".claude" / "projects" / encoded_name
    if not claude_sessions.is_dir():
        return None

    jsonl_files = sorted(claude_sessions.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    if not jsonl_files:
        return None
    return str(jsonl_files[-1])


def read_session_content(session_file: str) -> str:
    """从 JSONL transcript 文件中提取文本内容。"""
    lines = []
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                # 提取消息文本（兼容不同格式）
                msg = entry.get("message", {})
                if isinstance(msg, str):
                    lines.append(msg)
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        lines.append(content)
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, str):
                                lines.append(part)
                            elif isinstance(part, dict) and part.get("type") == "text":
                                lines.append(part.get("text", ""))
    except OSError:
        return ""
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 触发匹配 + 合规检测
# ---------------------------------------------------------------------------


def match_trigger(asset: dict, session_text: str, session_keywords: set[str]) -> tuple[bool, float, list[str]]:
    """检测资产的 trigger 是否在会话中被触发。

    返回: (是否触发, 命中率, 命中的关键词列表)
    """
    trigger = asset.get("trigger", "")
    if not trigger:
        return False, 0.0, []

    trigger_keywords = extract_keywords(trigger)
    if not trigger_keywords:
        return False, 0.0, []

    matched = trigger_keywords & session_keywords
    score = len(matched) / len(trigger_keywords) if trigger_keywords else 0.0

    return score >= TRIGGER_MATCH_THRESHOLD, score, sorted(matched)


def check_compliance(asset: dict, session_text: str, session_keywords: set[str]) -> str:
    """检测资产的 method/steps 是否在会话中被遵守。

    返回: "compliant" | "non_compliant" | "ambiguous"
    """
    asset_type = asset.get("asset_type", "gene")

    # 根据资产类型获取行为描述
    if asset_type == "gene":
        steps = asset.get("method", [])
    elif asset_type == "sop":
        steps = asset.get("steps", [])
    elif asset_type == "pref":
        # 偏好类：检查 rationale 关键词
        rationale = asset.get("rationale", "")
        preferred = asset.get("preferred", "")
        pref_keywords = extract_keywords(rationale) | extract_keywords(preferred)
        if not pref_keywords:
            return "ambiguous"
        overlap = pref_keywords & session_keywords
        if len(overlap) >= max(1, len(pref_keywords) * 0.3):
            return "compliant"
        return "ambiguous"
    else:
        return "ambiguous"

    # 对 gene/sop：检查 method/steps 中的行为关键词
    if not steps:
        return "ambiguous"

    if isinstance(steps, str):
        steps = [steps]

    matched_steps = 0
    for step in steps:
        step_text = step if isinstance(step, str) else step.get("action", step.get("description", str(step)))
        step_keywords = extract_keywords(step_text)
        if step_keywords and (step_keywords & session_keywords):
            matched_steps += 1

    if not steps:
        return "ambiguous"

    rate = matched_steps / len(steps)
    if rate >= 0.5:
        return "compliant"
    elif rate <= 0.2:
        return "non_compliant"
    else:
        return "ambiguous"


# ---------------------------------------------------------------------------
# Confidence 更新
# ---------------------------------------------------------------------------


def compute_delta(compliance: str) -> float:
    """根据合规性计算 confidence 变化量。"""
    if compliance == "compliant":
        return COMPLIANT_DELTA
    elif compliance == "non_compliant":
        return NON_COMPLIANT_DELTA
    else:
        return 0.0


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def update_asset_confidence(asset_id: str, new_confidence: float, memory_dir: str):
    """调用 manage_assets.py 更新资产的 confidence。"""
    manage_script = _SCRIPT_DIR / "manage_assets.py"
    try:
        subprocess.run(
            [
                sys.executable,
                str(manage_script),
                "--memory-dir", memory_dir,
                "update",
                "--id", asset_id,
                "--confidence", str(round(new_confidence, 4)),
            ],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass  # 静默失败，不影响用户


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def validate_session(project_dir: str, session_file: str | None, mode: str) -> dict | None:
    """执行会话验证的核心逻辑。

    返回验证结果 dict，或 None（跳过验证时）。
    """
    memory_dir = os.path.join(project_dir, "memory")

    # 1. 读取 memory/ 中所有 active + provisional 资产
    if not os.path.isdir(memory_dir):
        return None

    assets = load_all_assets(memory_dir, statuses=INJECTABLE_STATUSES)
    if not assets:
        return None

    # 2. 读取本次会话内容
    if session_file and os.path.isfile(session_file):
        transcript_path = session_file
    else:
        transcript_path = find_latest_transcript(project_dir)

    if not transcript_path:
        return None

    session_text = read_session_content(transcript_path)
    if len(session_text) < MIN_SESSION_LENGTH:
        return None

    # 预提取会话关键词（一次提取，多次匹配）
    session_keywords = extract_keywords(session_text)

    # 3-4. 对每个资产做触发匹配 + 合规检测
    triggered_assets = []
    for asset in assets:
        triggered, score, matched_kw = match_trigger(asset, session_text, session_keywords)
        if not triggered:
            continue

        compliance = check_compliance(asset, session_text, session_keywords)
        delta = compute_delta(compliance)

        triggered_assets.append({
            "asset_id": asset.get("id", "unknown"),
            "asset_type": asset.get("asset_type", "gene"),
            "trigger_match_score": round(score, 2),
            "compliance": compliance,
            "matched_keywords": matched_kw,
            "confidence_delta": delta,
            "_current_confidence": float(asset.get("confidence", 0.5)),
        })

    # 5. 构建结果
    today = utc_today_iso()
    compliant_count = sum(1 for a in triggered_assets if a["compliance"] == "compliant")
    non_compliant_count = sum(1 for a in triggered_assets if a["compliance"] == "non_compliant")

    result = {
        "session_date": today,
        "triggered_assets": [],
        "summary": (
            f"本次会话触发了 {len(triggered_assets)} 条规则，"
            f"{compliant_count} 条遵守，"
            f"{non_compliant_count} 条未遵守"
        ),
    }

    # 6. 如果 mode == "update"，更新 confidence 并写 evolution
    for item in triggered_assets:
        asset_id = item["asset_id"]
        delta = item["confidence_delta"]
        current_conf = item["_current_confidence"]
        new_conf = clamp(round(current_conf + delta, 4))

        if mode == "update" and delta != 0.0:
            # 更新 confidence
            update_asset_confidence(asset_id, new_conf, memory_dir)

            # 写入 evolution.jsonl
            append_evolution(memory_dir, {
                "ts": utc_now_iso(),
                "event": "session_validate",
                "asset_id": asset_id,
                "details": {
                    "compliance": item["compliance"],
                    "session_date": today,
                    "trigger_score": item["trigger_match_score"],
                    "confidence_from": current_conf,
                    "confidence_to": new_conf,
                },
            })

            # confidence 降到告警阈值以下 → 输出告警到 stderr
            if new_conf < CONFIDENCE_WARN_THRESHOLD:
                print(
                    f"WARNING: 资产 '{asset_id}' confidence 降至 {new_conf:.2f}，"
                    f"低于阈值 {CONFIDENCE_WARN_THRESHOLD}，可能需要 deprecated",
                    file=sys.stderr,
                )

        # 移除内部字段，构建输出
        output_item = {
            "asset_id": item["asset_id"],
            "asset_type": item["asset_type"],
            "trigger_match_score": item["trigger_match_score"],
            "compliance": item["compliance"],
            "matched_keywords": item["matched_keywords"],
            "confidence_delta": item["confidence_delta"],
        }
        result["triggered_assets"].append(output_item)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="会话结束时的轻量级 Gene 增量验证（SessionEnd hook）"
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="项目根目录（含 memory/ 和 .retro/）",
    )
    parser.add_argument(
        "--session-file",
        default=None,
        help="本次会话的 transcript 文件路径（可选）",
    )
    parser.add_argument(
        "--mode",
        choices=["check", "update"],
        default="check",
        help="check=只检查不更新, update=检查并更新 confidence",
    )
    args = parser.parse_args()

    try:
        project_dir = os.path.abspath(args.project_dir)
        result = validate_session(project_dir, args.session_file, args.mode)
        if result is not None:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
    except Exception:
        # 任何异常都静默退出，不影响用户会话
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
