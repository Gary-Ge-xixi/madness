# 中期复盘执行步骤

> 侧重：诊断 + 学习。目标是纠偏当前方向、提取阶段性认知。

## 输入

- 本轮新 session 的所有 facet（从 .retro/facets/ 读取，筛选上次复盘之后的）
- 项目目录产出物变化清单

## 执行：阶段 A.0 — Gene 验证与偏离检测

> 在常规两阶段分析之前执行。如果 memory/ 不存在或无活跃资产 → 跳过此阶段。

先运行结构化验证脚本：
```bash
python3 "$MADNESS_DIR"/scripts/validate_genes.py \
  --memory-dir ./memory --retro-dir .retro --since LAST_REVIEW_DATE
```

然后加载 [validation-protocol.md](validation-protocol.md) 补充语义验证：

1. **Gene 验证**：基于脚本输出的 evidence_sessions，回到原始会话验证遵守情况和效果
2. **偏离检测**：检查 SOP 偏离、Pref 偏离、新模式发现
3. **弹药准备**：将验证发现（遵守但无效、未遵守但成功、偏离）传递给苏格拉底质询
4. **产出**：Gene 验证报告（追加到分析报告最前面）

验证完成后，更新 memory/ 中资产的 confidence 和 status。

## 执行：聚合分析

### 分析组 A：诊断（按顺序逐项分析）

> **数据基础**：先运行 `python3 "$MADNESS_DIR"/scripts/aggregate_facets.py --retro-dir .retro --since LAST_REVIEW_DATE` 获取聚合统计（goal_category 分布、friction Top5、loop_rate、ai_collab 统计等）。以下分析基于脚本输出 + 子智能体深度归因。

**1. 循环检测**

```
- 筛选所有 loop_detected=true 的 facet
- 对每个循环，输出：
  「什么问题 → 循环了几个 session → 根因推断 → 建议怎么打破」
- 如果无循环，输出「本轮未检测到循环模式」
```

**2. 效率瓶颈**

```
- 按 goal_category 分组，统计每组的 session 数和总耗时
- 找出占比最高的 1-2 个类别
- 输出：「最耗时的任务类型 → 是否存在可以并行/自动化/简化的空间」
```

**3. 决策质量**

```
- 收集所有 facet 中的 key_decision 字段（跳过空值）
- 评估：
  - 决策是否及时（问题出现到决策之间隔了几个 session？）
  - 是否有该做但没做的决策（基于 friction 推断）
- 输出：「做了哪些决策 → 及时性评估 → 遗漏的决策建议」
```

**4. 摩擦点分类**

```
- 聚合所有 facet 的 friction 字段，按类型计数
- 排序后取 Top 3
- 对每个摩擦类型，输出：「类型 → 出现次数 → 典型场景 → 改进建议」
```

**5-6. AI 执行质量 + 协作审计**

> 加载 [_shared/ai-audit.md](_shared/ai-audit.md) 执行。

- 统计 tools_used 使用分布，交叉分析 tools_used × outcome
- 输出：「AI 执行问题清单 → 受影响的 session → 返工归因分布」
- 输出：「AI 用得好的模式 → 协作中的认知陷阱 → 具体场景引用 → 纠偏建议」
- AI 执行发现在苏格拉底质询（Step 5）中优先于用户行为问题
- 协作审计发现将作为苏格拉底质询（Step 5）的弹药

**7. 产出物变化**

使用 Glob 扫描项目目录，找出自上次复盘以来新增/修改的文件：
- 扫描项目根目录（排除 .git、.retro、node_modules、__pycache__、.venv）
- 按类型分类（报告 .md/.txt、数据 .json/.csv、工具 .py/.ts、可视化 .png/.svg/.html）
- 统计新增文件数量和类型分布

基于扫描结果：
```
- 解读新增/修改文件清单和类型分布
- 评估产出物与本轮目标的匹配度
- 输出：「新增了哪些产出 → 是否符合阶段预期 → 产出效率评估」
- 在 Summary 的「做得好的」或「卡住的地方」中酌情引用产出数据
```

**8. Goal-Gap 分析（GRAI-G 维度）**

> 仅当 state.json 中 goals 非空时执行。

```
读取 state.json 的 goals 列表（含 success_criteria 和 status）
读取 goal_history 获取变更记录
FOR each goal:
  - 从本轮 facet 中匹配相关 session（goal_category + goal 关键词匹配）
  - 评估进展：对照 success_criteria 判断达成程度
  - 更新 status：not_started → in_progress → achieved / abandoned / changed
  - 如果偏离：引用 facet 证据说明何时何因偏离
  - 如果 success_criteria 为空：标注「无量化标准，按定性判断」
输出：GRAI 目标回顾表格（填入报告模板的 grai:goal-review section）
输出：GRAI 结果比对表格（填入报告模板的 grai:result-comparison section）
```

### 分析组 B：学习（按顺序逐项分析）

**1. 新认知清单**

```
- 收集所有 facet 中的 learning 字段（跳过空值）
- 去重、归类为三种：
  - 领域知识（关于项目所在领域的认知）
  - 方法论（关于如何做事的认知）
  - 工具技巧（关于 AI/工具使用的认知）
- 输出清单，每条标注类别
```

