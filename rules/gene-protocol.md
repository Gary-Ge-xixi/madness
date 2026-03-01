# Gene 化执行协议

> 在用户确认报告后、存盘前执行。将复盘发现转化为结构化资产并注入 CLAUDE.md。

## 前置条件

- 苏格拉底质询（含 Step 5 触发条件提炼）已完成
- 用户已确认报告内容
- 报告中包含「提炼的 Gene 候选」表格（来自质询 Step 5）

## Step 6.1: 收集 Gene 候选

```
来源 1: 苏格拉底质询 Step 5 产出的「待 Gene 化」候选
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

建议新 Gene 添加探索豁免：
  - 对于方法论类 Gene，建议添加 skip_when: "goal_category == 'explore_learn'"
  - 用户可在 Step 6.1 确认时决定是否采纳此默认建议
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
前置检查（仅当父目录有 shared-memory/ 时）：
  IF shared-memory/META.json 存在:
    读取 META.json 的 rules 列表
    对每个 Gene 候选，检查 shared-memory 中是否已有同类规则（相同 id 或语义相同 trigger）
    IF 发现已有同类:
      提示用户：「shared-memory 中已有类似规则 [rule_id]（来自 [source_project]）。
      是合并到已有规则，还是作为独立 Gene 创建？」
      用户选合并 → 更新已有 Gene 的 version + confidence
      用户选独立 → 正常创建，标记 related_shared_rule: [rule_id]

对每个候选，运行脚本创建资产（自动处理 ID 生成、去重、版本号、evolution 记录）：

python3 "$MADNESS_DIR"/scripts/manage_assets.py create \
  --type gene|sop|pref \
  --data '{
    "title": "一句话标题",
    "domain": ["适用领域"],
    "tags": [],
    "trigger": "伪代码触发条件",
    "skip_when": "伪代码跳过条件",
    "method": ["步骤1", "步骤2"],
    "checkpoint": "完成判定",
    "expected_outcome": "预期效果",
    "evidence": [{"project":"...","session":"...","quote":"用户原话","lesson":"..."}],
    "created_from": "reviews/YYYY-MM-DD-type.md"
  }'

→ 脚本自动：
  - 生成 kebab-case id（从 title 派生，自动去重）
  - 设置 version=1, confidence=0.70, status="provisional"
  - 追加到 memory/{type}s.json
  - 记录 evolution.jsonl

对 SOP 类型，将 method 替换为 steps：
  --data '{"steps": [{"seq":1,"action":"...","checkpoint":"..."}]}'

对 Pref 类型，将 method 替换为 rationale + tradeoff：
  --data '{"rationale":"为什么选A不选B","tradeoff":"代价是什么"}'
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

Step 4-5: 运行注入脚本（自动处理合并检测、规则重写、写入、审计）：
  python3 "$MADNESS_DIR"/scripts/inject_claudemd.py \
    --claudemd ./CLAUDE.md \
    --memory-dir ./memory \
    --max-rules 10 \
    --backup
  → 脚本自动：
    - 读取所有 active/provisional 资产（confidence≥0.50）
    - 解析已有规则，执行 merge（同 id → version+1）
    - 生成伪代码格式规则块（≤3 行/条）
    - 替换 <!-- madness:memory-inject start/end --> 区间
    - 备份原始 CLAUDE.md
    - stdout 输出变更日志（merge/new/replace actions）

  注意：Reflection 的语义判断（合并 vs 吸收 vs 修订）仍由 Claude 执行。
  脚本处理的是结构化 merge（同 id 匹配）。
  对于需要语义判断的场景（如 trigger 描述同一场景但 id 不同），
  Claude 应先通过 manage_assets.py update 调整资产，再运行注入脚本。
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

如果 memory/ 不存在（首次 Gene 化时），运行初始化脚本：

```bash
python3 "$MADNESS_DIR"/scripts/manage_assets.py init --project-dir .
```

→ 自动创建完整目录结构：
```
memory/
├── index.json        # {"schema_version":"1.0","assets":{"genes":0,"sops":0,"prefs":0},"last_updated":""}
├── INDEX.md          # # Memory 资产索引（自动生成）
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
