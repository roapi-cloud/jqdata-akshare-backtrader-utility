# 任务 07：年度 / 状态 / 风格切片框架

## 目标

为策略稳定性分析设计可复用的切片分解框架,确保任何策略都能回答：
- 它赚的是哪几年？
- 哪种市场环境？
- 哪类风格暴露？

本框架直接服务于 `33_master_validation_pipeline.md` 和 `38_strategy_admission_oos.md`。

---

## 一、切片强制性与适用范围

### 1.1 必跑切片（所有策略）

| 切片类型 | 适用策略 | 强制等级 | 理由 |
|---------|---------|---------|------|
| 年度收益切片 | 所有 | 强制 | 识别"只赚某几年"的异常 |
| 年度回撤切片 | 所有 | 强制 | 评估历史最差场景 |
| 样本内/外对照 | 所有 | 强制 | 验证过拟合风险 |
| 最近1-2年表现 | 所有 | 强制 | 防止旧样本幻觉 |

### 1.2 主仓策略必跑切片

| 切片类型 | 适用策略 | 强制等级 | 理由 |
|---------|---------|---------|------|
| 市场状态切片 | 股票低频主仓、ETF主仓 | 强制 | 评估不同市场环境适应性 |
| 基本风格暴露 | 主仓候选 | 强制 | 识别风格依赖风险 |
| 压力成本对照 | 主仓候选 | 强制 | 验证成本敏感性 |

### 1.3 微盘策略必跑切片

| 切片类型 | 适用策略 | 强制等级 | 理由 |
|---------|---------|---------|------|
| 小盘暴露切片 | 微盘/小市值策略 | 强制 | 识别纯小盘效应 |
| 流动性切片 | 微盘策略 | 强制 | 评估流动性风险 |
| 换手率分布 | 高频策略 | 强制 | 识别交易成本风险 |

### 1.4 可选切片（按需）

| 切片类型 | 适用场景 | 触发条件 |
|---------|---------|---------|
| 行业暴露切片 | 行业轮动策略、怀疑行业集中 | 行业集中度>40% |
| 因子动态切片 | 多因子策略 | 因子数量≥3 |
| 极端压力场景 | 风险事件策略 | 主观判断需要 |
| 宏观周期切片 | 宏观驱动策略 | 策略说明中涉及宏观因子 |

---

## 二、年度切片定义

### 2.1 年度收益切片

**目的**：识别策略是否只在少数年份有效。

**核心指标**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| year | int | 年份 |
| annual_return | float | 年度收益率 |
| annual_alpha | float | 年度Alpha |
| excess_return | float | 年度超额收益 |
| trading_days | int | 实际交易天数 |
| position_days | int | 有持仓天数 |
| win_rate | float | 年度胜率 |
| sharpe | float | 年度Sharpe |
| max_dd | float | 年度最大回撤 |
| turnover | float | 年度换手率 |
| net_profit | float | 年度净利润 |
| gross_profit | float | 年度总盈利 |
| gross_loss | float | 年度总亏损 |
| profit_factor | float | 盈亏比 |

**异常识别规则**：

| 异常类型 | 判定条件 | 处理建议 |
|---------|---------|---------|
| 单年依赖 | 单年贡献>总收益50% | 强制降档至D档或E档 |
| 集中依赖 | 连续2年贡献>总收益70% | 进入OOS观察，重点监控样本外 |
| 近期失效 | 最近2年年度Alpha<0 | 强制降档，需重新验证 |
| 高波动 | 年度收益标准差>年度均值 | 标记为高波动策略 |
| 负偏度 | 负收益年份占比>40% | 标记为下行风险高 |

**输出模板**：

```csv
year,annual_return,annual_alpha,excess_return,trading_days,position_days,win_rate,sharpe,max_dd,turnover,net_profit,gross_profit,gross_loss,profit_factor
2018,-0.15,-0.08,-0.05,244,180,0.42,-0.45,-0.25,12.5,-150000,200000,-350000,0.57
2019,0.35,0.12,0.08,244,220,0.55,1.20,-0.10,8.3,350000,500000,-150000,3.33
2020,0.28,0.18,0.15,244,200,0.52,0.95,-0.12,9.1,280000,400000,-120000,3.33
...
```

