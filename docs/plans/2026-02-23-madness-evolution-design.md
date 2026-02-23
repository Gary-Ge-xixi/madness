# Madness Skill Evolution — 设计文档

> Smart Retrospective：从单向存档到双向闭环的进化架构

## 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 核心定位 | Smart Retrospective | 保留现有流程骨架，增量升级，最快落地 |
| 注入机制 | CLAUDE.md 自动摘要注入 | 零工具链依赖，利用 Claude Code 现有机制 |
| 认知提纯 | 苏格拉底质询强化版 | 最小改动，复用现有质询管道 |
| Schema 层级 | 统一 JSON + 领域视图 MD | 底层一份 JSON 存所有，视图层按领域自动生成 |
| CLAUDE.md 注入策略 | Reflection + Top 10 伪代码 | 不是截断排序，是带自反思的规则集优化 |

---

## 一、架构总览

### 数据流闭环

```
Session JSONL ──→ Facet 提取 ──→ 两阶段分析
                                    │
                                    ▼
                           苏格拉底质询（强化版）
                           ┌──────────────────┐
                           │ 第4轮：触发条件提炼 │
                           │ IF/THEN 强制卡点  │
                           └────────┬─────────┘
                                    │
                                    ▼
                     ┌───────── Gene 化 ─────────┐
                     │                           │
                     ▼                           ▼
               genes.json                  sops.json
               prefs.json
                     │                           │
                     └─────────┬─────────────────┘
                               │
                               ▼
                     ┌─────────────────────┐
                     │  CLAUDE.md 注入      │
                     │  Reflection → Top 10 │
                     └────────┬────────────┘
                              │
                              ▼
                   下一次 Session 自动生效
                              │
                              ▼
                   下次 /madness → Gene 验证
                   置信度 +/- 调整
                   失效 Gene 降级/淘汰
```

### 相对现有 madness 的增量改动

1. **socratic.md** — 新增第 4 轮「触发条件提炼」
2. **SKILL.md** — 新增 Step 6「Gene 化 + CLAUDE.md 注入」
3. **mid-review.md** — 新增阶段 A.0「Gene 验证 + 偏离检测」
4. **final-review.md** — 新增阶段 A.0 + 导出 portable.json
5. **memory/ 目录** — 全新的结构化资产存储

---

## 二、memory/ Schema 设计

### 目录结构

```
memory/
├── index.json              # 资产索引（机器入口）
├── INDEX.md                # 资产索引（人类入口）
├── genes.json              # 方法论基因库
├── sops.json               # 操作规程库
├── prefs.json              # 偏好/取舍规则库
├── evolution.jsonl          # 进化事件流（审计链）
├── views/                  # 领域视图层（自动生成）
│   ├── product.md
│   ├── dev.md
│   ├── research.md
│   └── _all.md
└── exports/                # 跨团队共享
    └── portable.json
```

### Gene Schema

```json
{
  "id": "string — 唯一标识，kebab-case",
  "version": "number — 版本号，每次合并/修订 +1",
  "type": "gene",
  "title": "string — 一句话标题",
  "domain": ["string[] — 适用领域标签：product/dev/research/..."],
  "tags": ["string[] — 自由标签"],

  "trigger": "string — 伪代码格式的触发条件",
  "skip_when": "string — 伪代码格式的跳过条件",

  "method": ["string[] — 执行步骤，Step 1/2/3..."],
  "checkpoint": "string — 怎么判断做对了",
  "expected_outcome": "string — 可量化或可观察的预期效果",

  "evidence": [
    {
      "project": "string — 来源项目",
      "session": "string — 来源 session ID",
      "quote": "string — 用户原话引用",
      "lesson": "string — 教训/经验"
    }
  ],

  "confidence": "number — 0.0~1.0",
  "validated_count": "number — 验证通过次数",
  "failed_count": "number — 验证失败次数",
  "status": "active | provisional | deprecated",

  "created_at": "string — YYYY-MM-DD",
  "created_from": "string — 来源复盘文件路径",
  "last_validated": "string — YYYY-MM-DD",
  "last_failed": "string | null"
}
```

### SOP Schema

```json
{
  "id": "string",
  "version": "number",
  "type": "sop",
  "title": "string",
  "domain": ["string[]"],
  "tags": ["string[]"],

  "trigger": "string — 何时执行此 SOP",
  "skip_when": "string — 何时跳过",

  "steps": [
    {
      "seq": "number",
      "action": "string — 具体动作",
      "checkpoint": "string — 该步骤的完成判定"
    }
  ],

  "evidence": [{ "project": "", "quote": "", "lesson": "" }],

  "confidence": "number",
  "validated_count": "number",
  "status": "active | provisional | deprecated",
  "created_at": "string",
  "last_validated": "string"
}
```

### Pref Schema

