---
name: madness
license: MIT
description: >
  Use when user invokes /madness or /madness final for project-level AI collaboration
  retrospective with bidirectional feedback loop. Three modes: /madness on first run
  triggers init (baseline analysis), subsequent /madness triggers mid-review (diagnose +
  learn), /madness final triggers end-of-project review (learn + diagnose + cross-project
  methodology). Core capabilities: (1) Gene/SOP/Pref structured asset system with
  confidence lifecycle and evolution audit trail, (2) Socratic questioning with 4 rounds
  including trigger distillation, (3) CLAUDE.md rule injection via Reflection (merge/
  absorb/replace, not stacking), (4) Cross-team sharing via portable.json. Also: if
  .retro/state.json exists in project root and last_review_at exceeds review_interval_days,
  remind user at session start.
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

### Step 0.5: 跨项目知识回溯检查（所有模式）

```
IF .retro/ 存在 AND memory/ 不存在 AND .retro/reviews/ 下有历史复盘报告:
  警告用户：「检测到历史复盘数据但无 memory/ 目录。
  这意味着之前的 Gene 化流程可能未执行。
  是否从历史复盘报告中回溯提取 Gene？」
  用户确认 → 初始化 memory/，然后从 .retro/reviews/ 提取 Gene 候选
  用户跳过 → 继续，记录告警到报告中
```

### Step 1: 初始化（仅 init 模式）

如果 .retro/ 不存在，执行初始化：

1. 问用户两个问题：
   - Q1: 项目名称？（默认建议当前目录名）
   - Q2: 项目大概持续多久？（1周内 / 2-4周 / 1个月+）
     → 自动映射复盘间隔：2天 / 4天 / 7天

2. 创建目录结构 + state.json：
   ```bash
   python3 scripts/manage_state.py init \
     --project-name "用户回答的项目名" \
     --interval DAYS \
     --project-dir "当前项目根目录"
   ```

3. 检查项目 CLAUDE.md 是否已有复盘提醒行，没有则追加：
   ```
   <!-- madness retro reminder -->
   如果 .retro/state.json 存在且距 last_review_at 超过 review_interval_days，在会话开头提醒："距上次复盘已过 N 天，建议 /madness"
   ```

4. **shared-memory 扫描 + 下拉（仅当父目录有 shared-memory/ 时）**：
   ```
   IF 父目录有 shared-memory/:
     Step A: 扫描
       读取 shared-memory/META.json
       扫描兄弟项目的 memory/exports/portable.json（如有）
       输出：shared-memory 规则总数 + 兄弟项目已沉淀的 Gene 总数

     Step B: 比对去重（先比对，再下拉）
       运行 sync_shared_memory.py --direction down:
         python3 scripts/sync_shared_memory.py \
           --shared-memory-dir ../shared-memory \
           --project-memory-dir ./memory \
           --direction down
       → 输出 pull_candidates 列表（仅 shared-memory 中有但本项目无的规则）
       → 自动排除本项目 memory/ 中已有相同 id 的规则
       → 如果 Step 0.5 已回溯生成了 Gene，这里会自动跳过重复项

     Step C: 用户确认后下拉
       展示去重后的导入候选列表
       用户确认 → 批量创建到本项目 memory/，标记 imported_from_shared: true
       每条下拉的 Gene confidence 沿用 shared-memory 的值，status 设为 provisional
   ELSE:
     跳过此步骤
   ```

5. 扫描已有 session 建立基线：
   ```bash
   # 扫描新 session
   python3 scripts/scan_sessions.py \
     --state .retro/state.json --project-dir .

   # 对每个 session，子智能体提取 facet 后验证并缓存
   python3 scripts/validate_facet.py cache \
     --session-id SESSION_ID --input facet.json
   ```

6. 基线分析 → 加载 [rules/init-baseline.md](rules/init-baseline.md) 执行两阶段分析

