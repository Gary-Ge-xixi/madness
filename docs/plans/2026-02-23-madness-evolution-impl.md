# Madness Evolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 madness skill 从单向复盘升级为双向闭环——复盘产出 Gene/SOP/Pref 资产，自动注入 CLAUDE.md，下次复盘时验证旧资产有效性。

**Architecture:** 在现有 Step 0-5 流程基础上，新增 Step 6（Gene 化 + CLAUDE.md 注入）。苏格拉底质询新增第 4 轮（触发条件提炼）。mid/final 分析流程前插入阶段 A.0（Gene 验证 + 偏离检测）。所有新逻辑通过独立 rules 文件实现，主流程通过引用加载。

**Tech Stack:** Markdown prompt 工程 + JSON Schema 规范（纯文件系统，无代码依赖）

**Design Doc:** `docs/plans/2026-02-23-madness-evolution-design.md`

---

### Task 1: 创建 Gene 化执行规则

新增 `rules/gene-protocol.md`，定义 Gene/SOP/Pref 的创建、Reflection、CLAUDE.md 注入的完整执行协议。这是最核心的新文件，后续所有任务都引用它。

**Files:**
- Create: `rules/gene-protocol.md`

**Step 1: 创建 gene-protocol.md**

```markdown
# Gene 化执行协议

> 在用户确认报告后、存盘前执行。将复盘发现转化为结构化资产并注入 CLAUDE.md。

## 前置条件

- 苏格拉底质询（含第 4 轮提炼）已完成
- 用户已确认报告内容
- 报告中包含「提炼的 Gene 候选」表格

## Step 6.1: 收集 Gene 候选

```
来源 1: 苏格拉底质询第 4 轮产出的「待 Gene 化」候选
来源 2: 报告中的「改进 SOP」（每条可执行的改进建议）
来源 3: 报告中的「最佳实践」（已验证有效的做法）
来源 4: Gene 验证报告中的修订建议（如 trigger 过宽需收窄）

对每个候选，确认以下字段完整：
  - trigger（伪代码格式）
  - skip_when（伪代码格式）
  - method（步骤列表）
  - checkpoint（完成判定）
  - evidence（至少 1 条 session 原话引用）

缺失字段 → 回到报告/质询记录补充，不可跳过。
```

## Step 6.2: 资产分类

```
对每个候选判断资产类型：

IF 候选描述的是「遇到 X 情况怎么做」
  → type = gene（方法论基因）

IF 候选描述的是「某个流程阶段必须做哪些事」
  → type = sop（操作规程）

IF 候选描述的是「为什么选 A 不选 B」
  → type = pref（偏好/取舍规则）
```

## Step 6.3: 写入 memory/

```
1. 读取 memory/{type}s.json（如 genes.json）
   - 文件不存在 → 创建空数组 []

2. 对每个候选：
   a. 生成 id（kebab-case，从 title 派生）
   b. 设置 version = 1, confidence = 0.70, status = "provisional"
   c. 设置 validated_count = 1（本次复盘即首次验证）
   d. 填充完整 Schema 字段（见设计文档 Section 2.2）
   e. 追加到数组末尾

3. 写入 JSON 文件
4. 记录 evolution.jsonl:
   {"ts":"ISO8601","event":"create","asset_type":"...","asset_id":"...","from_review":"...","confidence":0.70}
```

## Step 6.4: CLAUDE.md 注入 Reflection

**不可跳过。这是规则集优化的核心步骤。**

```
Step 1: 增量收集
  delta = 本次新创建的资产列表

