# AI 审计协议

> 归因优先级（硬约束）：AI 执行 → 流程/工具 → 用户行为。先审查 AI 自身是否忠实执行，排除 AI 因素后再质疑用户行为。

## 一、AI 执行质量审计（归因优先级最高）

从 facet 的 `ai_execution` 字段 + 原始 session 中检测三类 AI 执行问题：

**1. 参数不忠实 (Param Infidelity)**
用户给了明确数值（Playground 参数、设计稿标注、参考代码），AI 未按原值执行。
→ 标志：ai_execution.param_fidelity 有值

**2. 规范不遵循 (Spec Non-compliance)**
CLAUDE.md / shared-memory 中已有的规则，AI 实现时未遵循。
→ 标志：ai_execution.spec_compliance 有值

**3. 首轮方向性错误 (First-round Misdirection)**
AI 首轮实现与用户需求方向不同（如逐字切 vs 整行切、线性驱动 vs 有界振荡）。
→ 标志：ai_execution.first_round_accuracy == "wrong"

### 返工归因 (rework_attribution)

对每个返工循环，判定根因：
- `user_change` = 用户主动变更需求
- `ai_deviation` = AI 执行偏差导致返工
- `both` = 两者兼有

### 归因优先级规则

```
IF ai_execution 问题 ≥ 1:
  优先级置于 ai_collab（用户行为）之上
  报告「核心诊断」必须先列 AI 问题，再列用户问题
  Socratic 第 1 轮必须先质询 AI 执行问题
```

## 二、AI 协作审计（用户行为维度，5 类检测）

从 facet 的 `ai_collab` 字段 + 原始 session 中检测五类用户行为问题：

**阿谀陷阱 (Sycophancy Trap)**
用户问了引导性问题（"这样是不是更好？""用户应该会喜欢吧？"），AI 顺着说了。
→ 标志：ai_collab.sycophancy 有值

**逻辑跳跃 (Logic Leap)**
从用研直接跳到设计、从需求直接跳到代码，中间缺推导步骤。
→ 标志：ai_collab.logic_leap 有值，或相邻 session 的 goal_category 跨度大

**思维偷懒 (Lazy Prompting)**
直接问"怎么解决"而不是"为什么出错"。
→ 标志：ai_collab.lazy_prompting 有值

**自动化投降 (Automation Surrender)**
AI 给出代码/方案后直接使用，未验证正确性、未检查边界条件、未理解底层逻辑。
→ 标志：ai_collab.automation_surrender 有值

**锚定效应 (Anchoring Effect)**
被 AI 给出的第一个方案锚定思维，未探索替代方案、未质疑是否最优。
→ 标志：ai_collab.anchoring_effect 有值