```json
{
  "id": "string",
  "version": "number",
  "type": "pref",
  "title": "string",
  "domain": ["string[]"],
  "tags": ["string[]"],

  "trigger": "string — 何时应用此偏好",
  "skip_when": "string — 何时不适用",

  "rationale": "string — 为什么选 A 不选 B",
  "tradeoff": "string — 取舍的代价是什么",

  "evidence": [{ "project": "", "quote": "", "lesson": "" }],

  "confidence": "number",
  "validated_count": "number",
  "status": "active | provisional | deprecated",
  "created_at": "string",
  "last_validated": "string"
}
```

### 进化事件流 (evolution.jsonl)

每行一个事件：

```jsonl
{"ts":"ISO8601","event":"create|validate|invalidate|deprecate|merge|import|inject_reflection|pending_observation|no_match|import_merge|import_skip","asset_type":"gene|sop|pref","asset_id":"string","detail":"string","confidence_delta":"number"}
```

### 置信度生命周期

```
创建 → confidence = 0.70（单项目单次验证）
  │
验证通过（同项目）→ +0.05
验证通过（跨项目）→ +0.10
验证失败 → -0.15 ~ -0.30
  │
  ├─ ≥ 0.85 → active（注入 CLAUDE.md）
  ├─ 0.50 ~ 0.84 → provisional（仅存储）
  └─ < 0.50 → deprecated（隐藏）
```

---

## 三、CLAUDE.md 注入协议

### 注入不是截断排序，是 Reflection 流程

```
Step 1: 增量收集（delta = 本次复盘产出的新资产）

Step 2: Reflection（不可跳过）
  FOR each delta_asset:
    IF 与旧资产描述同一场景
      → 合并，用更精确伪代码重写 trigger/method
      → version +1, evolution.jsonl 记 merge 事件
    IF 是旧资产的子集/特例
      → 吸收进旧资产的 skip_when 或 method 分支
      → 不新增条目
    IF 与 Top 10 完全无关
      → 与最低置信度条目比较
      → 赢了替换，输了仅存 genes.json
    IF 改变了旧资产的前提假设
      → 降低旧资产置信度
      → 重新评估旧资产是否留在 Top 10

Step 3: 重写规则集
  - Top 10，每条 ≤ 3 行伪代码 + 1 行注释
  - 统一格式写入 CLAUDE.md 的 madness:memory-inject 区间
```

### CLAUDE.md 中的注入格式

```markdown
<!-- madness:memory-inject start -->
## 复盘沉淀规则集（vN, YYYY-MM-DD）

# R1 [gene:classify-first, c:0.92, v:3]
IF items > 10 AND categories_undefined:
    define_standard(samples=3) → classify → revise_if_mismatch
# 分类前必须先定标准，否则返工率 > 60%

# R2 [sop:phase0-checklist, c:0.88, v:2]
IF project_start OR new_phase:
    check(classification_standard, output_format, metric_definition, success_criteria)
# Phase 0 四项检查，缺一项后续返工概率翻倍

...（最多 10 条）

<!-- madness:memory-inject end -->
```

---

## 四、苏格拉底质询强化 — 第 4 轮提炼协议

### 在现有三轮质询之后新增第 4 轮

```
第 1-3 轮（保留）：攻击性提问 → 追问 → 澄清/定性
第 4 轮（新增）：触发条件提炼（Trigger Distillation）
```

### 第 4 轮执行协议

```
FOR each 行为纠偏指南中的「强制约束」:

  1. 结构化提问（不可绕过）：
     「你刚才说 [引用质询中的回答]。
      现在把它变成规则：
      IF _______ THEN 执行这个做法
      IF _______ THEN 不需要（跳过条件）
      填不出来也没关系，说你的直觉，我帮你转译。」

  2. 用户回答后：
     a. Agent 将自然语言转译为伪代码 trigger/skip_when
     b. 回显确认：「我理解的是 [伪代码]，对吗？」

  3. 用户确认 → 暂存为 Gene 候选（待 Step 6 处理）

  特殊情况：
  - 「说不清楚」→ Agent 给 2 个候选 trigger 让用户选
  - 「不需要规则化」→ 追问「怎么保证下次不犯？」
    有合理论证 → 记录「已澄清」
    说不清 → 标记「待观察」
```

### 提炼产出格式

追加到报告末尾（思维尸检和行为纠偏之后）：

```markdown
### 提炼的 Gene 候选

| ID | 触发条件 | 跳过条件 | 来源 | 状态 |
|----|---------|---------|------|------|
| classify-first-v2 | IF items>10 AND no_standard | IF categories<3 AND predefined | 质询第2轮 | 待 Gene 化 |
| [无法提炼] | — | — | 质询第1轮 | 待观察 |
```

---

## 五、动态评估引擎 — Gene 验证与偏离检测

### 阶段 A.0: Gene 验证协议

在 mid-review / final-review 的两阶段分析之前插入：