Step 2: Reflection
  读取项目 CLAUDE.md 中 <!-- madness:memory-inject start/end --> 区间
  如果区间不存在 → 这是首次注入，直接进入 Step 3
  如果区间存在 → 解析出当前 Top N 规则列表

  FOR each new_asset IN delta:

    扫描当前 Top N，寻找场景重叠：

    IF new_asset.trigger 与某条 old_rule 描述同一场景
      THEN 合并：
        - 用更精确的伪代码重写 trigger + method
        - old_rule.version += 1
        - 更新 genes.json 中对应条目
        - evolution.jsonl 记录 {"event":"merge","asset_id":old_id,"merged_from":new_id}

    ELIF new_asset 是某条 old_rule 的子集或特例
      THEN 吸收：
        - 将 new_asset 的条件加入 old_rule 的 skip_when 或 method 分支
        - 不新增规则条目
        - evolution.jsonl 记录 {"event":"absorb","asset_id":old_id,"absorbed":new_id}

    ELIF new_asset 改变了某条 old_rule 的前提假设
      THEN 修订：
        - 降低 old_rule 的 confidence（-0.10）
        - 重新评估 old_rule 是否还应留在 Top 10
        - evolution.jsonl 记录 {"event":"assumption_change","affected":old_id,"caused_by":new_id}

    ELSE（完全无关的新资产）
      IF len(current_top) < 10
        THEN 直接加入
      ELIF new_asset.confidence > min(current_top).confidence
        THEN 替换最低置信度条目
        被替换的条目仍保留在 genes.json，仅从 CLAUDE.md 移除
      ELSE
        仅存入 genes.json，不注入 CLAUDE.md

Step 3: 重写规则集
  对最终的 Top 10（或更少），统一用伪代码格式重写：
  - 每条规则 ≤ 3 行伪代码
  - 附 1 行自然语言注释（说明「为什么」）
  - 格式：# RN [type:id, c:置信度, v:版本]

Step 4: 写入 CLAUDE.md
  替换 <!-- madness:memory-inject start --> 和 <!-- madness:memory-inject end --> 之间的内容
  如果标记不存在，在文件末尾追加完整区间

Step 5: 审计
  evolution.jsonl 记录:
  {"ts":"...","event":"inject_reflection","top10_before":[...],"delta":[...],"actions":[...],"top10_after":[...]}
```

## Step 6.5: 生成领域视图

```
读取 genes.json + sops.json + prefs.json
按 domain 字段分组

FOR each domain:
  生成 memory/views/{domain}.md:
    - 标题：「{domain} 领域工作指南」
    - 副标题：「自动生成于 YYYY-MM-DD」
    - Section 1: 活跃资产（status=active, confidence≥0.85）
    - Section 2: 观察中（status=provisional, 0.50≤confidence<0.85）
    - 每条资产：标题 + 何时用 + 何时不用 + 做法摘要 + 验证次数 + 置信度
    - 底部：「完整数据见 memory/{type}s.json」

生成 memory/views/_all.md（全量视图，不按 domain 过滤）

更新 memory/INDEX.md（人类可读的资产索引）
更新 memory/index.json（机器可读的资产索引）
```

## memory/ 目录初始化

如果 memory/ 目录不存在（首次执行 Gene 化时），创建以下结构：

```
memory/
├── index.json        # {"schema_version":"1.0","assets":{"genes":0,"sops":0,"prefs":0},"last_updated":""}
├── INDEX.md          # # Memory 资产索引\n\n> 自动生成，请勿手动编辑\n\n暂无资产。
├── genes.json        # []
├── sops.json         # []
├── prefs.json        # []
├── evolution.jsonl   # （空文件）
├── views/            # （空目录）
└── exports/          # （空目录）
```
```

**Step 2: 验证文件内容一致性**

检查：
- 所有 Schema 字段与设计文档 Section 2.2 一致
- Reflection 流程与设计文档 Section 2.7 一致
- evolution.jsonl 事件类型覆盖：create, merge, absorb, assumption_change, inject_reflection

**Step 3: Commit**

```bash
git add rules/gene-protocol.md
git commit -m "feat: add Gene化 execution protocol with CLAUDE.md injection Reflection"
```

---

### Task 2: 创建 Gene 验证执行规则

新增 `rules/validation-protocol.md`，定义阶段 A.0 的 Gene 验证 + 偏离检测逻辑。mid-review.md 和 final-review.md 将引用此文件。

