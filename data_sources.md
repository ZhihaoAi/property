# 数据源说明

本文档说明当前 repo 默认口径下的数据源分层、角色和差异。

当前默认规则已经切换为：

- 默认只看 `resale-only`
- `propertyforsale resale` 优先
- `propertyforsale` 本地拿不到时，回退到 `URA resale`
- `SRX` 不再作为默认主源，只保留历史备份

## 当前快照

以下状态基于当前仓库内产物：

- `data/dashboard_data.json` 生成时间：`2026-03-28T18:19:25`
- `data/srx_project_registry.json` 生成时间：`2026-03-28T18:16:28`
- 默认本地交易项目数：`47`
- 默认 `propertyforsale resale` 主源项目数：`40`
- 默认 `URA resale fallback` 项目数：`7`
- 默认 `SRX` 主源项目数：`0`
- 仍保留 `SRX` 备份窗口的项目数：`17`
- 本地 `URA` 浏览项目数：`3430`
- 已和默认本地项目自动匹配上的 `URA` 项目数：`43`

当前不在默认集里的项目：

- `the_botany_at_dairy_farm`
- `the_myst`
- `the_sen`

原因是当前本地缓存里没有可用于默认口径的 resale 数据。

## 一览表

| 类型 | 来源 | 当前角色 | 主要落盘位置 | 主要脚本 | 关键差异 |
| --- | --- | --- | --- | --- | --- |
| 外部原始源 | `propertyforsale.com.sg` | 默认 resale 主交易源 | `data/*_transactions.csv`、`data/propertyforsale_html/*` | `scripts/fetch_missing_propertyforsale_transactions.py` | 只保留显式标记为 `Resale` 的成交 |
| 外部原始源 | `URA Data Service` | 默认 resale fallback | `data/*_transactions.csv`、`data/ura/*` | `scripts/fetch_missing_propertyforsale_transactions.py`、`scripts/fetch_ura_private_residential.py` | 只取 `typeOfSale = 转售`，并在 propertyforsale resale 不可用时顶上 |
| 外部原始源 | `SRX last-transacted-prices` | 历史备份源 | `data/srx/*` | `scripts/fetch_missing_srx_transactions.cjs` | 不再作为默认主源，只留作备查 |
| 外部原始源 | developer brochure / floor-plan + `99.co` 辅助片段 | 户型证据源 | `data/poc_layout/layout_reference_poc.csv`、`data/layout_mapping/*` | `scripts/build_layout_mappings.py` | brochure / floor-plan 优先，`99.co` 仅作辅助线索；正式输出统一写入 `data/layout_mapping/*` |
| 本地派生产物 | 统一 dashboard 数据 | 前端唯一直接读取的数据 | `data/dashboard_data.json`、`data/dashboard_data.js` | `build_dashboard_data.py` | 聚合了默认 resale CSV、分析结果、layout mapping、URA 浏览数据 |
| 本地派生产物 | 年度统计与 CAGR | 分析中间层 | `data/appreciation_analysis.json` | `analyze.py` | 基于默认 resale CSV 计算 |
| 本地派生产物 | 详细 resale 明细 | 辅助分析层 | `data/detailed/*`、`data/resale_transactions_detailed.csv` | `extract_resale_detailed.py` | 只覆盖部分项目，且来自 propertyforsale 原始缓存页 |

## 默认主源规则

### 1. propertyforsale resale

这是当前 repo 的默认主交易源。

- 默认只抽 `Type of Sale = Resale`
- 不再默认把 `New Sale / Sub Sale` 写进 `data/*_transactions.csv`
- markdown cache 项目优先复用仓库内已有的 resale 备份
- HTML cache 项目优先复用 `data/propertyforsale_html/*`
- 若成功拿到 resale 行，就写回 `data/<slug>_transactions.csv`

相关脚本：

- `scripts/fetch_missing_propertyforsale_transactions.py`

当前角色：

- 40 个项目的默认主源
- 前端默认榜单、主源 CAGR、面积近似 PK 都优先用这套数据

### 2. URA resale fallback

这是当前 repo 默认口径下的官方 fallback。

只有在下列情况才启用：

- `propertyforsale` 本地缓存不可用
- `propertyforsale` 页面被验证码拦住
- `propertyforsale` 本地缓存里没有 resale 行

使用规则：

- 只取 `typeOfSale = 3`
- 即只保留转售 / resale
- 面积从 `sqm` 转成 `sqft`
- `psf` 由 `price / sqft` 推导

当前使用 URA resale fallback 的 7 个项目：

- `hillion_residences`
- `midwood`
- `eight_riversuites`
- `the_tennery`
- `dairy_farm_residences`
- `le_quest`
- `daintree_residence`

