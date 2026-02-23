# Gene 化执行协议

> 在用户确认报告后、存盘前执行。将复盘发现转化为结构化资产并注入 CLAUDE.md。

## 前置条件

- 苏格拉底质询（含第 4 轮提炼）已完成
- 用户已确认报告内容
- 报告中包含「提炼的 Gene 候选」表格（来自质询第 4 轮）

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
   d. 填充完整 Schema 字段（见下方 Schema 参考）
   e. 追加到数组末尾

3. 写入 JSON 文件
4. 记录 evolution.jsonl:
   {"ts":"ISO8601","event":"create","asset_type":"...","asset_id":"...","from_review":"...","confidence":0.70}
```

### Gene Schema 参考

```json
{
  "id": "string — kebab-case 唯一标识",
  "version": 1,
  "type": "gene | sop | pref",
  "title": "string — 一句话标题",
  "domain": ["string[] — 适用领域：product/dev/research/..."],
  "tags": ["string[] — 自由标签"],
  "trigger": "string — 伪代码触发条件",
  "skip_when": "string — 伪代码跳过条件",
  "method": ["string[] — 执行步骤"],
  "checkpoint": "string — 完成判定",
  "expected_outcome": "string — 预期效果",
  "evidence": [
    {
      "project": "string",
      "session": "string",
      "quote": "string — 用户原话",
      "lesson": "string"
    }
  ],
  "confidence": 0.70,
  "validated_count": 1,
  "failed_count": 0,
  "status": "provisional",
  "created_at": "YYYY-MM-DD",
  "created_from": "string — 来源复盘文件路径",
  "last_validated": "YYYY-MM-DD",
  "last_failed": null
}
```

SOP 额外字段（替换 method）：
```json
{
  "steps": [
    {"seq": 1, "action": "string", "checkpoint": "string"}
  ]
}
```

Pref 额外字段（替换 method）：
```json
{
  "rationale": "string — 为什么选 A 不选 B",
  "tradeoff": "string — 代价是什么"
}
```

## Step 6.4: CLAUDE.md 注入 Reflection

**不可跳过。这是规则集优化的核心步骤。**

```
Step 1: 增量收集
  delta = 本次新创建的资产列表

Step 2: Reflection
  读取项目 CLAUDE.md 中 <!-- madness:memory-inject start/end --> 区间
  如果区间不存在 → 首次注入，直接进入 Step 3
  如果区间存在 → 解析当前 Top N 规则列表

  FOR each new_asset IN delta:

    扫描当前 Top N，寻找场景重叠：

    IF new_asset.trigger 与某条 old_rule 描述同一场景
      THEN 合并：
        - 用更精确伪代码重写 trigger + method
        - old_rule.version += 1
        - 更新对应 JSON 文件
        - evolution.jsonl: {"event":"merge","asset_id":old_id,"merged_from":new_id}

    ELIF new_asset 是某条 old_rule 的子集或特例
      THEN 吸收：
        - 加入 old_rule 的 skip_when 或 method 分支
        - 不新增条目
        - evolution.jsonl: {"event":"absorb","asset_id":old_id,"absorbed":new_id}

    ELIF new_asset 改变了某条 old_rule 的前提假设
      THEN 修订：
        - old_rule.confidence -= 0.10
        - 重新评估是否留在 Top 10
        - evolution.jsonl: {"event":"assumption_change","affected":old_id,"caused_by":new_id}

    ELSE（完全无关）
      IF len(current_top) < 10
        THEN 直接加入
      ELIF new_asset.confidence > min(current_top).confidence
        THEN 替换最低置信度条目（被替换者仍保留在 JSON，仅从 CLAUDE.md 移除）
      ELSE
        仅存入 JSON，不注入 CLAUDE.md

Step 3: 重写规则集
  对最终 Top 10（或更少），统一用伪代码格式重写：
  - 每条 ≤ 3 行伪代码
  - 附 1 行注释说明「为什么」
  - 格式：# RN [type:id, c:置信度, v:版本]

Step 4: 写入 CLAUDE.md
  替换 <!-- madness:memory-inject start --> 和 <!-- madness:memory-inject end --> 之间的内容
  如果标记不存在 → 在文件末尾追加完整区间

Step 5: 审计
  evolution.jsonl:
  {"ts":"...","event":"inject_reflection","top10_before":[...],"delta":[...],"actions":[...],"top10_after":[...]}
```

### CLAUDE.md 注入格式

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

## Step 6.5: 生成领域视图

```
读取 genes.json + sops.json + prefs.json
按 domain 字段分组

FOR each domain:
  生成 memory/views/{domain}.md:
    标题：「{domain} 领域工作指南」
    副标题：「自动生成于 YYYY-MM-DD」
    Section 1: 活跃资产（status=active, confidence≥0.85）
      每条：标题 + 何时用 + 何时不用 + 做法摘要 + 验证次数 + 置信度
    Section 2: 观察中（status=provisional, 0.50≤confidence<0.85）
    底部：「完整数据见 memory/{type}s.json」

生成 memory/views/_all.md（全量视图）
更新 memory/INDEX.md（人类索引）
更新 memory/index.json（机器索引）
```

## memory/ 目录初始化

如果 memory/ 不存在（首次 Gene 化时），创建：

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

## 置信度生命周期

```
创建 → confidence = 0.70（status = provisional）
  │
验证通过（同项目）→ +0.05
验证通过（跨项目）→ +0.10
验证失败 → -0.15 ~ -0.30
  │
  ├─ ≥ 0.85 → status = active（注入 CLAUDE.md）
  ├─ 0.50 ~ 0.84 → status = provisional（仅存储）
  └─ < 0.50 → status = deprecated（从视图隐藏）
```