**Files:**
- Create: `rules/validation-protocol.md`

**Step 1: 创建 validation-protocol.md**

```markdown
# Gene 验证与偏离检测协议

> 在 mid/final 模式的两阶段分析之前执行（阶段 A.0）。验证已有资产的有效性，检测偏离，为苏格拉底质询提供弹药。

## 前置条件

- memory/ 目录存在且至少有 1 条 status=active 或 status=provisional 的资产
- 本轮新 session 的 facet 已提取完成（Step 3 完成后）
- 如果 memory/ 不存在或全部资产为空 → 跳过阶段 A.0，直接进入阶段 A

## 执行：Gene 验证

```
输入：
  - memory/genes.json 中 status IN (active, provisional) 的全部 Gene
  - memory/sops.json 中 status IN (active, provisional) 的全部 SOP
  - memory/prefs.json 中 status IN (active, provisional) 的全部 Pref
  - 本轮新 session 的所有 facet

FOR each asset IN all_active_assets:

  === Step 1: 场景匹配 ===
  扫描本轮所有 facet，判断是否存在该 asset.trigger 描述的场景。
  匹配依据：
    - facet.goal_category 与 asset.domain/tags 的相关性
    - facet.friction 与 asset.trigger 中条件的吻合度
    - facet.goal 与 asset.title 的语义相关性

  IF 本轮无匹配场景
    THEN 跳过，记录：
    evolution.jsonl: {"event":"no_match","asset_id":"...","review_period":"MM-DD~MM-DD"}
    在验证报告中标注「无匹配场景」

  IF 本轮有匹配场景 → 进入 Step 2

  === Step 2: 遵守检测 ===
  在匹配场景的 session 原始数据中，检查 asset.method 中的步骤是否被执行。

  必须引用具体 session 原文作为证据。不允许凭「感觉」判断。

  判定标准：
    - method 中的 step 被执行了 ≥ 80% → 「已遵守」
    - method 中的 step 被执行了 < 50% → 「未遵守」
    - 中间地带 → 「部分遵守」

  对 SOP：逐步检查 steps 列表，标注每步是否完成
  对 Pref：检查实际选择是否符合 trigger 中的推荐选项

  === Step 3: 效果评估 ===
  交叉对比匹配 session 的：
    - outcome（fully_achieved / partially_achieved / not_achieved）
    - friction 列表
    - loop_detected

  判定矩阵：

  | 遵守情况 | outcome | 判定 | confidence 变化 | 说明 |
  |---------|---------|------|----------------|------|
  | 已遵守 | fully_achieved | validated | +0.05（同项目）/ +0.10（跨项目） | 规则有效 |
  | 已遵守 | partially_achieved | weak_validate | +0.02 | 规则有帮助但不充分 |
  | 已遵守 | not_achieved | ineffective | -0.15 | 规则本身可能有问题 |
  | 部分遵守 | fully_achieved | partial_validate | +0.02 | 部分有效 |
  | 部分遵守 | not_achieved | inconclusive | 不变 | 无法归因 |
  | 未遵守 | fully_achieved | over_scoped | -0.10 | trigger 过宽，需收窄 |
  | 未遵守 | not_achieved | unrelated | 不变 | 无法归因 |

  === Step 4: 更新资产 ===
  根据 Step 3 的判定，更新 memory/ 中的资产：
    - confidence += delta
    - validated_count += 1（如果 result 包含 validate）
    - failed_count += 1（如果 result = ineffective）
    - last_validated = today（如果通过）
    - last_failed = today（如果失败）

  状态转换：
    - confidence ≥ 0.85 → status = "active"
    - 0.50 ≤ confidence < 0.85 → status = "provisional"
    - confidence < 0.50 → status = "deprecated"

  写入 evolution.jsonl:
  {"event":"validate","asset_id":"...","result":"...","evidence":"session原文摘录","confidence_delta":...,"new_confidence":...}
