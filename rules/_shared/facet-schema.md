# Facet 字段定义

## 完整 JSON Schema

```json
{
  "session_id": "",
  "date": "YYYY-MM-DD",
  "duration_min": 0,
  "goal": "本次会话的主要目标（一句话）",
  "goal_category": "implement | refine_methodology | debug_fix | explore_learn | review_calibrate | plan_design | visualize_report",
  "outcome": "fully_achieved | partially_achieved | not_achieved",
  "friction": ["摩擦类型枚举值"],
  "loop_detected": false,
  "loop_detail": "如果检测到循环，描述循环内容",
  "key_decision": "本次会话中做出的关键决策（如有）",
  "learning": "本次会话中获得的关键认知（如有）",
  "tools_used": ["工具名称"],
  "files_changed": 0,
  "domain_knowledge_gained": "获得的领域知识（如有）",
  "ai_collab": {
    "sycophancy": "引导性问题+AI顺从的场景（如有）",
    "logic_leap": "跳过推导直接跳结论的场景（如有）",
    "lazy_prompting": "直接要答案没问为什么的场景（如有）",
    "automation_surrender": "不验证AI输出直接使用的场景（如有）",
    "anchoring_effect": "被AI第一个方案锚定思维、未探索替代方案的场景（如有）"
  },
  "ai_execution": {
    "param_fidelity": "用户给了明确参数但AI未忠实执行的场景（如有）",
    "spec_compliance": "AI未遵循CLAUDE.md或项目规范的场景（如有）",
    "first_round_accuracy": "首轮实现方向是否正确（correct/partial/wrong）",
    "rework_attribution": "返工根因是用户变更还是AI执行偏差（user_change/ai_deviation/both）"
  },
  "extraction_confidence": 0.85
}
```

## friction 枚举值

- `prompt_too_long` — Prompt 过长导致注意力稀释
- `classification_ambiguity` — 分类/判断标准不清晰
- `serial_bottleneck` — 串行执行导致效率低
- `data_architecture_mismatch` — 数据格式不适合后续处理
- `scope_creep` — 范围蔓延
- `tool_misuse` — 工具使用不当
- `context_limit` — 上下文窗口不足
- `domain_knowledge_gap` — 领域知识不足
- `rework_from_poor_planning` — 规划不足导致返工
- `ai_dependency` — 过度依赖 AI 导致认知偷懒
- `other` — 其他（附说明）
