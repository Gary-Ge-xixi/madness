# 苏格拉底质询协议

> 在展示报告后、确认存盘前执行。目标不是总结问题，是逼用户面对思维盲区。

## Step 1：AI 执行质量自审（不可跳过）

> 加载 [_shared/ai-audit.md](_shared/ai-audit.md) 执行。

在质询用户行为之前，必须先按 ai-audit.md 的归因优先级审查 AI 自身的执行质量。

```
IF ai_execution 问题 ≥ 1:
  Step 4 第 1 轮必须先质询 AI 执行问题
  质询措辞示例：
  - 「在 [日期] 的会话中，你给了 AI [参数/参考]，但 AI 实现时 [偏差描述]。这不是你的问题，是 AI 执行偏差。我们需要一条规则来防止下次再犯。」
  - 「CLAUDE.md 第 N 行写了 [规则]，但 AI 在 [session] 中没有遵循。这是 AI 的规范遵循缺陷，不是你的指令不够清晰。」
```

构建完 AI 执行问题清单后，再进入下方的用户行为证据构建。

---

## Step 2：证据构建（内部执行，不展示）

> 按 [_shared/ai-audit.md](_shared/ai-audit.md) 的五类用户行为检测定义，从 facet 的 `ai_collab` 字段 + 原始 session 中寻找嫌疑。

如果 facet 中证据不足，回到原始 session 数据补充。
构建至少 3 条"起诉书"后进入质询。

## Step 3：亮点确认（可选）

> 在攻击性质询前，先用 1-2 句话确认正向行为。降低用户防御心理。

IF 本轮有 validated_highlights（来自阶段 A.0）:
  用 1-2 句话确认亮点，例如：
  「大锅，这轮做得好的：[asset_title] 规则你执行到位了，效果也验证了。」
  不展开讨论，快速进入 Step 4。

IF 无 validated_highlights:
  跳过，直接进入 Step 4。

## Step 4：攻击性质询（3 轮）

### 铁律

1. **必须引用原文** — 指出具体 session 日期 + 用户原话 + AI 回应
2. **必须挑战假设** — 不问"你怎么看"，问"证据在哪"
3. **禁止废话** — 不问感受，只问逻辑

### 提问武器库

- 「在 [日期] 的会话中，你问 AI '[原话]'。你凭什么认为 AI 能代表真实用户？数据在哪？」
- 「你直接用了 AI 推荐的 [X]，是因为最适合，还是因为给代码最快？」
- 「从 [A] 到 [B]，中间的推导过程呢？补上。」
- 「你说你懂了 [X]，不看 AI 代码，你能从零说出思路吗？」
- 「这个结论是你从数据中发现的，还是 AI 说的你就信了？」
- 「AI 给了你 [X] 方案，你验证过它的正确性吗？还是直接 copy-paste 了？」
- 「你用了 AI 第一个建议的 [方案]。你考虑过替代方案吗？还是被第一印象锚定了？」

### 流程

每轮：
1. 提出 1-2 个攻击性问题（必须有证据）
2. **使用 AskUserQuestion 收集结构化回复**（证据 + 提问写入 `question` 文本，选项用于分类回复）：

```
AskUserQuestion({
  questions: [{
    question: "在 [日期] 的会话中，[证据描述 + 攻击性提问]",
    header: "质询RN",  // N = 当前轮次
    options: [
      { label: "我有证据反驳", description: "我当时做了对比/验证，可以具体说明" },
      { label: "确实没深想", description: "承认这个点没考虑周全" },
      { label: "部分认同", description: "有些方面做了验证，有些确实漏了" }
    ],
    multiSelect: false
  }]
})
```

   如果一轮有 2 个问题，使用 `questions` 数组一次发送（最多 4 个）。

3. 根据用户选择分类：
   - 选「我有证据反驳」→ 追问让其补充证据（用普通文本追问或再次 AskUserQuestion）→ 证据充分记录「已澄清」
   - 选「确实没深想」→ 记录「认知缺陷」→ 进入追问
   - 选「部分认同」→ 记录「部分澄清」→ 追问未覆盖的部分
   - 选「Other」自由输入 → AI 判断分类（有理有据→已澄清，否则→认知缺陷）

> **Fallback**：若 AskUserQuestion 工具不可用，退回纯文本提问 + 等待自由文本回复的方式。

## Step 5：触发条件提炼 (Trigger Distillation)

> 把质询中暴露的隐性知识，当场压成结构化的 Gene 触发条件。不可跳过。

### 前置条件

Step 4 已完成，已产出「思维尸检」初稿和「行为纠偏指南」初稿。

### 额外弹药来源