```

## 执行：偏离检测

```
在 Gene 验证之后执行。

1. SOP 偏离检测：
   FOR each active SOP:
     IF 本轮 facet 中存在 SOP.trigger 场景
       AND SOP.steps 中有 step 未被执行
     THEN 标记为 SOP 偏离：
       输出：「[SOP.title] 在 session [X] 中应被执行但未执行。
              具体：step [N] "[action]" 被跳过。
              用户原话：[引用]
              可能原因：[基于 facet.friction 和 facet.goal 推断]」

2. Pref 偏离检测：
   FOR each active Pref:
     IF 本轮 facet 中存在 Pref.trigger 场景
       AND 实际选择与 Pref 推荐不符
     THEN 标记为 Pref 偏离：
       输出：「[Pref.title] 建议在 [场景] 下选 [A]，
              但 session [X] 中选了 [B]。
              结果：[outcome]。
              需要修订偏好规则吗？」

3. 新模式发现：
   FOR each 本轮 facet:
     IF facet.learning 非空
       AND 该 learning 与所有现有 Gene 的 trigger 场景不匹配
     THEN 标记为新 Gene 候选：
       推入苏格拉底质询第 4 轮的提炼队列
       输出：「session [X] 中发现新模式："[learning]"，
              与现有 Gene 库无匹配，建议在质询中提炼为规则。」
```

## 输出：Gene 验证报告

追加到 mid/final 分析报告中（在诊断/学习 section 之前）：

```markdown
### Gene 验证报告（阶段 A.0）

**验证覆盖**：本轮 N 条活跃资产中，M 条有匹配场景，K 条无匹配。

| 资产 | 类型 | 本轮场景 | 遵守情况 | 效果 | 置信度变化 |
|------|------|---------|---------|------|-----------|
| [title] | gene/sop/pref | session [日期] [描述] | 已遵守/部分/未遵守 | [outcome] | X.XX → Y.YY |
| ... | ... | ... | ... | ... | ... |

**偏离告警**：
- [具体偏离描述 + 用户原话 + 改进建议]
- ...（如无偏离则标注「本轮无偏离」）

**新 Gene 候选**：
- [推入质询第 4 轮的新模式描述]
- ...（如无则标注「本轮无新候选」）
```

## 苏格拉底质询弹药增强

将以下验证发现传递给苏格拉底质询作为额外弹药：

```
弹药类型 1 —「遵守但无效」（ineffective）：
  「你按 [Gene名] 的规则做了，但 session [X] 的结果是 [not_achieved]。
   规则本身有问题，还是你对规则的理解有偏差？证据呢？」

弹药类型 2 —「未遵守但成功」（over_scoped）：
  「你没按 [Gene名] 做，但 session [X] 成功了。
   是运气，还是这条规则的 trigger 条件定得太宽了？
   什么情况下真的需要这条规则？」

弹药类型 3 — SOP 偏离：
  「[SOP名] 的第 [N] 步你跳过了。上次不做导致返工 [M] 轮你忘了？
   这次跳过的理由是什么？」

弹药类型 4 — Pref 偏离：
  「你说好的 [场景] 下用 [A]，这次为什么用了 [B]？
   是偏好变了，还是临时妥协？如果偏好变了，更新规则。」
```
```

**Step 2: 验证内容一致性**

检查：
- 判定矩阵 7 种情况全覆盖
- confidence 变化值与设计文档 Section 4.2 一致
- 偏离检测 3 种类型全覆盖
- 弹药类型 4 种全覆盖

**Step 3: Commit**

```bash
git add rules/validation-protocol.md
git commit -m "feat: add Gene validation and deviation detection protocol"
```

---

### Task 3: 强化苏格拉底质询 — 新增第 4 轮

修改 `rules/socratic.md`，在现有第 3 轮之后新增第 4 轮「触发条件提炼」。

**Files:**
- Modify: `rules/socratic.md:46-67` (在「输出」section 之前插入第 4 轮)