### 2.2 年度回撤切片

**目的**：识别策略历史最差场景，评估修复能力。

**核心指标**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| year | int | 年份 |
| max_dd | float | 年度最大回撤 |
| max_dd_start | date | 回撤开始日期 |
| max_dd_end | date | 回撤结束日期 |
| dd_duration | int | 回撤持续天数 |
| recovery_days | int | 修复天数（如未修复填-1） |
| current_dd | float | 年末剩余回撤 |
| dd_count | int | 年度回撤次数（>5%回撤） |
| avg_dd_duration | float | 平均回撤持续天数 |

**异常识别规则**：

| 异常类型 | 判定条件 | 处理建议 |
|---------|---------|---------|
| 极端回撤 | 单年最大回撤>40% | 强制进入A档淘汰审查 |
| 长期无法修复 | 回撤>30%且持续>180天 | 标记为修复能力差 |
| 连续回撤 | 连续3年最大回撤>20% | 强制要求风险控制增强 |
| 年末大回撤 | 年末回撤>15% | 提示进入下一年风险 |

---

## 三、市场状态切片定义

### 3.1 状态定义（复用03_state_router）

**状态分类**：

| 状态编号 | 状态名称 | 广度阈值 | 情绪阈值 | 标准仓位 |
|---------|---------|---------|---------|---------|
| 0 | 极弱停手 | <15 | <30 | 0% |
| 1 | 底部防守 | 15-25 | 30-50 | 30% |
| 2 | 震荡平衡 | 25-35 | 50-80 | 50% |
| 3 | 趋势正常 | 35-40 | ≥80 | 70% |
| 4 | 强趋势 | ≥40 | ≥80 | 100% |

**计算方法**：
- 广度 = 沪深300成分股站上MA20的比例
- 情绪 = 涨停家数
- 每日根据双指标落入的状态档位

**核心指标**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| state_id | int | 状态编号 |
| state_name | str | 状态名称 |
| total_days | int | 该状态总天数 |
| position_days | int | 有持仓天数 |
| total_return | float | 该状态累计收益 |
| total_alpha | float | 该状态累计Alpha |
| avg_return_per_day | float | 日均收益 |
| win_rate | float | 该状态胜率 |
| sharpe | float | 该状态Sharpe |
| max_dd | float | 该状态最大回撤 |
| contribution_pct | float | 该状态收益贡献占比 |
| expected_position | float | 理论仓位 |
| actual_avg_position | float | 实际平均仓位 |
| position_efficiency | float | 仓位效率=收益/仓位 |

**异常识别规则**：

| 异常类型 | 判定条件 | 处理建议 |
|---------|---------|---------|
| 单状态依赖 | 单状态贡献>总收益60% | 标记为市场环境依赖型，降档 |
| 防守期亏损 | 底部防守+极弱停手期Alpha<0 | 警示：需增强防守能力 |
| 震荡期失效 | 震荡平衡期Alpha显著<0 | 提示：可能不适合震荡市 |
| 趋势期跑输 | 趋势正常+强趋势Alpha<0 | 强制降档，主仓必须能捕获趋势 |

**输出模板**：

```csv
state_id,state_name,total_days,position_days,total_return,total_alpha,avg_return_per_day,win_rate,sharpe,max_dd,contribution_pct,expected_position,actual_avg_position,position_efficiency
0,极弱停手,45,0,0,0,0,0,0,0,0.00,0,0,0
1,底部防守,120,36,-0.05,-0.03,-0.0004,0.38,-0.30,-0.08,-0.05,30,28,-0.0018
2,震荡平衡,180,90,0.08,0.05,0.0004,0.52,0.45,-0.06,0.08,50,48,0.0017
3,趋势正常,245,171,0.25,0.15,0.0010,0.58,1.20,-0.10,0.50,70,65,0.0038
4,强趋势,120,120,0.35,0.18,0.0029,0.62,1.80,-0.08,0.47,100,95,0.0037
```

