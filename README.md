# /madness — 项目级 AI 协作复盘系统

一套为 Claude Code 设计的结构化复盘 skill，从会话记录中提取可执行的改进行动，形成**双向反馈闭环**：不只是回顾过去，更把认知沉淀为可验证、可演化的规则资产，持续优化人-AI 协作质量。

## 核心理念

传统复盘是**单向归档**：回顾 → 总结 → 存起来 → 遗忘。

/madness 是**双向反馈闭环**：

```
Session → Facet 提取 → A.0 验证 → 两阶段分析 → 苏格拉底质询(4轮)
    ↑                                                          ↓
    └── CLAUDE.md 注入 ← memory/ 资产 ← Gene 化 ← 触发条件提炼
```

每次复盘不仅产出报告，还会：
1. **验证**已有规则在新场景中是否有效（Gene 验证协议）
2. **提炼**新的行为模式为结构化资产（Gene/SOP/Pref）
3. **优化**注入 CLAUDE.md 的规则集（Reflection 机制，非简单堆叠）
4. **质询**用户的思维盲区（苏格拉底式攻击性提问）

## 快速开始

### 安装

将本仓库克隆到 Claude Code 的 skills 目录：

```bash
# 全局安装
git clone https://github.com/Gary-Ge-xixi/madness.git ~/.claude/skills/madness

# 或项目级安装
git clone https://github.com/Gary-Ge-xixi/madness.git .claude/skills/madness
```

### 使用

在 Claude Code 中输入：

| 命令 | 说明 |
|------|------|
| `/madness` | 首次使用自动初始化；之后触发中期复盘 |
| `/madness final` | 项目结束时的总复盘 |

首次运行会引导你完成项目配置（项目名称、持续时间），之后自动按间隔提醒复盘。

## 三种复盘模式

### Init（首次初始化）

自动扫描已有会话记录，建立基线分析。包含：
- 基线报告（两阶段：结构化提取 → 深度归因）
- 苏格拉底质询 3 轮 + 触发条件提炼（第 4 轮）
- Gene 化 + CLAUDE.md 注入

### Mid（中期复盘）

侧重**诊断 + 学习**，纠偏当前方向：
- 阶段 A.0：Gene 验证 — 验证已有规则的有效性
- 诊断组：循环检测 → 效率瓶颈 → 决策质量 → 摩擦点 → AI 协作审计（5 类）→ 产出物变化
- 学习组：新认知清单 → 领域知识图谱 → 认知纠偏
- 两层报告：先展示摘要（≤500 字），用户要求时展开详情
- 苏格拉底质询 + Gene 化

### Final（总复盘）

侧重**学习 + 诊断**，沉淀跨项目方法论：
- 阶段 A.0：全量 Gene 验证
- 学习组：能力成长曲线 → 可复用方法论 → 领域知识全图 → 不熟悉领域应对策略
- 诊断组：全程摩擦热力图 → 时间效率审计 → 循环模式 → 决策复盘 → AI 协作审计（5 类）
- 生成 portable.json 跨团队共享包

## 核心机制

### Gene/SOP/Pref 资产体系

复盘发现被结构化为三类资产，存储在 `memory/` 目录：

| 类型 | 含义 | 示例 |
|------|------|------|
| **Gene** | 方法论基因 — 遇到 X 情况怎么做 | 分类前必须先定标准 |
| **SOP** | 操作规程 — 某阶段必须做哪些事 | Phase 0 四项检查清单 |
| **Pref** | 偏好规则 — 为什么选 A 不选 B | 批量提取用 3份/智能体 |

每条资产包含：触发条件（伪代码）、跳过条件、执行步骤、检查点、证据链。

### 置信度生命周期

```
创建 → confidence = 0.70（provisional）
  │
验证通过（同项目）→ +0.05
验证通过（跨项目）→ +0.10
验证失败 → -0.15 ~ -0.30
  │
  ├─ >= 0.85 → active（注入 CLAUDE.md）
  ├─ 0.50 ~ 0.84 → provisional（仅存储）
  └─ < 0.50 → deprecated（隐藏）
```

### CLAUDE.md 注入 Reflection

不是简单堆叠规则，而是走 Reflection 流程：
- **合并**：新旧规则描述同一场景 → 精确重写
- **吸收**：新规则是旧规则的特例 → 归入分支
- **修订**：新规则改变旧规则前提 → 降低置信度
- **替换**：Top 10 满员 → 替换最低置信度条目

最终输出 <= 10 条伪代码规则，每条 <= 3 行。