**Step 1: 在 socratic.md 第 46 行之后插入第 4 轮协议**

在 `## 输出：追加到报告末尾` 之前（即第 48 行之前）插入：

```markdown
## 第 4 轮：触发条件提炼 (Trigger Distillation)

> 把质询中暴露的隐性知识，当场压成结构化的 Gene 触发条件。不可跳过。

### 前置条件

第 1-3 轮已完成，已产出「思维尸检」初稿和「行为纠偏指南」初稿。

### 额外弹药来源

如果本次复盘执行了 Gene 验证（阶段 A.0），以下验证发现也作为第 4 轮的输入：
- 「遵守但无效」的 Gene → 追问规则是否需要修订
- 「未遵守但成功」的 Gene → 追问 trigger 是否过宽
- SOP/Pref 偏离 → 追问是否需要更新规则

### 执行逻辑

```
FOR each 行为纠偏指南中的「强制约束」:
  以及 Gene 验证中需要修订的资产:

  1. 向用户提出结构化提问（不可绕过）：

     「你刚才说 [引用用户在质询中的回答]。
      现在把它变成规则：

      IF _______ THEN 执行这个做法
      IF _______ THEN 不需要（跳过条件）

      填不出来也没关系，说你的直觉，我帮你转译。」

  2. 用户回答后，Agent 做两件事：
     a. 将用户的自然语言转译为伪代码格式的 trigger/skip_when
     b. 回显给用户确认：「我理解的是：
        IF [伪代码条件] THEN [做法]
        SKIP IF [伪代码条件]
        对吗？」

  3. 用户确认 → 暂存为 Gene 候选（status = 待Gene化）
     用户修正 → 按修正后版本暂存

  特殊情况处理：
  - 用户说「说不清楚」
    → Agent 基于 facet 证据给出 2 个候选 trigger，让用户选
    → 选中的暂存为 Gene 候选

  - 用户说「这个不需要规则化」
    → 追问：「那你怎么保证下次不犯？」
    → 用户给出合理论证 → 记录「已澄清，不 Gene 化」，附用户论证
    → 用户说不清 → 标记「待观察」，下次复盘再验证
```

### 产出

追加到报告末尾（在「思维尸检」和「行为纠偏指南」之后）：

```markdown
### 提炼的 Gene 候选

| ID（建议） | 触发条件 | 跳过条件 | 来源 | 状态 |
|-----------|---------|---------|------|------|
| [kebab-case] | IF [伪代码] | IF [伪代码] | 质询第N轮 / Gene验证 | 待 Gene 化 |
| — | 用户说不清 | — | 质询第N轮 | 待观察 |
| — | — | — | 质询第N轮 | 已澄清，不 Gene 化 |
```

### 与 Step 6 的衔接

第 4 轮产出的 Gene 候选列表，在用户确认报告后，由 Step 6（Gene 化）统一处理：
- 「待 Gene 化」→ 进入 gene-protocol.md 的 Step 6.1-6.5
- 「待观察」→ 记录到 evolution.jsonl（event: "pending_observation"），不写入 genes.json
- 「已澄清」→ 不做任何处理
```

**Step 2: 更新现有「输出」section 的引用**

将原第 48-67 行的「输出」section 中的模板，在「行为纠偏指南」之后追加提炼产出的引用说明。

修改第 61 行之后，在 `## 特殊情况` 之前追加：

```markdown
    ### 提炼的 Gene 候选
    （由第 4 轮产出，格式见上方）
```

**Step 3: 验证**

检查：
- 第 1-3 轮内容未被修改
- 第 4 轮与现有流程逻辑连贯
- 产出格式与 gene-protocol.md Step 6.1 的输入匹配
- 「额外弹药来源」与 validation-protocol.md 的输出匹配

**Step 4: Commit**

```bash
git add rules/socratic.md
git commit -m "feat: add Round 4 trigger distillation to Socratic questioning"
```

---

### Task 4: 修改 SKILL.md — 新增 Step 6

