# 质量门控协议（展示前必须通过，不可跳过）

报告生成后，**必须运行自动化质量检测**，通过后才能展示给用户：

```
Step 1: 运行自动化检测
  python3 "$MADNESS_DIR"/scripts/check_report.py --file /tmp/madness_report_draft.md --state-path "$STATE_PATH"
  → 输出 JSON：score + grai_score + 各规则得分明细

Step 2: 双分数判定
  通过条件: legacy_score >= 80 AND grai_score.total >= 55

  IF 双条件均满足: 通过 → 进入展示流程
  IF 任一不满足:
    根据扣分明细，回到阶段 B 补充对应内容
    补充后重新生成报告 → 重新运行检测
    最多重试 2 次
    仍不达标 → 标注「质量告警: legacy=XX, grai=XX」后继续展示

Step 2.1: GRAI 维度低分告警
  如果 GRAI 某维度低于 40% 满分，输出该维度的具体补救建议：
  - G (Goal) < 8/20   → 补救: 补充目标逐条列出 + success_criteria + 目标变更说明
  - R (Result) < 10/25 → 补救: 补充目标-结果对照表 + 量化差距 + 证据引用
  - A (Analysis) < 14/35 → 补救: 补充两阶段分析 + 主观/客观分类 + 嵌套因果链
  - I (Insight) < 8/20  → 补救: 补充洞察 section + IF/THEN 规则 + Gene 候选

Step 3: 附质检结果到报告末尾（用户可见），格式：
  [质量自检: legacy=XX/100, grai=XX/100 (G:XX R:XX A:XX I:XX)]
  [证据引用:XX/15 | 可执行步骤:XX/15 | 最佳实践:XX/15 | 空话检测:XX/15 | 两阶段:XX/13 | 摘要-详情:XX/12 | 目标对齐:XX/15]
```

## CLAUDE.md 注入后质量门控（Step 6.4 后置验证）

Gene 注入 CLAUDE.md 后，自动运行质量检查（不阻塞流程，仅告警）：

```
Step 4: CLAUDE.md 质量检查（可选，Gene 注入后自动运行）
  python3 "$MADNESS_DIR"/scripts/check_report.py --claudemd "$PROJECT_DIR/CLAUDE.md"
  → 输出 JSON：total + 6 维度明细 + warnings

  IF total >= 70: 通过（静默）
  IF total < 70: 输出告警和优化建议，但不阻塞流程
    告警格式: ⚠ CLAUDE.md 质量评分 XX/100，建议优化以下维度：[维度列表]
```

## 人工自检清单（通用项）

- [ ] 每个摩擦点有 ≥1 条用户原话引用？
- [ ] 每条改进有可执行步骤（不是空话）？
- [ ] 是否先展示给用户确认，而非直接写入文件？
- [ ] 对照 [bad-cases.md](../bad-cases.md) 中的自检规则？

**自动化检测不达标且重试 2 次仍不达标 → 标注告警后继续，但不可跳过检测步骤本身。**

**如果任何一条人工自检不满足，回到阶段 B 补充，不要直接输出。**
