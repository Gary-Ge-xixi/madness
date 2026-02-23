---
name: madness
description: >
  Use when user invokes /madness or /madness final for project-level retrospective.
  Use /madness for mid-review, /madness final for end-of-project review.
  Also: if .retro/state.json exists in project root and last_review_at exceeds the configured
  review_interval_days, remind user at session start: "距上次复盘已过 N 天，建议 /madness"
---

# /madness — 项目级会话复盘

> 一套结构化的项目复盘 workflow，从会话记录中提取可执行的改进行动，提升 AI 协作 productivity。

## 触发条件

- 用户输入 `/madness` → 中期复盘
- 用户输入 `/madness final` → 总复盘
- 会话开始时检测到 `.retro/state.json` 且距上次复盘超过间隔 → 提醒

## 执行总控流程

**严格按以下步骤执行，不要跳步。**

### Step 0: 判断模式

```
读取当前项目根目录下的 .retro/state.json
  - 文件不存在 → 模式 = init（首次初始化）
  - 文件存在 + 用户输入含 "final" → 模式 = final（总复盘）
  - 文件存在 + 无 "final" → 模式 = mid（中期复盘）
```

### Step 1: 初始化（仅 init 模式）

如果 .retro/ 不存在，执行初始化：

1. 问用户两个问题：
   - Q1: 项目名称？（默认建议当前目录名）
   - Q2: 项目大概持续多久？（1周内 / 2-4周 / 1个月+）
     → 自动映射复盘间隔：2天 / 4天 / 7天

2. 创建目录结构：
   ```
   .retro/
   ├── state.json
   ├── facets/
   └── reviews/
   ```

3. 写入 state.json（结构见下方）

4. 检查项目 CLAUDE.md 是否已有复盘提醒行，没有则追加：
   ```
   <!-- madness retro reminder -->
   如果 .retro/state.json 存在且距 last_review_at 超过 review_interval_days，在会话开头提醒："距上次复盘已过 N 天，建议 /madness"
   ```

5. 扫描已有 session 建立基线，提取 facet 并缓存

6. 基线分析 → 加载 [rules/init-baseline.md](rules/init-baseline.md) 执行两阶段分析

7. **展示报告**（不要直接写入文件）
   - 先展示给用户看

8. **苏格拉底质询** → 加载 [rules/socratic.md](rules/socratic.md) 执行
   - 基于基线报告 + facet 中的 ai_collab 证据，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼，将行为纠偏中的强制约束转化为 Gene 候选
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告

9. **确认并存盘**
   - 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
   - 用户确认后：
     1. 执行 Step 6（Gene 化 + CLAUDE.md 注入）→ 加载 [rules/gene-protocol.md](rules/gene-protocol.md)
     2. 写入 `.retro/reviews/YYYY-MM-DD-init.md`
   - **严禁跳过确认直接存盘**

初始化完成后，本次不再执行中期复盘。提示用户下次直接 `/madness`。

### 子智能体通用规则

> 适用于所有模式中的 facet 提取（init Step 1.5 / mid-final Step 3）和聚合分析。

- 每个子智能体批量处理 ≥3 个 session，不要 1 对 1
- 语义理解任务用 sonnet，不用 haiku
- **JSON 输出约束**：Prompt 中必须包含以下指令：
  ```
  输出要求：
  1. 必须是有效的 JSON 数组
  2. 字符串值中不要使用未转义的 ASCII 双引号，中文引号用「」替代
  3. 不要在 JSON 中包含注释
  4. 输出前自行验证 JSON 格式有效性
  ```

### Step 2: 项目扫描 + 数据采集（仅 mid / final 模式）

```
0. 项目扫描（苏格拉底质询的基础）
   - 扫描项目目录，建立对当前产出物的全景理解
   - 读取关键文件的结构和内容摘要
   - 理解项目处于什么阶段、做到了哪一步
1. 读取 state.json，获取 sessions_analyzed_up_to
2. 扫描 ~/.claude/projects/ 下当前项目的 JSONL 会话记录
   - 只读取 sessions_analyzed_up_to 之后的新 session
   - 过滤掉：子智能体 session、<2 条用户消息的 session
3. 扫描项目工作目录：
   - 列出自上次复盘以来新增/修改的文件
   - 统计产出物变化（文件数、总大小变化）
```

### Step 3: Facet 提取（仅 mid / final 模式）

对每个新 session 提取结构化 facet：

```
对每个未缓存的 session：
  1. 如果 session 内容 >30K 字符，分 25K 块摘要
  2. 提取 facet（字段定义见下方）
  3. 缓存到 .retro/facets/{session_id}.json
```

> 子智能体使用规则见上方「子智能体通用规则」段落。

**Facet 字段**：

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
    "lazy_prompting": "直接要答案没问为什么的场景（如有）"
  }
}
```

**friction 枚举值**：
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

### Step 4: 聚合分析（仅 mid / final 模式，两阶段）

> **注意**：init 模式的两阶段分析已在 Step 1.6 中通过 init-baseline.md 执行，不走此步骤。

mid 和 final 模式执行**两阶段分析**，不允许一次成型：

> **术语澄清**：各模式的两阶段分析维度不同，具体见各 rules 文件。init 侧重「基线建立」（结构化提取 → 深度归因），mid 侧重「诊断 + 学习」，final 侧重「学习 + 诊断」。核心约束统一：必须先提取再归因，不允许一次成型。

```
阶段 A: 结构化提取（子智能体并行）
  - 提取 facet、统计分布、识别模式
  - 产出：数据聚合 + 初步诊断