在 SKILL.md 的 Step 5 之后新增 Step 6（Gene 化），并更新 init 模式的步骤引用。

**Files:**
- Modify: `SKILL.md:183-199` (Step 5 section, 新增 Step 6)

**Step 1: 在 SKILL.md 第 199 行之后（Step 5 的 ``` 结束之后）插入 Step 6**

在 `---` 分隔线（第 201 行）之前插入：

```markdown
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
```

**Step 2: 更新 Step 5 中的存盘逻辑**

修改 SKILL.md 第 195-198 行，在存盘步骤中加入 Step 6 引用：

将：
```
5. 确认后：
   - 写入 .retro/reviews/YYYY-MM-DD-{mid|final}.md
   - 更新 state.json（last_review_at、reviews 数组、sessions_analyzed_up_to）
   - 如果是 final 模式，额外更新 memory/ 下的经验文件
```

改为：
```
5. 确认后：
   - 执行 Step 6（Gene 化 + CLAUDE.md 注入）
   - 写入 .retro/reviews/YYYY-MM-DD-{mid|final}.md
   - 更新 state.json（last_review_at、reviews 数组、sessions_analyzed_up_to）
   - 如果是 final 模式，额外执行 portable.json 导出（见 rules/final-review.md 沉淀逻辑）
```

**Step 3: 更新 init 模式的步骤引用**

修改 SKILL.md 第 69-72 行（init 模式的「确认并存盘」），加入 Gene 化引用：

将：
```
9. **确认并存盘**
   - 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
   - 用户确认后才写入 `.retro/reviews/YYYY-MM-DD-init.md`
   - **严禁跳过确认直接存盘**
```

改为：
```
9. **确认并存盘**
   - 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
   - 用户确认后：
     1. 执行 Step 6（Gene 化 + CLAUDE.md 注入）→ 加载 [rules/gene-protocol.md](rules/gene-protocol.md)
     2. 写入 `.retro/reviews/YYYY-MM-DD-init.md`
   - **严禁跳过确认直接存盘**
```

**Step 4: 更新 init 模式第 8 步的苏格拉底引用**

修改 SKILL.md 第 65-67 行，明确质询包含第 4 轮：

将：
```
8. **苏格拉底质询** → 加载 [rules/socratic.md](rules/socratic.md) 执行
   - 基于基线报告 + facet 中的 ai_collab 证据，向用户发起 3 轮攻击性提问
   - 质询完成后追加「思维尸检」和「行为纠偏」到报告
```

改为：
```
8. **苏格拉底质询** → 加载 [rules/socratic.md](rules/socratic.md) 执行
   - 基于基线报告 + facet 中的 ai_collab 证据，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼，将行为纠偏中的强制约束转化为 Gene 候选
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告
```

**Step 5: 同样更新 Step 5 中的苏格拉底引用**

修改 SKILL.md 第 189-191 行：

将：
```
2. 苏格拉底质询 → 加载 rules/socratic.md 执行
   - 基于报告 + facet 中的 ai_collab 证据，向用户发起 3 轮攻击性提问
   - 质询完成后追加「思维尸检」和「行为纠偏」到报告
```

改为：
```
2. 苏格拉底质询 → 加载 rules/socratic.md 执行
   - 基于报告 + facet 中的 ai_collab + Gene 验证弹药，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼（含 Gene 验证中需修订的资产）
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告
```

**Step 6: 验证**

检查：
- Step 0-5 原有逻辑未被破坏
- Step 6 在所有模式（init/mid/final）中都有正确入口
- 苏格拉底质询的引用统一更新为包含第 4 轮
- gene-protocol.md 的链接正确

**Step 7: Commit**

```bash
git add SKILL.md
git commit -m "feat: add Step 6 Gene化 to SKILL.md, update Socratic refs to include Round 4"
```

---

### Task 5: 修改 mid-review.md — 新增阶段 A.0 + 报告模板更新

**Files:**
- Modify: `rules/mid-review.md:10-12` (在「执行：聚合分析」之前插入阶段 A.0)
- Modify: `rules/mid-review.md:102-131` (Summary 模板新增 Gene 验证 section)

**Step 1: 在 mid-review.md 第 10 行（`## 执行：聚合分析`）之前插入阶段 A.0**