7. **质量门控 + 展示报告**
   - 运行 `python3 scripts/check_report.py --file /tmp/madness_report_draft.md`
   - score ≥ 80 → 展示给用户看
   - score < 80 → 回到阶段 B 补充，重新检测（最多 2 次），仍不达标则标注「质量告警」后展示
   - 将质检分数附在报告末尾（用户可见）
   - **不要直接写入文件**

8. **苏格拉底质询** → 加载 [rules/socratic.md](rules/socratic.md) 执行
   - 先执行 AI 执行质量自审（前置步骤 0），再基于基线报告 + facet 中的 ai_collab 证据，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼，将行为纠偏中的强制约束转化为 Gene 候选
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告

9. **确认并存盘**
   - 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
   - 用户确认后：
     1. 执行 Step 6（Gene 化 + CLAUDE.md 注入）→ 加载 [rules/gene-protocol.md](rules/gene-protocol.md)
     2. 写入 `.retro/reviews/YYYY-MM-DD-init.md`
   - **严禁跳过确认直接存盘**

**历史复盘数据回溯检查**：
```
IF .retro/ 存在但 memory/ 不存在:
  警告用户：「检测到历史复盘数据（.retro/）但无 memory/ 目录。
  这意味着之前的 Gene 化流程可能未执行。
  是否从历史复盘报告中回溯提取 Gene？」
  用户确认 → 读取 .retro/reviews/ 中的复盘报告，提取 Gene 候选 → 执行 Step 6
  用户跳过 → 继续，但记录告警
```

初始化完成后，本次不再执行中期复盘。提示用户下次直接 `/madness`。

### 子智能体通用规则

> 详见 [rules/_shared/subagent-protocol.md](rules/_shared/subagent-protocol.md)。
> 核心：批量 ≥3 session/智能体、语义任务用 sonnet、JSON 输出必须含 4 条格式约束指令。

### Step 2: 项目扫描 + 数据采集（仅 mid / final 模式）

```
0. 项目扫描（苏格拉底质询的基础）
   - 扫描项目目录，建立对当前产出物的全景理解
   - 读取关键文件的结构和内容摘要
   - 理解项目处于什么阶段、做到了哪一步
1. 扫描新 session：
   python3 scripts/scan_sessions.py \
     --state .retro/state.json --project-dir .
   → 输出 JSON 数组到 stdout，包含 session_id、file_path、message_count、date
2. 扫描产出物变化：
   python3 scripts/scan_artifacts.py \
     --project-dir . --last-review-at LAST_REVIEW_DATE
   → 输出新增/修改文件清单和类型分布
```

### Step 3: Facet 提取（仅 mid / final 模式）

对每个新 session 提取结构化 facet：

```
1. 获取未缓存 session 列表：
   python3 scripts/validate_facet.py list-uncached \
     --sessions "$(python3 scripts/scan_sessions.py --state .retro/state.json --project-dir .)"
   → 输出需要提取 facet 的 session 列表

2. 对每个未缓存的 session：
   a. 如果 session 内容 >30K 字符，分 25K 块摘要
   b. 子智能体提取 facet（字段定义见下方）
   c. 验证并缓存：
      python3 scripts/validate_facet.py cache \
        --session-id SESSION_ID --input facet.json
      → 自动验证 13 必填字段 + 枚举值 + ai_collab 结构（5 类）+ extraction_confidence，失败则报错
```

> 子智能体使用规则见上方「子智能体通用规则」段落。

**Facet 字段定义** → 详见 [rules/_shared/facet-schema.md](rules/_shared/facet-schema.md)（含 13 必填字段、ai_collab 5 类、ai_execution 4 类、friction 11 枚举值）。

### Step 3b: Facet 质量抽检（仅 mid / final 模式，>5 个 facet 时）

> 当本轮提取的 facet 数量 >5 个时，随机抽取 2 个展示给用户确认准确性。

