# 聚宽有价值策略558 - 6个Jupyter Notebook文件分析报告

> 分析日期: 2026-03-27

---

## 概述

本报告对聚宽有价值策略558目录下的6个Jupyter Notebook文件进行了系统性分析，重点关注工具的功能和用途、可复用的代码模块以及对多因子研究的辅助价值。

---

## 文件详细分析

### 1. 机器学习5折保形回归 (49)

**文件路径**: `49 干货贴《机器学习5折保形回归》.ipynb`

#### 功能概述
实现机器学习5折保形回归（Conformal Regression）用于股票预测，从聚宽平台获取A股市场数据，构建机器学习训练数据集。

#### 核心因子
- 非线性市值 (non_linear_size)
- 贝塔 (beta)
- 市面账值比 (book_to_price_ratio)
- 盈利能力 (earnings_yield)
- 成长 (growth)

#### 可复用代码模块

```python
# 获取指定周期的日期列表
def get_period_date(peroid, start_date, end_date):
    # 支持周期: 'W'(周)、'M'(月)、'Q'(季度)
    pass

# 去除上市不足3个月的股票
def delect_stop(stocks, beginDate, n=30*3):
    pass

# 获取股票池（支持HS300、ZZ500、ZZ800、创业板、中小板、全A股等）
def get_stock(stockPool, begin_date):
    pass

# 使用行业平均值处理缺失值
def replace_nan_indu(factor_data, stockList, industry_code, date):
    pass

# 因子数据预处理（去极值、缺失值处理、标准化）
def data_preprocessing(factor_data, stockList, industry_code, date):
    pass

# 获取指定日期的全部因子数据
def get_factor_data(securities_list, date):
    pass
```

#### 对多因子研究的价值
- 提供完整的因子数据预处理流程（去极值、行业标准化）
- 适用于多因子模型的机器学习训练框架
- 支持按月度频率构建训练和测试数据集

---

### 2. 聚类算法分析研究股票 (61)

**文件路径**: `61 利用聚类算法分析研究股票.ipynb`

#### 功能概述
使用t-SNE降维和K-Means聚类算法分析股票收益率特征，基于股票日收益率序列进行聚类，发现具有相似收益模式的股票群。

#### 可复用代码模块

```python
# 去除上市不足1年的股票
def delect_stop(stocks, beginDate, n=365):
    pass

# 获取股票池
def get_stock(stockPool, begin_date):
    pass

# 获取股票名称
def get_stock_name(code):
    return get_security_info(code).display_name

# 获取股票行业
def get_stock_industry(code):
    return get_industry(code, date=None)['jq_l2']['industry_name']

# t-SNE降维
from sklearn.manifold import TSNE
tsne = TSNE(n_components=2, random_state=42)
embedded_data = tsne.fit_transform(DATA)

# K-Means聚类
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=num_clusters, random_state=42)
labels = kmeans.fit_predict(embedded_data)
```

#### 对多因子研究的价值
- 可用于发现股票收益的潜在结构模式
- 帮助识别具有相似风险收益特征的股票群
- 为因子选股提供聚类视角的补充分析

---

### 3. A股日内动量效应研究 (66)

**文件路径**: `66 研究 【复现】A股日内动量效应（一）半小时 涨跌幅间的规律.ipynb`

#### 功能概述
复现学术论文《Market intraday momentum》中的研究方法，分析A股市场（沪深300、中证500、上证综指、深证成指）的半小时涨跌幅相关性，构建日内动量/反转策略。

#### 主要发现
1. 各指数在下午的交易时段，半小时涨跌幅之间呈现相对较强的正相关关系
2. 上午临收盘半小时（11:00-11:30）与下午开盘半小时（13:00-13:30）正相关
3. 上午临收盘半小时（11:00-11:30）与下午（13:30-14:00）负相关
4. 开盘后半小时（9:30-10:00）与下午开盘后半小时（13:00-13:30）正相关
5. 开盘后半小时（9:30-10:00）与下午临收盘半小时（14:30-15:00）正相关

#### 可复用代码模块