### 苏格拉底质询

7 步结构化质询，不是温柔的总结，是逼用户面对思维盲区：
- Step 1-2：AI 自审 + 证据构建（内部执行）
- Step 3（可选）：亮点确认 — 先肯定后质疑，降低防御心理
- Step 4：攻击性质询 3 轮（引用 session 原话，追问证据）— 通过 AskUserQuestion 提供结构化回复选项
- Step 5：触发条件提炼 — 将隐性知识压成 IF/THEN 规则
- Step 6（可选）：学习路径推荐 — 基于认知缺陷推荐具体学习方向
- Step 7：输出追加到报告

### 跨团队共享

总复盘会生成 `memory/exports/portable.json`，可发给同事挂载：
- 置信度自动降级（重置为 0.60）
- 状态设为 provisional（需在新项目中重新验证）

## 项目结构

```
madness/
├── SKILL.md                    # 入口 — 总控流程定义
├── README.md                   # 本文件
├── rules/
│   ├── init-baseline.md        # Init 模式两阶段分析
│   ├── mid-review.md           # Mid 模式聚合分析
│   ├── final-review.md         # Final 模式聚合分析 + portable.json
│   ├── socratic.md             # 苏格拉底质询协议（7 步：自审→证据→亮点→质询→提炼→学习→输出）
│   ├── gene-protocol.md        # Gene 化执行协议 + CLAUDE.md Reflection
│   ├── validation-protocol.md  # Gene 验证与偏离检测协议（四级匹配）
│   └── bad-cases.md            # 质量反面教材（6 条自检规则）
├── scripts/
│   ├── validate_facet.py       # Facet 验证与缓存（5 类 ai_collab + extraction_confidence、支持 raw JSON 输入）
│   ├── validate_genes.py       # Gene 验证协议（四级匹配 + 探索豁免 + 正向反馈）
│   ├── aggregate_facets.py     # Facet 聚合统计（含 --output-file 持久化、--facets-dir 兼容）
│   ├── check_report.py         # 报告质量红线自检（7 条规则，满分 100）
│   ├── manage_assets.py        # Gene/SOP/Pref 资产 CRUD + memory/ 初始化
│   ├── inject_claudemd.py      # CLAUDE.md 规则注入
│   └── scan_sessions.py        # 会话扫描
└── docs/plans/                 # 设计文档与实现计划
```

运行时生成的目录（在项目根目录下）：

```
.retro/                         # 复盘数据（项目级）
├── state.json                  # 状态文件
├── facets/                     # Session facet 缓存
└── reviews/                    # 复盘报告

memory/                         # 认知资产（可跨项目继承）
├── genes.json                  # 方法论基因
├── sops.json                   # 操作规程
├── prefs.json                  # 偏好规则
├── evolution.jsonl             # 资产演化审计日志
├── index.json                  # 机器索引
├── INDEX.md                    # 人类索引
├── views/                      # 领域视图
└── exports/                    # 跨团队共享包
```

## 报告质量红线

每份报告必须满足 6 条红线（自动化检测，总分 100，阈值 80）：

1. **诊断必须有证据** — 引用用户原话，不说空话
2. **改进必须可执行** — 包含具体步骤 + 检查点 + 预期效果
3. **最佳实践必须含 SOP** — 适用场景 + 做法 + 不适用场景
4. **必须带用户成长** — 教用户如何避免，画出演进轨迹
5. **两阶段分析结构** — 必须包含结构化提取 + 深度归因
6. **摘要/详情分离** — 先展示 ≤500 字摘要，用户要求时展开详情

## 更新记录

### v2.2.0 (2026-03-01) — 苏格拉底质询交互升级

- **AskUserQuestion 集成**：苏格拉底质询关键交互节点从纯文本改为结构化选项
  - Step 4 攻击性质询：用户可点选「我有证据反驳」「确实没深想」「部分认同」，降低回复成本
  - Step 5 触发条件提炼：回显确认、「说不清楚」候选选择、「不需要规则化」追问均使用结构化选项
  - Step 6 学习路径推荐：单缺陷单选、多缺陷 multiSelect 批量勾选
  - 所有节点保留 Other 自由输入选项，Fallback 到纯文本模式（工具不可用时）
- **步骤命名规范化**：质询协议从 Round 0/0.5/1-3/4/4.5 重命名为 Step 1-7 顺序编号
  - Step 1: AI 自审 → Step 2: 证据构建 → Step 3: 亮点确认 → Step 4: 攻击性质询 → Step 5: 触发条件提炼 → Step 6: 学习路径推荐 → Step 7: 输出