在 `## 输入` section 之后、`## 执行：聚合分析` 之前插入：

```markdown
## 执行：阶段 A.0 — Gene 验证与偏离检测

> 在常规两阶段分析之前执行。如果 memory/ 不存在或无活跃资产 → 跳过此阶段。

加载 [rules/validation-protocol.md](validation-protocol.md) 执行：

1. **Gene 验证**：对所有 active/provisional 资产，检查本轮 facet 中是否有匹配场景，验证遵守情况和效果
2. **偏离检测**：检查 SOP 偏离、Pref 偏离、新模式发现
3. **弹药准备**：将验证发现（遵守但无效、未遵守但成功、偏离）传递给苏格拉底质询
4. **产出**：Gene 验证报告（追加到分析报告最前面）

验证完成后，更新 memory/ 中资产的 confidence 和 status。

```

**Step 2: 更新 Summary 模板**

在 mid-review.md 的 Summary 模板中，在 `### 做得好的` 之前插入 Gene 验证 section：

```markdown
### Gene 验证报告
（如果执行了阶段 A.0，在此展示验证结果表格、偏离告警、新 Gene 候选。格式见 validation-protocol.md 的「输出」section。如果未执行阶段 A.0 则省略此 section。）
```

**Step 3: 更新质量自检**

在 mid-review.md 的质量自检清单中追加：

```markdown
- [ ] 如果存在活跃 Gene/SOP/Pref，是否执行了阶段 A.0 验证？
- [ ] Gene 验证报告中每条判定是否有 session 原文证据？
```

**Step 4: 验证**

检查：
- 现有分析组 A/B 逻辑未被修改
- 阶段 A.0 在分析组 A 之前执行
- Summary 模板中 Gene 验证 section 位置合理
- validation-protocol.md 链接正确

**Step 5: Commit**

```bash
git add rules/mid-review.md
git commit -m "feat: add Phase A.0 Gene validation to mid-review"
```

---

### Task 6: 修改 final-review.md — 新增阶段 A.0 + portable.json 导出

**Files:**
- Modify: `rules/final-review.md:10-12` (在分析组 A 之前插入阶段 A.0)
- Modify: `rules/final-review.md:118-161` (Summary 模板新增 Gene 验证 section)
- Modify: `rules/final-review.md:171-182` (沉淀逻辑新增 portable.json 导出)

**Step 1: 在 final-review.md 第 10 行（`## 执行：聚合分析`）之前插入阶段 A.0**

与 Task 5 的 Step 1 相同内容，插入 Gene 验证阶段。

**Step 2: 更新 Summary 模板**

在 final-review.md 的 Summary 模板中，在 `### 项目成果` 之前插入：

```markdown
### Gene 验证报告
（格式同 mid-review，见 validation-protocol.md）
```

在 `### 沉淀到 memory 的内容` 之后追加：

```markdown
### 跨团队共享包
- 导出资产数量：N 条 Gene + M 条 SOP + K 条 Pref
- 导出文件：memory/exports/portable.json
- 接收方挂载方式：复制 portable.json 到自己的 memory/exports/，下次 /madness 时自动检测并提示导入
```

**Step 3: 更新沉淀逻辑**

修改 final-review.md 第 175-182 行的沉淀逻辑：

将：
```
1. 写入 .retro/reviews/YYYY-MM-DD-final.md（完整分析）
2. 更新 state.json
3. 将「可复用方法论」和「不熟悉领域行动清单」写入 memory/ 目录：
   - 如果 memory/ 下已有相关主题文件，追加/更新
   - 如果没有，创建新文件并在 MEMORY.md 中添加索引
4. 提示用户：「总复盘完成。如需清理 .retro/ 目录可手动删除，或保留供下个项目参考。」
```

