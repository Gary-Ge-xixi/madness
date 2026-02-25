# 大项目策略（>30 session）

当 session 数量超过 30 个时，采用以下策略避免上下文溢出：

## 批次处理

- 将 session 按时间分批，每批 10-15 个
- 每批独立提取 facet + 聚合分析
- 批次之间传递聚合摘要（不传原始数据）

## 摘要传递

- 每批次产出结构化摘要 JSON（含 goal_category 分布、friction Top5、loop_rate）
- 后续批次基于前序摘要做增量分析
- 最终聚合时合并所有批次摘要

## 中间持久化

- 每个 session 的 facet 即时缓存（validate_facet.py cache）
- 聚合统计结果持久化到 `.retro/aggregation_cache.json`
- 子智能体崩溃时可从缓存恢复，无需重新提取