### 3.2 状态切片与主路由的关系

- 状态切片使用**历史回溯**方式计算，即根据历史数据反推每日应处状态
- 对于已接入主路由的策略，状态切片还应对比：
  - 理论仓位（状态路由建议） vs 实际仓位
  - 理论收益（完全遵守路由） vs 实际收益
  - 状态切换准确率

---

## 四、风格 / 暴露切片定义

### 4.1 基本风格因子

**强制覆盖的因子**（所有主仓策略）：

| 因子类别 | 因子名称 | 计算方法 | 数据来源 |
|---------|---------|---------|---------|
| 规模 | Size（市值） | log(总市值) | 行情数据 |
| 价值 | BP（账面市值比） | 净资产/总市值 | 财务数据 |
| 质量 | ROE | 净利润/净资产 | 财务数据 |
| 动量 | Momentum | 过去12个月收益（跳过最近1月） | 行情数据 |
| 波动率 | Volatility | 过去20日波动率 | 行情数据 |
| 流动性 | Liquidity | 过去20日平均成交额 | 行情数据 |

**扩展因子**（按策略类型选择）：

| 因子类别 | 适用策略 |
|---------|---------|
| 行业因子 | 行业轮动、怀疑行业集中 |
| Beta因子 | 指数增强、对冲策略 |
| 换手率因子 | 高频策略 |
| 北向资金因子 | 跟踪北向的策略 |
| 鳄鱼线因子 | 技术分析策略 |

### 4.2 风格暴露计算

**方法**：多因子回归

```
策略收益_t = α + β1*Size_t + β2*BP_t + β3*ROE_t + β4*Momentum_t + β5*Volatility_t + ε_t
```

**核心指标**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| factor_name | str | 因子名称 |
| factor_beta | float | 因子暴露系数 |
| factor_return | float | 因子收益贡献 |
| factor_contribution_pct | float | 因子贡献占比 |
| t_stat | float | t统计量 |
| p_value | float | p值 |
| significance | str | 显著性标记（***, **, *, 不显著） |

**异常识别规则**：

| 异常类型 | 判定条件 | 处理建议 |
|---------|---------|---------|
| 单因子依赖 | 单因子贡献>60% | 强制归因分析，可能仅为因子暴露 |
| 小盘暴露过大 | Size beta < -1.5且显著 | 微盘策略必须评估流动性风险 |
| 动量依赖 | Momentum beta > 2.0且显著 | 标记为动量策略，需监控动量崩塌 |
| 价值陷阱 | BP beta > 1.5但收益贡献为负 | 提示可能踩中价值陷阱 |
| 特异收益过低 | 特异收益占比<20% | 标记为纯因子策略，非真alpha |
| 显著因子过多 | 显著因子数>5且模型R²>0.8 | 策略可能过度拟合历史因子 |

**输出模板**：

```csv
factor_name,factor_beta,factor_return,factor_contribution_pct,t_stat,p_value,significance
Size,-1.23,0.08,0.25,-3.45,0.0006,***
BP,0.45,0.05,0.15,2.10,0.036,*
ROE,0.78,0.06,0.18,2.87,0.004,**
Momentum,1.92,0.12,0.36,4.21,0.00003,***
Volatility,-0.34,-0.02,-0.06,-1.12,0.263,不显著
Specific,-,0.03,0.12,-,-,-
```

### 4.3 小盘策略必查暴露

**适用**：微盘、小市值策略

**必查指标**：

| 指标 | 计算方法 | 异常阈值 |
|------|---------|---------|
| 平均市值 | 组合平均总市值 | <50亿触发流动性审查 |
| 市值分位数 | 组合市值在全市场分位 | <20%触发警示 |
| 流动性覆盖率 | 持仓<日均成交额*持仓天数 | <80%触发流动性风险 |
| 换手率冲击 | 模拟换手对价格的冲击 | >2%影响触发成本警示 |
| 极端事件影响 | 模拟跌停无法卖出比例 | >10%触发极端风险 |