改为：
```
1. 写入 .retro/reviews/YYYY-MM-DD-final.md（完整分析）
2. 更新 state.json
3. 执行 Step 6（Gene 化 + CLAUDE.md 注入）→ 加载 rules/gene-protocol.md
4. 生成 portable.json 导出包：
   - 筛选 memory/ 中 status=active 且 confidence ≥ 0.70 的资产
   - 将 confidence 重置为 portable_confidence = 0.60
   - 将 status 设为 "provisional"
   - 保留 original_confidence 字段供接收方参考
   - 写入 memory/exports/portable.json:
     {
       "schema_version": "1.0",
       "exported_at": "YYYY-MM-DD",
       "exported_by": "大锅",
       "source_project": "[项目名]",
       "assets": { "genes": [...], "sops": [...], "prefs": [...] }
     }
5. 提示用户：
   「总复盘完成。
   - memory/ 下的资产已更新，CLAUDE.md 已注入最新规则集
   - portable.json 已生成，可发给同事供其项目挂载
   - 如需清理 .retro/ 目录可手动删除，memory/ 建议保留供下个项目继承」
```

**Step 4: 更新质量自检**

追加：

```markdown
- [ ] 如果存在活跃资产，是否执行了阶段 A.0 验证？
- [ ] portable.json 中的 confidence 是否已重置为 0.60？
- [ ] portable.json 中的 status 是否全部为 "provisional"？
```

**Step 5: 验证**

检查：
- 现有分析组 A（学习组）/ B（诊断组）逻辑未被修改
- 阶段 A.0 在分析组 A 之前执行
- 沉淀逻辑正确引用 gene-protocol.md
- portable.json 格式与设计文档 Section 5.1 一致

**Step 6: Commit**

```bash
git add rules/final-review.md
git commit -m "feat: add Phase A.0 Gene validation + portable.json export to final-review"
```

---

### Task 7: 端到端一致性验证

完成所有文件修改后，做一次全局一致性检查。

**Files:**
- Read: 所有已修改文件

**Step 1: 检查引用链完整性**

```
SKILL.md Step 6 → 引用 rules/gene-protocol.md ✓
SKILL.md Step 8 (init) → 引用 rules/socratic.md（含第4轮）✓
SKILL.md Step 5 (mid/final) → 引用 rules/socratic.md（含第4轮）✓
mid-review.md 阶段 A.0 → 引用 rules/validation-protocol.md ✓
final-review.md 阶段 A.0 → 引用 rules/validation-protocol.md ✓
final-review.md 沉淀逻辑 → 引用 rules/gene-protocol.md ✓
socratic.md 第4轮 → 产出 Gene 候选 → 被 gene-protocol.md Step 6.1 消费 ✓
validation-protocol.md → 产出弹药 → 被 socratic.md 第4轮消费 ✓
```

**Step 2: 检查数据流闭环**

```
Session → Facet 提取 → 阶段 A.0 验证旧 Gene → 两阶段分析 →
苏格拉底质询（1-3轮 + 第4轮提炼）→ 用户确认 →
Step 6 Gene 化 → memory/ 写入 → CLAUDE.md 注入 →
下次 Session 生效 → 下次 /madness 验证 → 闭环 ✓
```

**Step 3: 检查 Schema 一致性**

```
gene-protocol.md 中的 Gene Schema ↔ 设计文档 Section 2.2 ✓
validation-protocol.md 中的判定矩阵 ↔ 设计文档 Section 4.2 ✓
portable.json 格式 ↔ 设计文档 Section 5.1 ✓
evolution.jsonl 事件类型全覆盖：
  create, validate, invalidate, deprecate, merge, absorb,
  assumption_change, inject_reflection, pending_observation,
  no_match, import, import_merge, import_skip ✓
```

**Step 4: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: consistency fixes from end-to-end validation"
```