**2. 领域知识图谱（增量）**

```
- 收集所有 domain_knowledge_gained
- 如果存在上次复盘的 MD，对比标注哪些是新增的
- 输出：「上次复盘时掌握 X → 本轮新增了 Y → 当前领域知识范围」
```

**3. 认知纠偏**

```
- 筛选 outcome=not_achieved 的 facet
- 从中提取 learning 字段
- 输出：「原来以为 A → 实际发现是 B → 这对后续工作意味着什么」
- 如果没有失败 session，输出「本轮无认知纠偏事件」
```

## 输出：摘要（≤500 字，先展示）

先展示摘要，用户要求时再展示详情。

```markdown
## 本轮复盘摘要（MM-DD ~ MM-DD）
**新 session**：N | **产出**：M | **循环**：X | **Gene 验证**：Y 条通过
**一句话诊断**：[最大问题/最大亮点]
**Goal-Gap**：N 个目标中 X 个在轨 / Y 个偏离（仅当 goals 非空）
**关键行动**：1. [...] 2. [...]
> 输入「展开详情」查看完整报告。
```（end template）

## 输出：详情（用户要求时展示）

按以下模板生成，**先展示给用户，确认后才存盘**：

```markdown
## 本轮复盘（MM-DD ~ MM-DD）

**新 session 数**：N 个 | **新产出文件**：M 个 | **检测到循环**：X 次

---

### Gene 验证报告
（如果执行了阶段 A.0，在此展示验证结果表格、**遵守亮点**、偏离告警、新 Gene 候选。格式见 [validation-protocol.md](validation-protocol.md) 的「输出」section。如未执行阶段 A.0 则省略此 section。）

<!-- grai:goal-review start -->
### 目标回顾
| 目标 | 优先级 | 成功标准 | 当前状态 | 变更记录 |
|------|--------|---------|---------|---------|
（从 state.json goals 填入，status 字段映射为中文：not_started=未开始, in_progress=进行中, achieved=已达成, abandoned=已放弃, changed=已变更）
（变更记录列从 goal_history 中筛选该目标相关条目，格式：MM-DD action reason）
<!-- grai:goal-review end -->

<!-- grai:result-comparison start -->
### 结果比对
| 目标 | 预期成果（success_criteria） | 实际结果 | 差距 | 亮点/不足 |
|------|---------------------------|---------|------|----------|
（基于 facet 聚合 + goals 交叉分析，对每个目标评估实际进展与 success_criteria 的差距）

**亮点**：（至少 1 条，带 session 证据：哪个 session、什么行为、什么结果）
**不足**：（至少 1 条，带用户原话引用）
<!-- grai:result-comparison end -->

<!-- grai:analysis start -->
### 原因分析
#### 主观原因（用户决策/认知层面）
...（带证据链：具体 session + 用户原话 + 行为后果）
#### 客观原因（AI/工具/环境层面）
...（带证据链：具体 session + 工具表现 + 影响范围）
<!-- grai:analysis end -->

<!-- grai:insight start -->
### 规律总结
（从多个 session/场景归纳的通用规律，IF/THEN 结构）
- IF [触发条件/场景] THEN [推荐做法] BECAUSE [证据/原因]
（标注适用边界和不适用场景）
<!-- grai:insight end -->

---

### 卡住的地方
对每条摩擦：
- **现象**: 引用用户原话
- **根因**: 不是表面原因，追到底层
- **改进 SOP**: 具体步骤 + 检查点（不说空话）
- **预期效果**: 量化的或可观察的

### 学到的
- [1-2 条关键认知，标注类别]
- 每条画出"原来以为 → 实际发现 → 意味着什么"

### 下一步行动
1. [问题] → [Step 1: ...] → [Step 2: ...] → [检查点: ...] → [预期效果]
2. [问题] → [Step 1: ...] → [Step 2: ...] → [检查点: ...] → [预期效果]
```

## 确认话术

Summary 展示后，必须询问：

> 「大锅，本轮复盘报告在上面了。有需要补充或调整的吗？确认后我再存盘。」

**严禁跳过确认直接存盘。** 用户确认后才写入 `.retro/reviews/YYYY-MM-DD-mid.md` 并更新 `state.json`。

## 质量门控（展示前必须通过，不可跳过）

> 加载 [_shared/quality-gate.md](_shared/quality-gate.md) 执行。

mid 模式额外自检项：
- [ ] 如果存在活跃 Gene/SOP/Pref，是否执行了阶段 A.0 验证？
- [ ] Gene 验证报告中每条判定是否有 session 原文证据？

## 注意事项

- 所有分析基于 facet 数据，不做无依据的推测
- 如果新 session 数 ≤2，提示用户「session 太少，建议积累更多再复盘」但仍可继续
- 诊断要具体到 session 级别的证据，不说空话
- 行动建议必须是下一阶段可立即执行的，不是长期愿景
- **改进建议必须回答"第一步做什么、第二步做什么、怎么判断做对了"**