---

## 五、综合切片结果表设计

### 5.1 主表：regime_slice_results.csv

**用途**：所有切片结果的汇总表，供统一报告引用。

**完整字段设计**：

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|---------|
| strategy_id | str | 策略标识 | 必填 |
| slice_type | str | 切片类型（year/state/style） | 必填 |
| slice_name | str | 切片名称（如2020/强趋势/Size） | 必填 |
| slice_id | int | 切片编号 | 必填 |
| total_return | float | 累计收益 | 年度/状态/风格通用 |
| total_alpha | float | 累计Alpha | 年度/状态/风格通用 |
| contribution_pct | float | 收益贡献占比 | 年度/状态/风格通用 |
| total_days | int | 总天数 | 年度/状态必填 |
| position_days | int | 有持仓天数 | 年度/状态必填 |
| win_rate | float | 胜率 | 年度/状态必填 |
| sharpe | float | Sharpe | 年度/状态必填 |
| max_dd | float | 最大回撤 | 年度/状态必填 |
| turnover | float | 换手率 | 年度必填 |
| recovery_days | int | 回撤修复天数 | 年度回撤切片 |
| factor_beta | float | 因子暴露系数 | 风格必填 |
| factor_contribution_pct | float | 因子贡献占比 | 风格必填 |
| t_stat | float | t统计量 | 风格必填 |
| significance | str | 显著性标记 | 风格必填 |
| expected_position | float | 理论仓位 | 状态必填 |
| actual_avg_position | float | 实际平均仓位 | 状态必填 |
| position_efficiency | float | 仓位效率 | 状态必填 |
| anomaly_flag | bool | 是否异常 | 必填 |
| anomaly_type | str | 异常类型（如有） | 可选 |
| review_action | str | 审查建议 | 可选 |

**示例数据**：

```csv
strategy_id,slice_type,slice_name,slice_id,total_return,total_alpha,contribution_pct,total_days,position_days,win_rate,sharpe,max_dd,turnover,recovery_days,factor_beta,factor_contribution_pct,t_stat,significance,expected_position,actual_avg_position,position_efficiency,anomaly_flag,anomaly_type,review_action
STRAT001,year,2018,2018,-0.15,-0.08,-0.20,244,180,0.42,-0.45,-0.25,12.5,180,,,,,,,,true,负收益年份占比高,监控
STRAT001,year,2019,2019,0.35,0.12,0.45,244,220,0.55,1.20,-0.10,8.3,45,,,,,,,,true,单年依赖,重点审查
STRAT001,state,强趋势,4,0.35,0.18,0.47,120,120,0.62,1.80,-0.08,,,,,,,100,95,0.0037,false,,
STRAT001,style,Momentum,-,0.12,-,0.36,,,,,,,,-,1.92,-,4.21,***,,,-,true,动量依赖,监控动量崩塌风险
```

### 5.2 辅助表：slice_anomaly_summary.csv

**用途**：汇总所有异常发现，供定档参考。

**字段设计**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| strategy_id | str | 策略标识 |
| anomaly_type | str | 异常类型 |
| slice_type | str | 切片类型 |
| slice_name | str | 切片名称 |
| severity | str | 严重程度（高/中/低） |
| impact_on_grade | str | 对定档的影响 |
| review_action | str | 审查建议 |
| is_resolved | bool | 是否已解决 |

---

## 六、与统一报告和定档的衔接

### 6.1 与33_master_validation_pipeline.md的衔接

**稳定性报告部分直接引用**：

```markdown
### B. 稳定性分解

#### B.1 年度分解
[引用 regime_slice_results.csv 中 slice_type='year' 的数据]

#### B.2 市场状态分解
[引用 regime_slice_results.csv 中 slice_type='state' 的数据]

#### B.3 风格归因
[引用 regime_slice_results.csv 中 slice_type='style' 的数据]

#### B.4 异常标记
[引用 slice_anomaly_summary.csv]
```

### 6.2 与38_strategy_admission_oos.md的衔接

**直接作为定档依据**：

