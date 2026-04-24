# 未来回报率估计：方法改进计划

## Context

当前 `wealth-model.js:32-33` 把 Lakeville 和 Lake Grande 的 `annualGrowth` 硬编码为 2%，作为压力测试的保守下限。用户想保留这个"给定收益率看结果"的能力，同时想要：

1. **一个区间扫描**：让收益率在一个范围内变化，看 wealth 结果如何变化，找到 buy vs rent 的 break-even。
2. **一个价值投资的"底"**：用租金收益率反推房产合理价值，作为现价是否值得买入的参考。
3. **修正系统性偏差**：当前模型完全没算 99 年地契的 lease decay（Lakeville TOP 2017、Lake Grande TOP 2019），是系统性偏乐观。
4. **单套挂牌价的公允性判断**：给定一个 listing，判断要价是否合理 —— 在已知信息不全（朝向/楼层未必有）的前提下降级为区间而非点估计。

### 已排除的方向（探讨后确认不做）

- **Bayesian 收缩到 URA PPI**：URA 全量 PPI 混合 30 年老盘和新盘、1b-5b 全户型、各价位段，与 2b2b 新 99 年 condo 不同质。且 `w` 权重的选择无非任意非任意的依据 —— 两个任意叠加比直接用本地 CAGR + 置信区间更糟。
- **同类 cohort 锚点**：cohort 边界（OCR? Lakeside only? 再按年代/户型细分?）都是主观判断，样本选择偏差无法消除。
- **延长历史（加回 New Sale）**：用户买二手房，未来回报的参照系是二手市场，不是开发商首发价。一手市场价格机制（early-bird 折扣、付款时间差）与二手脱节。
- **ARIMA / 时间序列预测模型**：样本量（160-190 笔交易，5-8 年）远不足以支撑。过拟合必然大于信号。
- **宏观回归（利率/人口/GDP → 房价）**：自由度问题。

## Scope

仅改动以下文件 / 新增文件：

- `wealth-model.js` —— 扩展为支持区间扫描、lease decay 系数。
- `analyze.py` —— 新增租金收益率时序计算、隐含公允价计算。
- `build_dashboard_data.py` —— 聚合新指标到 dashboard payload。
- `index.html` —— 新增一个顶级 tab **S11 · 决策**，内部上下三个区块：收益率扫描、租金收益率底、Listing 估价（不再拆成多 tab）。
- 新建 `listing_valuation.py` —— Model B 单套定价，独立工具。

## 四个改动

### 1. Lease decay 修正（结构性偏差）

**背景**：99 年地契剩余年限减少必然导致价格折扣。Bala's table 是业界标准曲线。Lakeville TOP 2017（购买时剩余 ~76 年），Lake Grande TOP 2019（购买时剩余 ~78 年）。持有 4 年剩余年限分别到 72 年、74 年，Bala 系数从 0.925 降到约 0.910，年化约 -0.4%。

**做法**：
- 在 `wealth-model.js` 加常量 `BALA_TABLE`（按剩余年限给系数，99/95/90/85/80/75/70/65 年常用档位线性插值）。
- 新增 `projectMeta.leaseStart`（Lakeville 2014、Lake Grande 2015，取发展商获地年份）和 `leaseYears: 99`。
- 修改 `wealth-model.js:448` 的未来价格计算：
  ```
  futurePrice = transaction.price
              * (1 + propertyGrowthRate)^year
              * balaAdjustment(remainingYearsAtT) / balaAdjustment(remainingYearsAt0)
  ```
- 在 `DEFAULT_ASSUMPTIONS` 加 `applyLeaseDecay: true` 开关，默认开启；用户也可关掉做对比。

### 2. 收益率情景扫描（决策鲁棒性）

**背景**：75% LTV、4 年窗口的决策对收益率分布尾部敏感。单点估计不够。

**做法**：
- `wealth-model.js` 新增 `sweepScenarios(planKey, { minRate, maxRate, step, ...overrides })` 函数：
  - 输入收益率区间（默认 `-0.02` 到 `0.06`，步长 `0.005`）。
  - 对每个收益率，复用现有 `simulateScenario()` 跑全部买 / 租场景。
  - 输出 `[{ growthRate, scenarioResults: { A: {totalWealth, totalCagr, ...}, B: ..., F: ... } }, ...]`。
- `build_dashboard_data.py` 把 sweep 结果写入 `dashboard_data.json` 下的 `sensitivity` 键。
- `index.html` 在 **S11 · 决策** tab 的「区块 1」呈现：
  - 主图：wealth 终值 vs `propertyGrowthRate` 折线图，每条买入方案一条线，对比租房基线。交叉点标注"break-even 收益率"。
  - 副图：propertyEquity、totalUpfront、avgInvestableCash 随收益率的变化。
  - 保留现有"单点 2%"的视图（S10）不动 —— 给定收益率看结果的能力完整保留。

### 3. 租金收益率作价值投资底（Gordon growth 反推隐含价值）

**背景**：长期房价 ≈ 租金现金流折现。repo 里 `data/ura/rental_median.json` 已有 Lakeville、Lake Grande 按季度 psf 租金中位数。用户要的"价值投资的底"就是从这里来。

