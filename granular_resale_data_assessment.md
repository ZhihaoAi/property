# 更细粒度二手房成交数据评估

参考 [gpt_data_suggestion.md](/Users/zhihao.ai/projects/property/gpt_data_suggestion.md) 的建议，当前结论可以拆成两层：

## 1. 现在就能稳定拿到的更细字段

基于当前仓库里已经缓存的 `propertyforsale.com.sg` 原始页面，不需要新增外部抓取，就能从交易表里稳定解析出这些字段：

- `project_name`
- `sale_period`
- `street_name`
- `district`
- `market_segment`
- `tenure`
- `lease_start`（仅 leasehold 项目）
- `floor_range`
- `floor_area_sqft`
- `psf_sgd`
- `sale_price_sgd`

这比当前仓库里大多数 CSV 只保留 `date/sqft/psf/price` 更细一层，已经足够支持：

- 分楼层区间分析
- 分区域 / segment 分析
- leasehold vs freehold 对比
- 后续按面积 + 楼层做户型映射

本次新增脚本 [extract_resale_detailed.py](/Users/zhihao.ai/projects/property/extract_resale_detailed.py) 会把这些字段导出为详细版 CSV。

## 2. 还拿不到的字段

仅靠当前 `propertyforsale` / URA caveat 同源交易表，仍然拿不到：

- `unit_no`
- `stack`
- `bedrooms`
- `bathrooms`

也就是说，当前公开成交表本身仍然不够直接标出 `2b1b / 2b2b / 3b2b`。

## 3. 已验证可行的补数路径

我额外核实了 99.co 当前公开项目页，确认它通常同时提供两类信息：

1. `Sale Transactions`
   - 可见更细成交字段，如 `unit_no`、`floor`、`beds`、`area`、`sold_month`、`price`
2. `Floor Plans`
   - 可见 `bedrooms`、`bathrooms`、`sqft`

这意味着可行的半自动流程是：

1. 用成交表保留真实成交记录
2. 用 99.co / 楼书 / 户型页补 `bedrooms`、`bathrooms`
3. 按 `project + area + bedrooms` 做主匹配
4. 若同面积存在多个 bath 版本，再用 `unit_no / floor / stack` 缩小范围
5. 仍无法唯一匹配的记录标记为 `ambiguous`

## 4. 最实际的判断

结论不是“换个成交网站就能直接拿到完整单套成交明细”，而是：

- `更细的成交字段`：现在就能拿到一部分，已经可以落地
- `2b1b / 2b2b / 3b2b`：可以做，但要走“成交表 + 户型表”的拼接流程
- `bathroom`：仍然不是官方成交表直出字段，必须通过户型库或楼书映射

## 5. 当前产物

- 详细抽取脚本：[extract_resale_detailed.py](/Users/zhihao.ai/projects/property/extract_resale_detailed.py)
- 输出目录：[data/detailed](/Users/zhihao.ai/projects/property/data/detailed)
- 汇总文件：[data/resale_transactions_detailed.csv](/Users/zhihao.ai/projects/property/data/resale_transactions_detailed.csv)