```
IF uncached_count > 5:
  randomly_pick 2 facets from newly cached
  FOR each picked facet:
    展示 facet 摘要（session_id + goal + goal_category + friction + ai_collab）
    问用户：「大锅，这个 facet 提取准确吗？有需要修正的吗？」
    用户确认 → 继续
    用户修正 → 更新缓存后继续
ELSE:
  跳过抽检（facet 数量少，可在报告阶段一并确认）
```

目的：在大批量提取时尽早发现子智能体的系统性提取偏差。如果 2 个抽检中 ≥1 个有重大偏差，应复核全部 facet。

### Step 4: 聚合分析（仅 mid / final 模式，两阶段）

> init 模式的两阶段分析在 Step 1→6 通过 init-baseline.md 执行，不走此步骤。

两阶段分析：阶段 A 运行 `aggregate_facets.py` 做结构化提取 + 初步诊断，阶段 B 回到原始会话深度归因（带证据链）。不允许一次成型。

> validate_genes.py 匹配结果分 high/medium/low/none 四级。medium 需 Claude 语义确认后才进入合规检测。

- **mid 模式** → 加载 [rules/mid-review.md](rules/mid-review.md) 执行（侧重「诊断 + 学习」）
- **final 模式** → 加载 [rules/final-review.md](rules/final-review.md) 执行（侧重「学习 + 诊断」）

### Step 5: 展示 + 苏格拉底质询 + 确认 + 沉淀（仅 mid / final 模式）

> **注意**：init 模式的展示、质询和确认已在 Step 1→7~9 中执行，不走此步骤。

```
1. 质量门控：运行 check_report.py 确认 score ≥ 80（详见各 rules 文件的「质量门控」section）
   score < 80 → 补充后重检（最多 2 次），仍不达标则标注「质量告警」
2. 先展示报告摘要（≤500 字）→ 问用户「展开详情？」→ 用户要求时展示完整报告
   注意：苏格拉底质询无论用户是否看了详情，都必须执行。
3. 苏格拉底质询 → 加载 rules/socratic.md 执行
   - 基于报告 + facet 中的 ai_collab + Gene 验证弹药，向用户发起 3 轮攻击性提问
   - 第 4 轮：触发条件提炼（含 Gene 验证中需修订的资产）
   - 质询完成后追加「思维尸检」+「行为纠偏」+「Gene 候选表」到报告
4. 询问：「大锅，报告 + 质询结果都在这了，需要补充或调整吗？」
5. 等待用户确认
   - 严禁在用户确认前写入文件
6. 确认后：
   - 执行 Step 6（Gene 化 + CLAUDE.md 注入）
   - 写入 .retro/reviews/YYYY-MM-DD-{mid|final}.md
   - 更新 state.json：
     python3 scripts/manage_state.py update \
       --last-review-at TODAY \
       --sessions-up-to LAST_SESSION_ID \
       --add-review mid|final
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
3. 写入 memory/：
   python3 scripts/manage_assets.py create \
     --type gene|sop|pref --data '{"title":"...","domain":[...],"trigger":"...","method":[...]}'
4. CLAUDE.md 注入 Reflection：
   python3 scripts/inject_claudemd.py \
     --claudemd ./CLAUDE.md --memory-dir ./memory --backup
5. 生成领域视图 MD

如果 memory/ 目录不存在 → 先运行 python3 scripts/init_memory.py --project-dir .

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

## 报告质量红线 & Bad Cases

> 详见 [rules/bad-cases.md](rules/bad-cases.md)。
> 4 条红线：①诊断必须有证据（引用用户原话）②改进必须可执行（步骤+检查点）③最佳实践必须含 SOP ④必须带用户成长。
> 执行时对照 bad case 自检，避免重蹈覆辙。

## 大项目策略（>30 session）

> 详见 [rules/_shared/large-project-strategy.md](rules/_shared/large-project-strategy.md)。
> 核心：批次处理（10-15 session/批）+ 摘要传递（聚合缓存持久化）+ 中间持久化（即时缓存 facet）。

## 语言

所有输出使用中文。称呼用户为「大锅」。