**做法**：
- `analyze.py` 新增 `compute_rental_yield_series(project_name)`：
  - 从 `rental_median.json` 拉出目标项目的 psf 月租时序。
  - 与本地交易 CSV 的 psf 售价时序对齐（按季度聚合）。
  - 算 gross yield = `psf_rent_annual / psf_sale`。
  - 输出每季度 gross yield，历史均值、当前值、当前值 vs 历史均值的偏离。
- `analyze.py` 新增 `implied_fair_psf(project_name, required_yield, g)`：
  - Gordon growth model 反推：`psf_fair = psf_rent_annual / (required_yield - g)`。
  - 输入参数：买家要求的净收益率（扣物业税/管理费/空置后，默认 3.5%）、长期租金增长率 g（默认 1.5%）。
  - 输出不同参数组合下的 fair psf 矩阵；并对比当前市场 psf，给出"折价/溢价 %"。
- 在 **S11 · 决策** tab 的「区块 2」呈现：
  - 主图：gross yield 时序折线（Lakeville 2b2b、Lake Grande 2b2b 各一条），叠加历史均值线。
  - 副图：当前 psf vs 隐含 fair psf 矩阵（行 = required yield，列 = g）热力图。用户能清楚看到"在什么假设下现价是合理的"。
  - **不把这个用作 wealth-model 的输入**。作为独立的估值参考信号，避免两个任意假设叠加。

### 4. Listing 公允价计算器（Model B，独立工具）

**背景**：Hedonic 回归需要朝向/楼层，用户实际很可能拿不到。做法是**降级**：有什么信息用什么，缺失信息反映为区间宽度。

**做法**：
- 新建 `listing_valuation.py`（CLI 脚本）：
  - 输入：`--project lakegrande --sqft 800 --price 1500000 [--floor mid] [--facing south]`
  - 步骤：
    1. 从 `data/lakegrande_transactions.csv` 取近 12 个月同项目成交。
    2. 按户型 bucket（用 repo 已有的 `data/layout_mapping/lakegrande_transaction_layout_map.csv`）过滤到同户型（例如 800 sqft 落入 2b2b 700-849 bucket）。
    3. 时间归一：把每笔历史成交的 psf 用本地 CAGR 折算到"今天"。
    4. 若用户提供 floor，按 low/mid/high 切子集；若提供 facing，按朝向切子集；缺失则用整个 bucket。
    5. 输出 adjusted psf 的 P10 / P25 / P50 / P75 / P90。
    6. 用户目标房 psf = price / sqft，报告它落在哪个分位数；给出"相对 P50 折价/溢价 %"。
  - 不用回归、不依赖"足够样本"假设。区间宽度自动反映不确定性 —— 信息越少区间越宽。
- 在 **S11 · 决策** tab 的「区块 3」呈现：输入框（项目 / sqft / 挂牌价 / 可选 floor / 可选 facing）+ 输出区间（P10/P25/P50/P75/P90、目标 psf 分位、折溢价 %）。首期可只出 CLI，再迁 UI；或直接前端算。

## 执行顺序与建议

1. **先做 1（lease decay）+ 2（sweep）**：最直接、只改 wealth 主线、给用户带来最多决策信息；不依赖外部判断。
2. **再做 3（rental yield）**：数据就位，纯分析工作，结果作为独立视图。
3. **最后做 4（listing）**：独立模块，可以等用户真的遇到具体挂牌时再补。

## 关键文件路径

| 改动 | 文件 | 参考行 |
|------|------|--------|
| Lease decay | `wealth-model.js` | `:32-33` (assumptions)、`:180-182` (getProjectGrowthRate)、`:448` (future price calc) |
| Sweep | `wealth-model.js` 新函数；`build_dashboard_data.py`；`index.html` 新 tab | - |
| Rental yield | `analyze.py:175-316`（既有 CAGR 逻辑）；`data/ura/rental_median.json` | - |
| Listing | `listing_valuation.py` (新)；`data/layout_mapping/*_transaction_layout_map.csv` | - |

## 验证方式

- **Lease decay**：关掉和打开 `applyLeaseDecay` 对同一收益率跑 wealth，差值应年化 ~0.4%。对 4 年仿真，totalWealth 差约 1-2 万新元。
- **Sensitivity sweep**：人工抽一个收益率（例如 3%），对比 `sweepScenarios(..., { fixed: 0.03 })` 和直接用 3% 跑 `buildScenario` 的输出，应完全一致。浏览器打开 dashboard 新 tab，检查曲线平滑、buy/rent 交叉点标注正确。
- **Rental yield**：手工从 `rental_median.json` 挑一条记录 + 同季度一笔成交，笔算 gross yield，对比脚本输出。Gordon fair psf 用 `rent=4 psf/月、required_yield=0.04、g=0.01` 应得 `fair_psf = 4*12/(0.04-0.01) = 1600`，脚本输出应一致。
- **Listing valuation**：挑一笔已知真实成交，输入 sqft / price，P50 附近应落在 ±5% 内；拿一个明显高出近期成交 20% 的假 listing，应报告"溢价 15-25%"。
- **既有测试**：`tests/wealth-model.spec.js` 和 `tests/dashboard.render.spec.js` 须继续全绿；lease decay 打开对既有断言（CPF / 贷款 / BSD）无影响。