```python
# 数据准备和处理
def preprocessing(symbol, start_date, end_date):
    """
    输入: 指数代码, 起始时间, 截止时间
    返回: daily_returns, ret, Pos_corr(动量关系), Neg_corr(反转关系)
    """
    pass

# 绘制半小时涨跌幅箱体图
def plot_data_box(df, symbol):
    pass

# 绘制相关性热力图
def plot_corr_table(Neg_corr, Pos_corr, symbol):
    pass

# 绘制日内动量/反转策略年化收益
def plot_ann_returns(ret, daily_returns, symbol):
    pass

# 绘制净值曲线
def plot_cum(ret, daily_returns, symbol, target):
    pass
```

#### 有效策略组合
1. 9:30-10:00(yclose)涨/跌 → 13:00-13:30做多/空
2. 9:30-10:00(yclose)涨/跌 → 14:30-15:00做多/空
3. 11:00-11:30涨/跌 → 13:00-13:30做多/空
4. 13:30-14:00涨/跌 → 14:00-14:30做多/空
5. 14:00-14:30涨/跌 → 14:30-15:00做多/空

#### 对多因子研究的价值
- 提供日内高频数据的分析框架
- 揭示A股市场特定的日内动量效应模式
- 可用于构建基于日内动量的因子策略

---

### 4. 聚宽因子库和国盛因子研究 (78)

**文件路径**: `78 获取聚宽因子库和国盛因子的研究.ipynb`

#### 功能概述
系统性获取聚宽平台所有因子库信息，分析因子分类统计，提供国盛证券因子的获取方法。

#### 聚宽因子库概览

| 因子类别 | 数量 | 说明 |
|----------|------|------|
| quality  | 71   | 质量因子 |
| basics   | 37   | 基础科目及衍生类因子 |
| emotion  | 36   | 情绪因子 |
| momentum | 34   | 动量因子 |
| style    | 30   | 风格因子 |
| technical| 16   | 技术因子 |
| pershare | 15   | 每股因子 |
| risk     | 12   | 风险因子 |
| growth   | 9    | 成长因子 |

**总计**: 260个因子

#### 可复用代码模块

```python
# 获取聚宽全部因子列表
from jqfactor import get_all_factors
all_factors = get_all_factors()

# 因子分类统计
all_factors['category'].value_counts()

# 获取行业板块成分股
get_industry_stocks(industry_code, date=None)

# 获取行业分类信息
get_industries('zjw', date=None)
```

#### 风格因子示例 (style类别)
- beta: BETA
- book_leverage: 账面杠杆
- book_to_price_ratio: 市净率因子
- earnings_yield: 收益因子
- growth: 成长因子
- leverage: 杠杆因子
- liquidity: 流动性因子
- momentum: 动量因子
- size: 市值因子
- residual_volatility: 残差波动率

#### 对多因子研究的价值
- **核心价值**: 提供完整的聚宽因子库概览（260个因子）
- 便于研究者快速定位所需因子类别
- 为多因子模型构建提供因子来源参考

---

### 5. 利用myTT库整合通达信公式 (92)

**文件路径**: `92 利用myTT库整合通达信公式——以"飞鹰优选"选股公式为例.ipynb`

#### 功能概述
展示如何使用myTT库将通达信公式转换为Python代码，以"飞鹰优选"选股公式为例，演示完整转换流程。

#### 通达信公式转换规则

| 序号 | 原始写法 | Python写法 |
|------|----------|------------|
| 1    | := 和 :  | =          |
| 2    | AND      | &          |
| 3    | OR       | \|         |
| 4    | = (判断) | ==         |
| 5    | C/COLOSE | close数组  |
| 6    | 分号;    | 可去掉或保留 |
| 7    | 过长语句 | 拆分多行   |
| 8    | 隐式运算 | 适当加括号 |

#### 飞鹰优选公式示例

```python
# 整理之后的Python代码
VAR1 = CLOSE / MA(CLOSE, 40) * 100 < 78
VAR2 = CLOSE / MA(CLOSE, 60) * 100 < 74
VAR3 = HIGH > LOW * 1.051
VAR4 = VAR3 & (COUNT(VAR3, 5) > 1)
TYP = (HIGH + LOW + CLOSE) / 3
CCI = (TYP - MA(TYP, 14)) / (0.015 * AVEDEV(TYP, 14))
T1 = (MA(CLOSE, 27) > 1.169*CLOSE) & (MA(CLOSE, 17) > 1.158*CLOSE)
T2 = (CLOSE < MA(CLOSE, 120)) & (MA(CLOSE, 60) < MA(CLOSE, 120)) & \
     (MA(CLOSE, 60) > MA(CLOSE, 30)) & (CCI > -210)
FYYH = VAR4 & (VAR1 | VAR2) & T1 & T2
XG = BARSLASTCOUNT(FYYH) == 1
```