相关脚本：

- `scripts/fetch_missing_propertyforsale_transactions.py`
- `scripts/fetch_ura_private_residential.py`
- `scripts/query_ura_project.py`

### 3. SRX last-transacted-prices

`SRX` 现在不是默认主源。

当前角色只剩两类：

- 历史窗口备份
- 人工排查时的参考数据

当前状态：

- 默认 `SRX` 主源项目数：`0`
- 仍保留 `SRX` 备份窗口的项目数：`17`

这些备份文件主要在：

- `data/srx/*`

要点：

- 默认 dashboard 不再依赖 `SRX` 当主口径
- 即使来源列里还会显示 `SRX`，那也只是 secondary source

### 4. 户型证据源

这不是成交主源，只是户型证据源。当前规则是 developer brochure / floor-plan 优先；`99.co` 和公开列表缓存只能作为辅助线索，不能单独覆盖 brochure 证据。

用途：

- 为 `Lakeville / Lake Grande` 的交易记录做 `bed/bath` 映射
- 支撑 `2b1b / 2b2b / 3b2b` 细户型口径

主要文件：

- `data/poc_layout/layout_reference_poc.csv`
- `data/layout_mapping/layout_reference_catalog.csv`
- `data/layout_mapping/*_transaction_layout_map.csv`

相关脚本：

- `scripts/build_layout_mappings.py`

## 本地文件分层

### A. 默认交易层

- `data/*_transactions.csv`
  - 默认主交易入口
  - 当前全都是默认 `resale-only` CSV
  - 不再默认混入 `New Sale / Sub Sale`

### B. 原始/备份层

- `data/propertyforsale_html/*`
  - propertyforsale HTML 缓存
- `data/propertyforsale_resale_backup/*`
  - 历史 resale 备份
- `data/propertyforsale_primary_backup/*`
  - 刷新脚本在本地覆盖主 CSV 前生成的备份目录（本地保留，默认不入库）
- `data/srx/*`
  - 历史 SRX 备份窗口
- `data/ura/*`
  - URA 成交 / 租中位 / 租约缓存

### C. 交易细化层

- `data/detailed/*`
  - richer resale 明细
- `data/resale_transactions_detailed.csv`
  - 详细 resale 合并表

### D. 户型映射层

- `data/poc_layout/layout_reference_poc.csv`
  - 正式 mapping 仍在使用的输入证据
- `data/layout_mapping/*`
  - 当前正式 mapping 输出

### E. 聚合分析层

- `data/appreciation_analysis.json`
  - 年度统计、CAGR
- `data/dashboard_data.json`
- `data/dashboard_data.js`
  - 前端统一消费的数据

## 当前数据流

### 默认交易主线

1. 优先从 `propertyforsale` 本地缓存提取 `Resale`
2. 如果拿不到，则尝试本地 `URA` 的 resale
3. 写入 `data/*_transactions.csv`
4. 运行 `analyze.py` 生成 `data/appreciation_analysis.json`
5. 运行 `scripts/build_layout_mappings.py` 重建户型 mapping
6. 运行 `build_dashboard_data.py` 生成 `data/dashboard_data.json/js`
7. `index.html` 只直接消费 `dashboard_data.json/js`

### 官方补充线

1. 从 `URA Data Service` 拉取成交、租金中位数、租约
2. 写入 `data/ura/*`
3. `build_dashboard_data.py` 把 `URA` 浏览数据拼进统一 payload
4. 前端 `URA 项目页` 展示并和本地主源做交叉对比

### 户型映射线

1. 用 developer brochure / floor-plan 验证面积到户型的证据表，`99.co` 只补充辅助线索
2. 输出正式 `data/layout_mapping/*`
3. `build_dashboard_data.py` 把 mapping 结果拼进 dashboard payload
4. 前端展示 `细户型 CAGR` 和 `面积近似 CAGR`

## 结论

当前 repo 的默认数据源策略可以概括为：

- `propertyforsale resale`：默认主交易源
- `URA resale`：默认 fallback
- `SRX`：历史备份，不再是默认主源
- developer brochure / floor-plan：户型主证据源
- `99.co`：户型辅助线索

前端真正直接读取的不是这些原始源，而是统一产物：

- `data/dashboard_data.json`
- `data/dashboard_data.js`

## 备注

- 如果后续需要 `New Sale` 或 `Sub Sale`，应该作为显式扩展需求单独做，不应再默认混入当前主 CSV
- 当前默认集从原来的 50 个项目收敛到 47 个项目，是因为默认口径改成了严格的 `resale-only`