| 异常类型 | 建议档位 | 说明 |
|---------|---------|------|
| 单年依赖 | D档或E档 | 进入OOS观察或淘汰 |
| 单状态依赖 | D档 | 标记为环境依赖型，OOS观察 |
| 小盘暴露过大 | B档或C档 | 根据流动性评估，可能只做过滤器 |
| 近期失效 | D档或E档 | 必须重新验证或淘汰 |
| 特异收益过低 | B档或C档 | 标记为因子策略，非真alpha |
| 无异常 | A档候选 | 继续评估其他指标 |

### 6.3 与后续任务的接口

**与任务08（样本外验证）的接口**：
- 年度切片中识别的"高依赖年份" → 样本外需重点监控这些年份的模式是否重现
- 风格切片中识别的"主导因子" → 样本外需监控该因子是否失效

**与任务09（稳定性压力测试）的接口**：
- 市场状态切片中的"弱势状态表现" → 压力测试需加重该状态
- 年度回撤切片中的"历史最大回撤" → 压力测试需超越该阈值

**与任务10（归因与报告）的接口**：
- 风格切片结果 → 直接进入归因报告
- 异常标记 → 直接写入报告警示部分

---

## 七、异常识别与解释框架

### 7.1 异常严重程度分级

| 级别 | 定义 | 典型表现 | 处理优先级 |
|------|------|---------|-----------|
| 高 | 可能导致策略不可用 | 单年依赖、极端回撤、主仓跑输趋势 | 立即处理 |
| 中 | 影响策略定位 | 单状态依赖、因子暴露过大、近期弱化 | 优先处理 |
| 低 | 提示性标记 | 负偏度、高波动、部分因子显著 | 监控观察 |

### 7.2 异常解释框架

**解释模板**：

```markdown
### 异常：[异常类型]

**发现位置**：[切片类型] - [切片名称]

**异常表现**：
- [具体数据，如：单年贡献45%收益]

**可能原因**：
1. [原因假设1]
2. [原因假设2]
3. [原因假设3]

**影响评估**：
- 对定档的影响：[高/中/低]
- 对样本外的影响：[具体说明]
- 对风险的影响：[具体说明]

**审查建议**：
- [建议动作1]
- [建议动作2]

**是否可接受**：
- [ ] 可接受（有合理解释）
- [ ] 需修正（有改进空间）
- [ ] 不可接受（致命缺陷）
```

### 7.3 异常处理流程

```text
切片分析完成 → 是否发现异常？
  → 否：正常进入定档
  → 是：严重程度判断
    → 高：立即进入异常审查 → 是否可接受？
      → 是：说明理由后继续
      → 否：降档或淘汰
    → 中：标记后进入定档 → 定档时考虑异常 → OOS观察？
      → 是：进入OOS池
      → 否：继续
    → 低：记录后继续
```

---

## 八、第一版最小实现建议

### 8.1 必须实现的切片

**第一版优先级排序**：

1. **年度收益切片**（必须）
   - 字段：year, annual_return, annual_alpha, contribution_pct, win_rate, sharpe, max_dd
   - 异常识别：单年依赖、集中依赖、近期失效

2. **年度回撤切片**（必须）
   - 字段：year, max_dd, max_dd_start, max_dd_end, recovery_days
   - 异常识别：极端回撤、长期无法修复

3. **样本内/外对照**（必须）
   - 字段：period, return, alpha, sharpe, max_dd
   - 异常识别：样本外显著弱于样本内

4. **基本风格暴露**（主仓必须）
   - 字段：factor_name, factor_beta, factor_contribution_pct, t_stat, significance
   - 因子：Size, BP, ROE, Momentum
   - 异常识别：单因子依赖、小盘暴露过大

### 8.2 可延后实现的切片

- 市场状态切片（第二版）
- 行业暴露切片（按需）
- 极端压力场景（第三版）
- 宏观周期切片（第三版）

### 8.3 实现顺序建议