#### 对多因子研究的价值
- **核心价值**: 打通通达信公式与Python的桥梁
- 便于将传统技术指标快速迁移到量化平台
- 提供技术指标因子化的方法论

---

### 6. 简单选股器分享 (96)

**文件路径**: `96 研究 分享一个简单的选股器.ipynb`

#### 功能概述
实现一个基于多条件筛选的选股器，结合成交量、价格、均线等技术指标进行选股，使用Alpha101因子对选股结果进行评分排序。

#### 选股条件
1. 换手率在3%-10%之间
2. 剔除ST股票和次新股（上市不足1年）
3. 单日成交量大于前5日所有成交量的2倍（倍量）
4. 当日上涨（收盘价高于开盘价）
5. 非长上影线（实体大于上影线）
6. 开盘涨幅不超过5%
7. 涨幅不低于5%
8. 10日内有7日股价高于60日均线
9. 近3日股价必须高于60日均线
10. 不得高于30日最低价的1.25倍
11. 不得高于5日最低价的1.13倍

#### 可复用代码模块

```python
# 获取近期n天大于value_list的个数
def get_bigger_than_val_counter(close, n, value_list):
    pass

# 均线计算
def get_ma(close, timeperiod=5):
    return talib.SMA(close, timeperiod)

# MACD计算
def get_macd(close):
    diff, dea, macd = talib.MACDEXT(
        close, fastperiod=12, fastmatype=1, 
        slowperiod=26, slowmatype=1, 
        signalperiod=9, signalmatype=1
    )
    return diff, dea, macd * 2

# 倍量判断
def is_multiple_stocks(volume, days=5):
    pass

# 波动百分比标准差
def get_std_percentage(var_list):
    pass

# 均线多头排列判断
def get_avg_array(avg_list):
    pass

# 股票评分排序
def get_stocks_score(tick_list, data_frame, pass_time):
    pass

# 完整选股流程
def select_ticks(check_date):
    pass
```

#### 对多因子研究的价值
- 提供完整的选股流程框架
- 展示技术指标与基本面筛选的结合方法
- 包含Alpha101因子评分的应用示例

---

## 综合评估

| 序号 | 文件名 | 核心价值 | 可复用性 | 对多因子研究的辅助价值 |
|------|--------|----------|----------|------------------------|
| 1 | 机器学习5折保形回归 | 因子预处理、ML框架 | 高 | ⭐⭐⭐⭐⭐ |
| 2 | 聚类算法分析研究股票 | 补充分析工具 | 中 | ⭐⭐⭐ |
| 3 | A股日内动量效应 | 高频因子研究 | 高 | ⭐⭐⭐⭐ |
| 4 | 获取聚宽因子库和国盛因子 | 因子库概览 | 极高 | ⭐⭐⭐⭐⭐ |
| 5 | 利用myTT库整合通达信公式 | 技术指标因子化 | 高 | ⭐⭐⭐⭐ |
| 6 | 分享一个简单的选股器 | 选股框架参考 | 中 | ⭐⭐⭐ |

---

## 建议使用顺序

### 多因子研究入门
1. **78 获取聚宽因子库** → 了解可用因子资源
2. **49 机器学习5折保形回归** → 学习因子预处理和模型构建
3. **96 简单选股器** → 理解因子筛选和评分机制

### 技术指标研究
1. **92 myTT库整合通达信公式** → 学习技术指标转换方法
2. **66 A股日内动量效应** → 研究高频动量因子

### 股票分类研究
1. **61 聚类算法分析研究股票** → 学习基于收益模式的股票聚类

---

## 附录：依赖库清单

```python
# 基础库
import numpy as np
import pandas as pd
import datetime
import warnings

# 聚宽专用库
from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
from jqlib.alpha101 import *

# 机器学习库
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

# 技术分析库
import talib
from myTT import *

# 可视化库
import matplotlib.pyplot as plt
import seaborn as sns
```

---

*本报告由AI助手自动生成，仅供参考学习使用。*
