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

  **必须引用具体 session 原文作为证据。不允许凭「感觉」判断。**

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
  | 已遵守 | partially_achieved | weak_validate | +0.02 | 有帮助但不充分 |
  | 已遵守 | not_achieved | ineffective | -0.15 | 规则本身可能有问题 |
  | 部分遵守 | fully_achieved | partial_validate | +0.02 | 部分有效 |
  | 部分遵守 | not_achieved | inconclusive | 不变 | 无法归因 |
  | 未遵守 | fully_achieved | over_scoped | -0.10 | trigger 过宽需收窄 |
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
      {"event":"deprecate","asset_id":"...","reason":"confidence dropped below 0.50","last_confidence":...,"trigger_result":"..."}

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