### v2.1.1 (2026-02-26) — 脚本输入健壮性修复

- **aggregate_facets.py**：新增 `--facets-dir` 兼容参数，自动推导 `--retro-dir`，修复 AI 传错参数时的 `unrecognized arguments` 错误
- **validate_facet.py**：`read_input()` 支持直接解析 raw JSON 字符串，修复 AI 将 JSON 当 `--input` 值传入导致的 `Errno 63: File name too long`

### v2.1.0 (2026-02-24) — 问题诊断与覆盖面分析

**7 维度系统性修复：**

- **AI 协作偏差扩展**：ai_collab 从 3 类扩展为 5 类
  - 新增 `automation_surrender`（自动化投降：不验证 AI 输出直接使用）
  - 新增 `anchoring_effect`（锚定效应：被 AI 第一个方案锚定思维）
  - 向后兼容：旧 facet 仍 valid，缺失新字段给 warning

- **语义匹配升级**：validate_genes.py 场景匹配从 bool 重构为四级（high/medium/low/none）
  - 加权评分系统：goal_category +2 / friction +2 / keyword overlap +1~3 / learning +1
  - medium 级别由 Claude 语义确认，解决关键词匹配准确性瓶颈

- **正向反馈闭环**：新增 `validated_highlights` 输出
  - `promotion_candidate`：provisional 资产验证通过将升为 active
  - `compliance_success`：active 资产被遵守且效果达成
  - 苏格拉底质询 Round 0.5：先肯定后质疑，降低用户防御心理

- **两层报告结构**：降低认知过载
  - 第一层：摘要（≤500 字）先展示，含一句话诊断 + 关键行动
  - 第二层：详情（用户要求时展示）保留完整模板
  - check_report.py 新增 Rule 6 检测摘要/详情分离

- **探索模式豁免**：explore_learn 占比 >50% 时 non_compliant → exploration_exempt
  - gene-protocol.md 建议新 Gene 添加 `skip_when: "goal_category == 'explore_learn'"`

- **Facet 质量校验**：新增 `extraction_confidence` 字段 + Step 3b 抽检机制

- **大项目策略**：>30 session 时批次处理 + 摘要传递 + 中间持久化
  - aggregate_facets.py 新增 `--output-file` 参数

### v2.0.0 (2026-02-23) — 双向反馈闭环

**新增核心能力：**

- **Gene 化执行协议** (`rules/gene-protocol.md`)
  - 将复盘发现转化为 Gene/SOP/Pref 三类结构化资产
  - CLAUDE.md 注入 Reflection 机制（合并/吸收/修订/替换，非简单堆叠）
  - Top 10 伪代码规则集自动生成与优化
  - memory/ 目录初始化与管理
  - evolution.jsonl 审计日志

- **Gene 验证与偏离检测协议** (`rules/validation-protocol.md`)
  - 阶段 A.0：在分析前验证已有资产有效性
  - 4 步验证流程：场景匹配 → 遵守检测 → 效果评估 → 资产更新
  - 7 种判定矩阵（validated / weak_validate / ineffective / partial_validate / inconclusive / over_scoped / unrelated）
  - 3 类偏离检测（SOP 偏离 / Pref 偏离 / 新模式发现）
  - 苏格拉底质询弹药增强

- **苏格拉底质询第 4 轮** (`rules/socratic.md`)
  - 触发条件提炼：将隐性知识压成 IF/THEN 伪代码
  - Gene 验证弹药集成
  - 特殊情况处理（说不清楚 / 不需要规则化）

- **跨团队共享** (`rules/final-review.md`)
  - portable.json 导出（置信度降级 + status 重置）
  - 接收方挂载协议

**修改：**

- `SKILL.md`：新增 Step 6（Gene 化 + CLAUDE.md 注入），更新 init/mid/final 流程引用
- `rules/mid-review.md`：新增阶段 A.0 Gene 验证入口
- `rules/final-review.md`：新增阶段 A.0、portable.json 导出、跨团队共享 Summary 模板

**修复：**

- 修正 mid-review.md 和 final-review.md 中 3 处链接显示文本不一致
- 补充 validation-protocol.md 中 confidence < 0.50 时的 deprecate 事件记录

### v1.0.0 — 初始版本

- 基础复盘流程：init / mid / final 三模式
- Facet 提取与缓存
- 两阶段分析（结构化提取 → 深度归因）
- 苏格拉底质询（3 轮）
- 报告质量红线

## License

MIT
