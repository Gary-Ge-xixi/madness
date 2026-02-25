# 总复盘执行步骤

> 侧重：学习 + 诊断。目标是沉淀可跨项目复用的认知，形成个人方法论。

## 输入

- **全部** facet（.retro/facets/ 下所有文件，含已缓存的历史 facet）
- 所有中期复盘 MD（.retro/reviews/*-mid.md）
- 项目最终产出物清单（扫描项目目录）

## 执行：阶段 A.0 — Gene 验证与偏离检测

> 在常规两阶段分析之前执行。如果 memory/ 不存在或无活跃资产 → 跳过此阶段。

先运行结构化验证脚本（使用全部 facet，不加 --since 过滤）：
```bash
python3 scripts/validate_genes.py \
  --memory-dir ./memory --retro-dir .retro
```

然后加载 [validation-protocol.md](validation-protocol.md) 补充语义验证：

1. **Gene 验证**：基于脚本输出的 evidence_sessions，回到原始会话验证遵守情况和效果
2. **偏离检测**：检查 SOP 偏离、Pref 偏离、新模式发现
3. **弹药准备**：将验证发现传递给苏格拉底质询
4. **产出**：Gene 验证报告（追加到分析报告最前面）

验证完成后，更新 memory/ 中资产的 confidence 和 status。

## 执行：聚合分析

### 分析组 A：学习组（主线，先执行）

**1. 能力成长曲线**

```
- 按时间排列所有中期复盘中的「学到的」部分
- 绘制认知变化轨迹：
  「项目初期认知水平 → 中期转折点事件 → 最终认知水平」
- 标注：哪个阶段成长最快，什么事件/决策触发了认知跃升
- 如果只有 1 次中期复盘，基于 facet 时间线重建轨迹
```

**2. 可复用方法论沉淀**

```
- 从全部 key_decision + learning 中提炼跨项目可复用的模式
- 筛选标准：至少在 2 个 session 中被验证有效（outcome=fully_achieved）
- 输出格式：
  「场景（什么时候用）→ 方法（怎么做）→ 为什么有效（证据）」
- 这些将作为 memory/ 沉淀的候选内容
```

**3. 领域知识全图**

```
- 汇总全项目所有 domain_knowledge_gained
- 分类为：
  - 核心知识（项目完成必须掌握的）
  - 延伸知识（有帮助但非必须的）
  - 边缘知识（偶然接触到的）
- 输出：从零到现在，在这个领域构建了什么知识体系
```

**4. 不熟悉领域的应对策略评估**

```
- 回顾项目初期（前 1/3 的 session）的 facet：
  - friction 中 domain_knowledge_gap 出现频率
  - outcome 达成率
  - 采用了什么探索策略
- 对比后期（后 1/3 的 session）的同类指标
- 输出：
  「初期策略是什么 → 效果如何 → 后来调整为什么 → 效果如何」
  「下次遇到不熟悉领域的推荐路径：」
    Step 1: ...
    Step 2: ...
    Step 3: ...
```

### 分析组 B：诊断组（辅线，后执行）

> **数据基础**：运行 `python3 scripts/aggregate_facets.py --retro-dir .retro` 获取全量聚合统计。以下分析基于脚本输出 + 子智能体深度归因。

**1. 全程摩擦热力图**

```
- 按时间维度（按周或按复盘周期分段）聚合 friction
- 输出：
  「第 1 阶段主要摩擦：X → 第 2 阶段：Y → 第 3 阶段：Z」
  「持续未解决的摩擦：[列表]」
  「成功消除的摩擦：[列表] + 怎么消除的」
```

**2. 时间效率审计**

```
- 统计：总 session 数 × 平均每 session 时长 = 总投入时间
- 按 goal_category 拆分时间占比
- 估算理论最优路径（如果所有最佳决策都及时做出）
- 输出：「实际 X 天/Y session → 理论最优估算 → 差距主要来自哪」
```

**3. 循环模式总结**

```
- 汇总全项目所有 loop_detected=true 的 facet
- 寻找共性：
  - 循环发生在什么类型的任务上？
  - 循环的触发模式是什么？（如：加 Prompt 长度解决不了就继续加）
  - 循环平均持续几个 session 才打破？
- 输出：「个人循环触发器识别 → 预防建议」
```

**4. 决策复盘**

```
- 列出全项目所有 key_decision
- 对每个决策标注结果：有效 / 无效 / 效果有限 / 待验证
- 排序后输出：
  「Top 3 最佳决策 + 为什么好」
  「Top 3 最差决策（或最迟的决策）+ 教训」
```

**5-6. 全项目 AI 执行质量 + 协作审计**

> 加载 [_shared/ai-audit.md](_shared/ai-audit.md) 执行。

final 模式特殊要求（全量视角）：
- 按三类问题统计**分布和演变趋势**（哪些阶段最容易出问题）
- 全程返工归因分布：user_change vs ai_deviation vs both 的比例 + 趋势
- 交叉分析：ai_collab 问题 × outcome 的关系
- 输出：「全项目 AI 执行质量画像 → 高危场景 → AI 执行偏差趋势」
- 输出：「全项目 AI 协作模式画像 → 高危场景 → 认知依赖趋势」
- 这些将作为苏格拉底质询和思维尸检的核心证据

## 输出：摘要（≤500 字，先展示）

```markdown
## 项目总复盘摘要：[项目名]（MM-DD ~ MM-DD）
**总 session**：N | **总耗时**：约 X 天 | **复盘次数**：M 次
**一句话总结**：[最大收获/最大教训]
**核心成果**：[1-2 句关键产出]
**Top 行动**：1. [...] 2. [...]
> 输入「展开详情」查看完整报告。
```（end template）

## 输出：详情（用户要求时展示）

按以下模板生成，**先展示给用户，确认后才存盘**：

```markdown
## 项目总复盘：[项目名]（MM-DD ~ MM-DD）

**总 session**：N 个 | **总耗时**：约 X 天 | **复盘次数**：M 次（含本次）

---

### Gene 验证报告
（格式见 [validation-protocol.md](validation-protocol.md) 的「输出」section，包括**遵守亮点**、偏离告警、新 Gene 候选）

### 项目成果
- 交付了什么（列出关键产出物）
- 质量评估（基于后期 session 的 outcome 达成率）

### 效率审计
- 实际投入 vs 理论最优
- 差距的主要来源（Top 2-3 原因）

### Top 3 成功模式
1. [场景] → [做法] → [效果]
2. [场景] → [做法] → [效果]
3. [场景] → [做法] → [效果]

### Top 3 失败模式
1. [场景] → [做错了什么] → [教训]
2. [场景] → [做错了什么] → [教训]
3. [场景] → [做错了什么] → [教训]

### 个人成长
- 入门时的认知水平
- 关键转折点
- 现在的认知水平
- 成长最快的阶段及原因

### 下次不熟悉领域的行动清单
1. [具体步骤]
2. [具体步骤]
3. [具体步骤]
...

### 沉淀到 memory 的内容
- [将要写入 memory/ 的方法论摘要，供用户确认]

### 跨团队共享包
- 导出资产数量：N 条 Gene + M 条 SOP + K 条 Pref
- 导出文件：memory/exports/portable.json
- 接收方挂载方式：复制 portable.json 到自己的 memory/exports/，下次 /madness 时自动检测并提示导入
```

## 确认话术

Summary 展示后，必须询问：

> 「大锅，项目总复盘报告在上面了。有需要补充或调整的吗？确认后我再存盘并沉淀到 memory。」

**严禁跳过确认直接存盘。** 用户确认后才执行下方沉淀逻辑。

## 沉淀逻辑

用户确认 Summary 后：

```
0. 强制 memory/ 存在性检查：
   IF memory/ 不存在:
     警告：「总复盘必须先完成 Gene 化，但 memory/ 目录不存在。」
     自动运行 python3 scripts/init_memory.py --project-dir .
     然后继续执行下方流程
1. 写入 .retro/reviews/YYYY-MM-DD-final.md（完整分析）
2. 更新 state.json
3. 执行 Step 6（Gene 化 + CLAUDE.md 注入）→ 加载 [gene-protocol.md](gene-protocol.md)
4. 生成 portable.json 导出包：
   python3 scripts/manage_assets.py export-portable --min-confidence 0.70 --memory-dir ./memory
   → 自动筛选 active 且 confidence≥0.70 的资产
   → confidence 重置为 0.60，status 设为 "provisional"
   → 保留 original_confidence 字段
   → 写入 memory/exports/portable.json
5. shared-memory 上推（仅当父目录有 shared-memory/ 时）：
   ```
   IF 父目录有 shared-memory/:
     Step A: 检测候选
       python3 scripts/sync_shared_memory.py \
         --shared-memory-dir ../shared-memory \
         --project-memory-dir ./memory \
         --direction up
       → 输出 push_candidates + conflicts

     Step B: Reflection 比对（先比对，再更新）
       对每个 push_candidate:
         读取 shared-memory 目标文件中已有的规则段落
         执行语义比对（类似 CLAUDE.md 注入的 Reflection 逻辑）：

         IF 目标文件已有语义相同的规则（trigger 描述同一场景）
           THEN 合并：用更精确的措辞重写该段落
           更新 META.json 中该条目的 version + confidence + validated_by
           evolution.jsonl: {"event":"merge_to_shared"}

         ELIF 目标文件已有该规则的旧版本（同 id 但内容更新）
           THEN 替换：用新版本覆盖旧段落
           更新 META.json 版本号
           evolution.jsonl: {"event":"update_shared"}

         ELSE（完全新规则）
           追加到目标文件对应 section
           在 META.json 中新增条目
           evolution.jsonl: {"event":"push_to_shared"}

     Step C: 用户确认后执行写入
       展示比对结果（合并 N 条 / 替换 N 条 / 新增 N 条）
       用户确认后：
       - 按 Step B 结果更新 shared-memory 文件
       - 更新 META.json
       - 项目 Gene 添加 "promoted_to_shared": true
       - 记录 evolution.jsonl
   ELSE:
     跳过此步骤
   ```
6. 提示用户：
   「总复盘完成。
   - memory/ 下的资产已更新，CLAUDE.md 已注入最新规则集
   - portable.json 已生成，可发给同事供其项目挂载
   - 如需清理 .retro/ 目录可手动删除，memory/ 建议保留供下个项目继承」
```

## 质量门控（展示前必须通过，不可跳过）

> 加载 [_shared/quality-gate.md](_shared/quality-gate.md) 执行。

final 模式额外自检项：
- [ ] 成长曲线有具体事件和时间戳（不是"显著提升"）？
- [ ] 如果存在活跃资产，是否执行了阶段 A.0 验证？
- [ ] portable.json 中的 confidence 是否已重置为 0.60？
- [ ] portable.json 中的 status 是否全部为 "provisional"？

## 注意事项

- 总复盘是整个项目的终结性分析，要有全局视角，不只是最后一轮的分析
- 「可复用方法论」要具体到可操作的步骤，不是抽象原则
- 「不熟悉领域行动清单」要基于本项目的实际经验推导，不是通用建议
- 成长曲线要有具体事件支撑，不说「显著提升」这类空话
- memory/ 沉淀内容需要用户确认后才写入
- **改进建议必须回答"第一步做什么、第二步做什么、怎么判断做对了"**