```
FOR each active_asset IN [genes, sops, prefs]:

  1. 场景匹配：本轮 facet 中是否出现 trigger 场景？
     无匹配 → skip，记录 no_match
     有匹配 → 进入验证 ↓

  2. 遵守检测（必须引用 session 原文）：
     method steps 执行 ≥ 80% → 已遵守
     method steps 执行 < 50% → 未遵守
     中间 → 部分遵守

  3. 效果评估（交叉 outcome × friction × loop）：
     已遵守 + fully_achieved → validated, confidence +0.05/+0.10
     已遵守 + not_achieved → 遵守但无效, confidence -0.15
     未遵守 + fully_achieved → 未遵守但成功, confidence -0.10（trigger 过宽）
     未遵守 + not_achieved → 无法归因, confidence 不变

  4. 写入 evolution.jsonl
```

### 偏离检测

```
1. SOP 偏离：trigger 场景存在但 steps 未执行
2. Pref 偏离：trigger 场景存在但选了标记为「不选」的选项
3. 新模式发现：facet.learning 与现有 Gene 不匹配 → 推入第 4 轮提炼队列
```

### 验证结果在报告中的呈现

mid/final Summary 新增 section：

```markdown
### Gene 验证报告

| 资产 | 本轮场景 | 遵守情况 | 效果 | 置信度变化 |
|------|---------|---------|------|-----------|
| ... | ... | ... | ... | ... |

**偏离告警**：
- [具体偏离描述 + 用户原话 + 改进建议]

**新 Gene 候选**：
- [推入质询第 4 轮的新模式]
```

### 苏格拉底质询弹药增强

现有弹药源 + 新增 4 类：
- 「遵守但无效」→ 规则有问题还是理解有偏差？
- 「未遵守但成功」→ 运气还是规则过时？
- SOP 偏离 → 为什么跳过？上次不做的后果忘了？
- Pref 偏离 → 为什么选了「不该选」的？

---

## 六、跨团队共享 — 开箱即用挂载协议

### portable.json 导出

final 模式沉淀时自动生成：

```json
{
  "schema_version": "1.0",
  "exported_at": "YYYY-MM-DD",
  "exported_by": "导出者名称",
  "source_project": "项目名",
  "assets": {
    "genes": [/* status=active, confidence≥0.70, confidence 重置为 0.60 */],
    "sops": [/* 同上 */],
    "prefs": [/* 同上 */]
  }
}
```

### 挂载逻辑

```python
def mount_external_memory(portable_path, local_memory_path):
    portable = read_json(portable_path)
    assert portable["schema_version"] == "1.0"

    for asset_type in ["genes", "sops", "prefs"]:
        local = read_json(f"{local_memory_path}/{asset_type}.json") or []
        incoming = portable["assets"][asset_type]

        for item in incoming:
            existing = find_by_id(local, item["id"])
            if existing is None:
                # 新资产：provisional 导入
                item["status"] = "provisional"
                item["confidence"] = item["portable_confidence"]
                local.append(item)
            elif existing["confidence"] < item["original_confidence"]:
                # 外部更强：合并，降级 provisional
                merged = merge_assets(existing, item)
                merged["status"] = "provisional"
                replace_in(local, merged)
            else:
                # 本地更强：跳过
                pass

        write_json(f"{local_memory_path}/{asset_type}.json", local)

    regenerate_views(local_memory_path)
    refresh_claude_md_injection(local_memory_path)
```

### 关键约束

- 导入资产一律 provisional，不直接注入 CLAUDE.md
- 必须经过接收方自己的 /madness 验证后才能升级为 active
- 防止「盲目继承」

---

## 七、工程死穴与对策

| 死穴 | 严重性 | 对策 |
|------|--------|------|
| JSON 并发写入 | 低（仅复盘时写入） | append 式更新 + 写后校验 |
| 置信度漂移 | 中 | 验证必须引用 session 原文，审计链可追溯 |
| CLAUDE.md 膨胀 | 高 | Reflection 流程 + Top 10 硬限 + 伪代码精简表达 |
| Gene 验证的 Agent 误判 | 中 | 强制证据引用 + 苏格拉底质询交叉验证 |

---

## 八、改动文件清单

| 文件 | 改动类型 | 内容 |
|------|---------|------|
| SKILL.md | 修改 | 新增 Step 6（Gene 化 + CLAUDE.md 注入） |
| rules/socratic.md | 修改 | 新增第 4 轮提炼协议 |
| rules/mid-review.md | 修改 | 新增阶段 A.0（Gene 验证 + 偏离检测）+ 报告模板新增 Gene 验证 section |
| rules/final-review.md | 修改 | 新增阶段 A.0 + portable.json 导出逻辑 |
| rules/gene-protocol.md | 新增 | Gene 化执行规则 + CLAUDE.md 注入 Reflection 协议 |
| rules/validation-protocol.md | 新增 | Gene 验证 + 偏离检测的详细执行规则 |
| memory/ 目录 | 新增 | 完整的 Schema 结构（首次 /madness 时创建） |