阶段 B: 深度归因分析（子智能体并行）
  - 基于阶段 A 的发现，回到原始会话数据追溯
  - 对每个摩擦点/循环/改进点，提取具体用户原话作为证据
  - 对每个"改进建议"，必须给出可执行的 SOP（步骤+检查点）
  - 对 AI 协作模式，识别阿谀陷阱/逻辑跳跃/思维偷懒的具体场景
  - 产出：带证据链的深度分析
```

- **mid 模式** → 加载 [rules/mid-review.md](rules/mid-review.md) 执行
- **final 模式** → 加载 [rules/final-review.md](rules/final-review.md) 执行

### Step 5: 展示 + 苏格拉底质询 + 确认 + 沉淀（仅 mid / final 模式）

> **注意**：init 模式的展示、质询和确认已在 Step 1.7-1.9 中执行，不走此步骤。

```
1. 将完整报告展示给用户（中文）
2. 苏格拉底质询 → 加载 rules/socratic.md 执行
   - 基于报告 + facet 中的 ai_collab + Gene 验证弹药，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼（含 Gene 验证中需修订的资产）
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告
3. 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
4. 等待用户确认
   - 严禁在用户确认前写入文件
5. 确认后：
   - 执行 Step 6（Gene 化 + CLAUDE.md 注入）
   - 写入 .retro/reviews/YYYY-MM-DD-{mid|final}.md
   - 更新 state.json（last_review_at、reviews 数组、sessions_analyzed_up_to）
   - 如果是 final 模式，额外执行 portable.json 导出（见 [rules/final-review.md](rules/final-review.md) 沉淀逻辑）
```

### Step 6: Gene 化 + CLAUDE.md 注入（所有模式，用户确认后执行）

> **注意**：此步骤在用户确认报告后执行，是存盘流程的一部分。

```
前置条件：用户已确认报告内容（包括苏格拉底质询第 4 轮的 Gene 候选）

执行：加载 rules/gene-protocol.md 执行 Step 6.1 ~ 6.5

具体流程：
1. 收集 Gene 候选（来自质询第 4 轮 + 报告改进建议）
2. 分类为 gene/sop/pref
3. 写入 memory/ 对应 JSON 文件（confidence=0.70, status=provisional）
4. 执行 CLAUDE.md 注入 Reflection（合并/吸收/替换/新增）
5. 生成领域视图 MD

如果 memory/ 目录不存在 → 先执行 gene-protocol.md 中的目录初始化

如果本次复盘无 Gene 候选（全部「已澄清」或「待观察」）→ 跳过写入，仅执行验证结果的 confidence 更新
```

---

## state.json 结构

```json
{
  "project_name": "项目名",
  "project_dir": "项目绝对路径",
  "created_at": "YYYY-MM-DD",
  "review_interval_days": 4,
  "last_review_at": "YYYY-MM-DD",
  "sessions_analyzed_up_to": "最后分析的session文件名或时间戳",
  "total_sessions": 0,
  "total_facets_cached": 0,
  "reviews": [
    {
      "type": "init | mid | final",
      "date": "YYYY-MM-DD",
      "file": "reviews/YYYY-MM-DD-type.md"
    }
  ]
}
```

## 报告质量红线

**每份报告必须满足以下标准，否则不允许展示给用户：**

### 红线 1: 诊断必须有证据
- 每个摩擦点/循环必须引用 ≥1 条用户原话作为证据
- 不允许出现"规划不足导致返工"这种没有上下文的空话
- 正确写法: "会话 X 中用户说'不如第一版本，重新构建'，返工 8 轮才收敛。根因是分类标准未在 Phase 0 定义"

### 红线 2: 改进必须可执行
- 每条改进建议必须包含：具体步骤 + 检查点 + 预期效果
- 不允许出现"Prompt 做减法不够彻底"这种不说怎么做的建议
- 正确写法: "Prompt 减法具体做法：①写步骤不写原则 ②分类标准放最前面 ③新版 Prompt 必须 A/B 测试后再推广 ④顶层≤50行"

### 红线 3: 最佳实践必须含 SOP
- 每条最佳实践必须包含：适用场景 + 具体做法 + 不适用场景
- 不允许出现"子智能体 3份/智能体"这种不解释推导过程的结论
- 正确写法: "批量提取同结构数据用 3份/智能体（18÷6=3，兼顾并行度和准确性）；精细校准用 1份/智能体；推导过程：1对1 资源浪费 → 6对1 任务过重 → 3对1 平衡点"

### 红线 4: 必须带用户成长
- 报告不只是"诊断问题"，必须"教用户如何避免"
- 每个问题必须回答：下次遇到同样情况，第一步做什么？第二步做什么？
- 对方法论演进，必须画出"从哪里来 → 经过什么转折 → 到哪里去"的轨迹

## Bad Cases

参见 [rules/bad-cases.md](rules/bad-cases.md)。执行时对照 bad case 自检，避免重蹈覆辙。

## 语言

所有输出使用中文。称呼用户为「大锅」。