```
Week 1: 年度收益切片 + 年度回撤切片 + 异常识别
Week 2: 样本内/外对照 + 基本风格暴露
Week 3: 市场状态切片（复用03_state_router）
Week 4: 综合异常报告 + 与统一报告集成
```

### 8.4 验证标准

**第一版必须回答**：

- [ ] 能识别"只赚2019年"的策略
- [ ] 能识别"只赚强趋势市"的策略
- [ ] 能识别"纯动量暴露"的策略
- [ ] 异常能直接映射到定档建议
- [ ] 输出能被统一报告直接引用

---

## 九、输出模板汇总

### 9.1 年度切片模板

见 5.1 主表设计，slice_type='year'

### 9.2 市场状态切片模板

见 5.1 主表设计，slice_type='state'

### 9.3 风格切片模板

见 5.1 主表设计，slice_type='style'

### 9.4 异常汇总模板

见 5.2 辅助表设计

---

## 十、代码实现建议

### 10.1 切片计算框架

```python
# regime_slices/base_slice.py

from abc import ABC, abstractmethod
import pandas as pd

class BaseSlice(ABC):
    """切片基类"""
    
    def __init__(self, strategy_id, returns, positions, benchmark_returns):
        self.strategy_id = strategy_id
        self.returns = returns
        self.positions = positions
        self.benchmark_returns = benchmark_returns
    
    @abstractmethod
    def calculate(self) -> pd.DataFrame:
        """计算切片，返回regime_slice_results格式"""
        pass
    
    @abstractmethod
    def detect_anomalies(self, slice_results: pd.DataFrame) -> pd.DataFrame:
        """检测异常，返回anomaly格式"""
        pass
```

### 10.2 年度切片实现

```python
# regime_slices/year_slice.py

class YearSlice(BaseSlice):
    """年度切片"""
    
    def calculate(self) -> pd.DataFrame:
        results = []
        for year in range(self.returns.index.min().year, 
                          self.returns.index.max().year + 1):
            year_returns = self.returns[self.returns.index.year == year]
            # 计算各项指标
            # ...
        return pd.DataFrame(results)
    
    def detect_anomalies(self, slice_results: pd.DataFrame) -> pd.DataFrame:
        anomalies = []
        # 单年依赖检测
        max_contribution = slice_results['contribution_pct'].max()
        if max_contribution > 0.5:
            anomalies.append({
                'anomaly_type': '单年依赖',
                'severity': '高',
                'review_action': '强制降档至D档或E档'
            })
        # ...
        return pd.DataFrame(anomalies)
```

### 10.3 风格切片实现

```python
# regime_slices/style_slice.py

class StyleSlice(BaseSlice):
    """风格切片"""
    
    def __init__(self, strategy_id, returns, positions, benchmark_returns, 
                 factor_data):
        super().__init__(strategy_id, returns, positions, benchmark_returns)
        self.factor_data = factor_data  # 因子数据
    
    def calculate(self) -> pd.DataFrame:
        # 多因子回归
        import statsmodels.api as sm
        X = self.factor_data[['Size', 'BP', 'ROE', 'Momentum']]
        X = sm.add_constant(X)
        y = self.returns - self.benchmark_returns
        model = sm.OLS(y, X).fit()
        # 返回回归结果
        # ...
```

---

## 十一、总结

本框架为策略稳定性分析提供了：

1. **三类切片定义**：年度、市场状态、风格/暴露，覆盖收益分解的主要维度
2. **强制性与选择性**：明确哪些切片是所有策略必跑，哪些按策略类型选择
3. **异常识别规则**：定义了15种异常类型及其对定档的影响
4. **输出格式统一**：设计了主表和辅助表，可直接被统一报告引用
5. **实现优先级**：第一版聚焦核心切片，后续逐步扩展

**核心价值**：

- 让"只赚某几年"的策略无处遁形
- 为准入定档提供直接证据
- 与现有验证流程无缝衔接

**下一步**：

- 任务08：样本外验证（使用年度切片识别的高依赖年份）
- 任务09：稳定性压力测试（使用状态切片识别的弱势状态）
- 任务10：归因与报告（使用风格切片结果）