#!/usr/bin/env python3
"""扫描 deprecated 资产并清理 CLAUDE.md 中的对应规则。

当资产 confidence 降到 deprecated（<0.50）后，其规则仍可能残留在
CLAUDE.md 的 memory-inject 区间中。本脚本检测并可选地自动清理。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 将 scripts/ 目录加入 sys.path，以便 import lib
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from lib import (
    append_evolution,
    load_all_assets,
    utc_now_iso,
    utc_today_iso,
)

# ---------------------------------------------------------------------------
# 常量（与 inject_claudemd.py 保持一致）
# ---------------------------------------------------------------------------

MARKER_START = "<!-- madness:memory-inject start -->"
MARKER_END = "<!-- madness:memory-inject end -->"

# 匹配规则行的模式：# R1 [gene:asset-id, c:0.85, v:2]
RULE_HEADER_PATTERN = re.compile(r"^#\s*R\d+\s*\[(\w+):(.+?),\s*c:([\d.]+),\s*v:(\d+)\]")


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------


def find_deprecated_ids(memory_dir: str) -> set[str]:
    """读取 memory/ 中所有 deprecated 资产的 id。"""
    assets = load_all_assets(memory_dir, statuses={"deprecated"})
    return {a.get("id", "") for a in assets if a.get("id")}


def parse_inject_section(claudemd_content: str) -> tuple[int, int, str]:
    """解析 CLAUDE.md 中的 memory-inject 区间。

    返回: (start_index, end_index, section_content)
    如果未找到标记，返回 (-1, -1, "")
    """
    start_idx = claudemd_content.find(MARKER_START)
    end_idx = claudemd_content.find(MARKER_END)

    if start_idx == -1 or end_idx == -1:
        return -1, -1, ""

    end_idx += len(MARKER_END)
    section = claudemd_content[start_idx:end_idx]
    return start_idx, end_idx, section


def find_stale_rules(section_content: str, deprecated_ids: set[str]) -> list[dict]:
    """在注入区间中查找仍然存在的 deprecated 资产规则。

    返回需要清理的条目列表，每项包含 asset_id、asset_type、confidence、version。
    """
    stale = []
    for line in section_content.splitlines():
        m = RULE_HEADER_PATTERN.match(line.strip())
        if m:
            asset_id = m.group(2).strip()
            if asset_id in deprecated_ids:
                stale.append({
                    "asset_id": asset_id,
                    "asset_type": m.group(1),
                    "confidence": float(m.group(3)),
                    "version": int(m.group(4)),
                })
    return stale


def remove_rules_from_section(section_content: str, ids_to_remove: set[str]) -> str:
    """从注入区间内容中移除指定 id 的规则块。

    规则块的结构：
    # RN [type:id, c:X.XX, v:N]
    IF trigger:
        method lines...
    # skip_when: ...  (可选)
    # outcome...      (可选)

    每个规则块以 "# R" 开头，到下一个 "# R" 或 MARKER_END 之前。
    """
    lines = section_content.splitlines()
    output_lines = []
    skip_block = False
    rule_index = 0  # 用于重新编号

    for line in lines:
        stripped = line.strip()

        # 检查是否是规则头
        m = RULE_HEADER_PATTERN.match(stripped)
        if m:
            asset_id = m.group(2).strip()
            if asset_id in ids_to_remove:
                skip_block = True
                continue
            else:
                skip_block = False
                # 重新编号
                rule_index += 1
                asset_type = m.group(1)
                confidence = m.group(3)
                version = m.group(4)
                line = f"# R{rule_index} [{asset_type}:{asset_id}, c:{confidence}, v:{version}]"
                output_lines.append(line)
                continue

        # 如果在跳过的块中
        if skip_block:
            # 遇到标记行则停止跳过
            if stripped == MARKER_START or stripped == MARKER_END:
                skip_block = False
                output_lines.append(line)
            # 遇到下一个规则头也停止跳过（但会在上面的 if m 中处理）
            continue

        output_lines.append(line)

    # 清理连续空行（规则移除后可能留下多余空行）
    cleaned = []
    prev_empty = False
    for line in output_lines:
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue
        cleaned.append(line)
        prev_empty = is_empty

    return "\n".join(cleaned)


def apply_cleanup(
    claudemd_path: Path,
    claudemd_content: str,
    start_idx: int,
    end_idx: int,
    section_content: str,
    stale_rules: list[dict],
    memory_dir: str,
) -> dict:
    """执行清理：修改 CLAUDE.md 并记录 evolution。"""
    ids_to_remove = {r["asset_id"] for r in stale_rules}
    new_section = remove_rules_from_section(section_content, ids_to_remove)

    # 替换 CLAUDE.md 中的区间
    new_content = claudemd_content[:start_idx] + new_section + claudemd_content[end_idx:]

    # 原子写入
    tmp_path = str(claudemd_path) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, str(claudemd_path))
    except OSError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"error": f"写入 CLAUDE.md 失败: {e}"}

    # 记录 evolution
    today = utc_today_iso()
    for rule in stale_rules:
        append_evolution(memory_dir, {
            "ts": utc_now_iso(),
            "event": "deprecate",
            "asset_id": rule["asset_id"],
            "details": {
                "action": "claudemd_cleanup",
                "removed_from_claudemd": True,
                "date": today,
                "previous_confidence": rule["confidence"],
            },
        })

    return {
        "applied": True,
        "removed_count": len(stale_rules),
        "removed_ids": sorted(ids_to_remove),
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="扫描 deprecated 资产并清理 CLAUDE.md 中的对应规则"
    )
    parser.add_argument(
        "--claudemd",
        default="./CLAUDE.md",
        help="CLAUDE.md 文件路径（默认: ./CLAUDE.md）",
    )
    parser.add_argument(
        "--memory-dir",
        default="./memory",
        help="memory 目录路径（默认: ./memory）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="自动从 CLAUDE.md 中移除 deprecated 规则并记录 evolution",
    )
    args = parser.parse_args()

    claudemd_path = Path(args.claudemd)
    memory_dir = args.memory_dir

    # 1. 读取 deprecated 资产
    if not os.path.isdir(memory_dir):
        print(json.dumps({"stale_rules": [], "message": "memory/ 目录不存在"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    deprecated_ids = find_deprecated_ids(memory_dir)
    if not deprecated_ids:
        print(json.dumps({"stale_rules": [], "message": "无 deprecated 资产"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 2. 读取 CLAUDE.md
    if not claudemd_path.exists():
        print(json.dumps({"stale_rules": [], "message": "CLAUDE.md 不存在"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    claudemd_content = claudemd_path.read_text(encoding="utf-8")
    start_idx, end_idx, section_content = parse_inject_section(claudemd_content)

    if start_idx == -1:
        print(json.dumps({"stale_rules": [], "message": "CLAUDE.md 中无 memory-inject 区间"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 3. 查找残留规则
    stale_rules = find_stale_rules(section_content, deprecated_ids)

    if not stale_rules:
        print(json.dumps({"stale_rules": [], "message": "无需清理的规则"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 4. 输出结果
    result = {
        "stale_rules": stale_rules,
        "message": f"发现 {len(stale_rules)} 条 deprecated 规则残留在 CLAUDE.md 中",
    }

    # 5. 如果 --apply，执行清理
    if args.apply:
        apply_result = apply_cleanup(
            claudemd_path, claudemd_content,
            start_idx, end_idx, section_content,
            stale_rules, memory_dir,
        )
        result["cleanup"] = apply_result

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