如果本次复盘执行了 Gene 验证（阶段 A.0），以下验证发现也作为 Step 5 的输入：
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
     b. 使用 AskUserQuestion 回显确认：
        ```
        AskUserQuestion({
          questions: [{
            question: "我理解的是：\nIF [伪代码条件] THEN [做法]\nSKIP IF [伪代码跳过条件]\n对吗？",
            header: "确认规则",
            options: [
              { label: "对，就这样", description: "确认，暂存为 Gene 候选" },
              { label: "需要修改", description: "大方向对但细节要调整，让我补充" }
            ],
            multiSelect: false
          }]
        })
        ```

  3. 用户选「对，就这样」→ 暂存为 Gene 候选（status = 待Gene化）
     用户选「需要修改」→ 用户补充修正 → 按修正后版本暂存
     用户选「Other」→ 自由输入修正内容 → Agent 重新转译并再次确认

  特殊情况处理：

  - 用户说「说不清楚」
    → 使用 AskUserQuestion 提供候选 trigger：
    ```
    AskUserQuestion({
      questions: [{
        question: "你说不太清楚触发条件，我基于证据给你 2 个候选，选一个最接近的：",
        header: "触发条件",
        options: [
          { label: "候选 A", description: "IF [基于 facet 证据的条件A] THEN [做法A]" },
          { label: "候选 B", description: "IF [基于 facet 证据的条件B] THEN [做法B]" }
        ],
        multiSelect: false
      }]
    })
    ```
    → 选中的暂存为 Gene 候选
    → 选「Other」→ 用户自由描述，Agent 转译

  - 用户说「这个不需要规则化」
    → 使用 AskUserQuestion 追问：
    ```
    AskUserQuestion({
      questions: [{
        question: "你说这个不需要规则化。那你怎么保证下次不犯？",
        header: "规则化",
        options: [
          { label: "我有替代方案", description: "我有其他方式确保不再犯，让我说明" },
          { label: "确实说不清", description: "标记为待观察，下次复盘再验证" },
          { label: "这本来就不是问题", description: "我不认为这是缺陷，让我论证" }
        ],
        multiSelect: false
      }]
    })
    ```
    → 选「我有替代方案」或「这本来就不是问题」→ 用户补充论证 → 合理则记录「已澄清，不 Gene 化」，附用户论证
    → 选「确实说不清」→ 标记「待观察」，下次复盘再验证
    → 选「Other」→ 自由输入，AI 判断分类
```

## Step 6：学习路径推荐（可选）

> 在 Step 5 完成后，基于质询中暴露的认知缺陷，推荐具体学习方向。

```
IF 思维尸检中存在「认知缺陷」（severity = 高 或 中）:
  FOR each 认知缺陷:
    1. 诊断知识缺口类型：
       - 领域知识缺口（如：不了解某技术原理）
       - 方法论缺口（如：不会做竞品分析）
       - 工具使用缺口（如：不熟悉某 API 用法）
    2. 推荐学习路径（1-2 条，必须具体）：
       - 关键词：用于搜索的精确搜索词
       - 学习形式：文档/教程/实践项目/开源代码阅读
       - 预期投入：30min / 2hr / 1天
       - 验收标准：学完后能做到什么
    3. 使用 AskUserQuestion 收集用户决策：

       单个认知缺陷时：
       ```
       AskUserQuestion({
         questions: [{
           question: "检测到认知缺陷：[描述]。推荐学习方向：[关键词]（[形式]，约[投入时间]）。要加入行动计划吗？",
           header: "学习路径",
           options: [
             { label: "加入计划", description: "追加到报告「下一步行动」" },
             { label: "先跳过", description: "知道了但暂时不加入" },
             { label: "换个方向", description: "我觉得应该学别的，让我说" }
           ],
           multiSelect: false
         }]
       })
       ```

       多个认知缺陷时，用 multiSelect 一次问：
       ```
       AskUserQuestion({
         questions: [{
           question: "以下学习方向，哪些你想加入行动计划？",
           header: "学习路径",
           options: [
             { label: "[缺陷1] 学习方向", description: "[关键词]，[形式]，约[投入]" },
             { label: "[缺陷2] 学习方向", description: "[关键词]，[形式]，约[投入]" },
             { label: "[缺陷3] 学习方向", description: "[关键词]，[形式]，约[投入]" }
           ],
           multiSelect: true
         }]
       })
       ```

       - 选中的 → 追加到报告「下一步行动」
       - 未选中的 → 不追加
       - 选「换个方向」或「Other」→ 用户说明替代方向，Agent 评估后追加

IF 无显著认知缺陷:
  跳过此轮。
```

### 产出

追加到报告末尾（在「思维尸检」和「行为纠偏指南」之后）：

```markdown
### 提炼的 Gene 候选

| ID（建议） | 触发条件 | 跳过条件 | 来源 | 状态 |
|-----------|---------|---------|------|------|
| [kebab-case] | IF [伪代码] | IF [伪代码] | Step 4/5 / Gene验证 | 待 Gene 化 |
| — | 用户说不清 | — | Step 4/5 | 待观察 |
| — | — | — | Step 4/5 | 已澄清，不 Gene 化 |
```

### 与 Gene 化的衔接

Step 5 产出的 Gene 候选列表，在用户确认报告后，由 Gene 化流程统一处理：
- 「待 Gene 化」→ 进入 [gene-protocol.md](gene-protocol.md) 的 Step 6.1-6.5
- 「待观察」→ 记录到 evolution.jsonl（event: "pending_observation"），不写入 genes.json
- 「已澄清」→ 不做任何处理

## Step 7：输出 — 追加到报告末尾

质询完成后追加：

    ### 思维尸检
    - **本项目最大认知缺陷**：[描述 + 证据]
    - **触发场景**：[什么时候容易犯]
    - **严重程度**：高/中/低

    ### 行为纠偏指南
    对每个缺陷：
    1. **强制约束**：下一项目必须遵守的规则
    2. **检查点**：怎么判断自己没犯
    3. **触发器**：什么信号提醒你正在犯

    ### 提炼的 Gene 候选
    （由 Step 5 产出，格式见上方 Step 5 section）

    ### 学习路径推荐
    （由 Step 6 产出，仅当存在认知缺陷时）

    | 缺陷 | 类型 | 学习关键词 | 形式 | 投入 | 验收标准 |
    |------|------|-----------|------|------|---------|

## 特殊情况

- 全部澄清 → 「本轮无显著认知缺陷，建议日常使用 /feynman 保持自检」
- facet 中 ai_collab 全空 → 基于 friction + outcome 推断协作问题
- 语气可以尖锐，但必须有据，不能无端指控
