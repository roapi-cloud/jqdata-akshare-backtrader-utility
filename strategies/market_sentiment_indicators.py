#!/usr/bin/env python3
"""
市场宽度、情绪、牛熊与顶底判断 - 统一指标库
============================================

包含8个维度的市场环境判断指标：
1. 市场宽度(BIAS) - 行业/个股在均线之上比例
2. 拥挤率 - 资金集中度
3. 市场底部特征 - 9个底部信号综合
4. C-VIX波动率 - 基于期权的恐慌指数
5. GSISI投资者情绪指数 - 国信复现
6. FED指标+格雷厄姆指数 - 大周期估值
7. 创新高个股比例 - 市场强度

使用方法：
    from market_sentiment_indicators import MarketSentimentAnalyzer
    analyzer = MarketSentimentAnalyzer()
    analyzer.run_all('2023-01-01', '2024-01-01')
"""

from jqdata import *
import pandas as pd
import numpy as np
import talib as tb
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.interpolate import interp1d
import warnings

warnings.filterwarnings("ignore")

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


class MarketSentimentAnalyzer:
    """市场情绪综合分析器"""

    def __init__(self, benchmark_index="000300.XSHG"):
        self.benchmark = benchmark_index
        self.results = {}

    # ==================== 1. 市场宽度 ====================
    def market_breadth(self, end_date, count=30, industry_type="sw_l1"):
        """
        市场宽度：各行业成分股BIAS>0的比例

        Args:
            end_date: 截止日期
            count: 回看天数
            industry_type: 行业分类方式(sw_l1/jq_l1)

        Returns:
            DataFrame: 各行业及总体宽度，0-100表示比例
        """
        index_stocks = get_index_stocks("000902.XSHG", date=end_date)
        trade_days = get_trade_days(end_date=end_date, count=count)[::-1]

        # 获取行业分类
        industries = get_industries(name=industry_type)
        industry_list = [
            i
            for i in industries.name.tolist()
            if i
            not in [
                "建筑建材I",
                "机械设备I",
                "交运设备I",
                "信息设备I",
                "金融服务I",
                "信息服务I",
            ]
        ]

        result = pd.DataFrame(index=trade_days, columns=industry_list + ["overall"])

        for day in trade_days:
            # 获取当日股票及行业
            stocks = get_index_stocks("000902.XSHG", date=day)
            stock_industry = {}
            for s in stocks:
                ind = get_industry(s, date=day)
                if industry_type in ind and ind[industry_type]:
                    stock_industry[s] = ind[industry_type]["industry_name"]

            # 计算BIAS
            bias = self._calc_bias(stocks, day, window=20)

            # 按行业汇总
            for industry in industry_list:
                ind_stocks = [s for s, i in stock_industry.items() if i == industry]
                if ind_stocks:
                    positive = sum(1 for s in ind_stocks if s in bias and bias[s] > 0)
                    result.loc[day, industry] = int(100 * positive / len(ind_stocks))

            # 总体
            positive_all = sum(1 for s in stocks if s in bias and bias[s] > 0)
            result.loc[day, "overall"] = int(100 * positive_all / len(stocks))

        self.results["market_breadth"] = result
        return result

    def _calc_bias(self, stocks, end_date, window=20):
        """计算BIAS = (C - MA) / MA"""
        try:
            prices = get_price(
                stocks,
                end_date=end_date,
                count=window + 1,
                fields=["close"],
                panel=False,
            )
            pivot = prices.pivot(index="time", columns="code", values="close")

            if len(pivot) >= window:
                ma = pivot.rolling(window).mean()
                last_close = pivot.iloc[-1]
                last_ma = ma.iloc[-1]
                bias = ((last_close - last_ma) / last_ma * 100).dropna()
                return bias.to_dict()
        except:
            pass
        return {}

    # ==================== 2. 拥挤率 ====================
    def crowding_rate(self, end_date, count=100, top_pct=0.05):
        """
        拥挤率：成交额前N%股票的资金集中度

        Args:
            end_date: 截止日期
            count: 回看天数
            top_pct: 前N%股票(默认5%)

        Returns:
            DataFrame: 日期、拥挤率(0-100)
        """
        all_stocks = get_all_securities(date=end_date).index.tolist()
        trade_days = get_trade_days(end_date=end_date, count=count)

        result = []
        for day in trade_days:
            try:
                df = get_price(
                    all_stocks, end_date=day, count=1, fields=["money"], panel=False
                )
                df = df.dropna().sort_values("money", ascending=False)

                n_top = max(1, int(len(df) * top_pct))
                crowd = df.iloc[:n_top]["money"].sum() / df["money"].sum() * 100

                result.append({"date": day, "crowding_rate": round(crowd, 2)})
            except:
                continue

        result_df = pd.DataFrame(result).set_index("date")
        self.results["crowding_rate"] = result_df
        return result_df

    # ==================== 3. 市场底部特征 ====================
    def bottom_features(self, end_date, count=3000):
        """
        市场底部特征：9个维度综合判断

        Returns:
            dict: 各指标的DataFrame
        """
        features = {}

        # 1. 股价<2元个股占比
        features["low_price_ratio"] = self._count_low_price(end_date, count)

        # 2. 破净个股占比
        features["pb_below_1_ratio"] = self._count_pb_below_1(end_date, count)

        # 3. 全市场成交额萎缩程度
        features["volume_shrinkage"] = self._volume_shrinkage(end_date, count)

        # 4. 个股平均成交金额
        features["avg_money_per_stock"] = self._avg_money_per_stock(end_date, count)

        # 5. 个股区间最大跌幅中位数
        features["median_max_drawdown"] = self._median_max_drawdown(end_date, count)

        # 6. 次新股破发率
        features["ipo_break_rate"] = self._ipo_break_rate(end_date, count)

        self.results["bottom_features"] = features
        return features

    def _count_low_price(self, end_date, count):
        """股价<2元占比"""
        all_stocks = get_all_securities(types="stock", date=end_date).index.tolist()
        df = history(
            count,
            unit="1d",
            field="close",
            security_list=all_stocks,
            df=True,
            skip_paused=False,
            fq=None,
        )
        df.fillna(10, inplace=True)

        result = pd.DataFrame(index=df.index)
        result["low_2"] = (df < 2).sum(axis=1) / len(all_stocks)
        return result

    def _count_pb_below_1(self, end_date, count):
        """破净占比"""
        df = history(
            count,
            unit="1d",
            field="close",
            security_list="000001.XSHG",
            df=True,
            skip_paused=False,
            fq=None,
        ).dropna()

        pb_counts = []
        for day in df.index:
            try:
                val = get_fundamentals(
                    query(valuation.code, valuation.pb_ratio).filter(
                        valuation.pb_ratio < 1
                    ),
                    date=day,
                )
                total = len(get_all_securities(types="stock", date=day))
                pb_counts.append(len(val) / total if total > 0 else 0)
            except:
                pb_counts.append(0)

        df["pb_below_1"] = pb_counts
        return df[["pb_below_1"]]

    def _volume_shrinkage(self, end_date, count):
        """成交额萎缩程度"""
        df = history(
            count + 250,
            unit="1d",
            field="money",
            security_list=["399001.XSHE", "000001.XSHG"],
            df=True,
            skip_paused=False,
            fq=None,
        )
        df["total"] = df["399001.XSHE"] + df["000001.XSHG"]

        result = []
        for day in df.index[-count:]:
            max_money = df.loc[:day, "total"].max()
            result.append({"date": day, "shrinkage": df.loc[day, "total"] / max_money})

        return pd.DataFrame(result).set_index("date")

    def _avg_money_per_stock(self, end_date, count):
        """个股平均成交额"""
        vol = self._volume_shrinkage(end_date, count)

        all_stocks = get_all_securities(types="stock").index.tolist()
        paused = history(
            count,
            unit="1d",
            field="paused",
            security_list=all_stocks,
            df=True,
            skip_paused=False,
            fq=None,
        )
        paused.fillna(1, inplace=True)
        trading_count = len(all_stocks) - paused.sum(axis=1)

        vol["avg_money"] = vol["total"] / trading_count
        return vol[["avg_money"]]

    def _median_max_drawdown(self, end_date, count):
        """个股最大跌幅中位数"""
        all_stocks = get_all_securities(types="stock", date=end_date).index.tolist()
        df = history(
            count,
            unit="1d",
            field="close",
            security_list=all_stocks,
            df=True,
            skip_paused=False,
            fq=None,
        )

        result = []
        for day in df.index[-count:]:
            sub_df = df.loc[:day]
            drawdown = (1 - sub_df.iloc[-1:] / sub_df.max()).median(axis=1).values[0]
            result.append({"date": day, "drawdown": drawdown})

        return pd.DataFrame(result).set_index("date")

    def _ipo_break_rate(self, end_date, count):
        """次新股破发率"""
        all_info = get_all_securities(types="stock", date=end_date)
        result = []

        for i in range(count, 0, -1):
            try:
                day = get_trade_days(end_date=end_date, count=i)[-1]
                one_year_ago = (day - timedelta(days=365)).date()
                day_date = day.date() if hasattr(day, "date") else day

                new_stocks = all_info[all_info.start_date < str(day_date)]
                new_stocks = new_stocks[new_stocks.start_date > str(one_year_ago)]

                if len(new_stocks) > 0:
                    prices = get_price(
                        new_stocks.index.tolist(),
                        end_date=day,
                        count=2,
                        fields=["open", "close"],
                        panel=False,
                    )
                    if len(prices) > 0:
                        break_count = len(prices[prices["open"] > prices["close"]])
                        result.append(
                            {"date": day, "break_rate": break_count / len(prices)}
                        )
            except:
                continue

        return pd.DataFrame(result).set_index("date") if result else pd.DataFrame()

    # ==================== 4. C-VIX波动率 ====================
    def calc_cvix(self, start_date, end_date, symbol="510050.XSHG"):
        """
        中国版VIX计算(基于上证50ETF期权)

        需要期权数据支持，此为简化版本
        """
        print("C-VIX需要期权数据，当前为简化版本")
        # 完整实现需要期权数据
        # 参见原文件 64 C-VIX编制手册.ipynb
        return None

    # ==================== 5. GSISI投资者情绪指数 ====================
    def gsisi(self, start_date, end_date, window=35, pct_window=15):
        """
        国信投资者情绪指数(GSISI)

        Args:
            start_date: 开始日期
            end_date: 结束日期
            window: Beta计算窗口
            pct_window: 收益率窗口

        Returns:
            Series: GSISI指数
        """
        # 获取沪深300
        index_price = get_price(
            self.benchmark,
            start_date=start_date,
            end_date=end_date,
            fields=["close"],
            panel=False,
        )
        index_price = index_price.set_index("time")["close"]

        # 获取申万行业
        sw_codes = get_industries(name="sw_l1").index.tolist()
        sw_data = {}
        for code in sw_codes:
            try:
                stocks = get_industry_stocks(code, date=end_date)
                if stocks:
                    prices = get_price(
                        stocks,
                        start_date=start_date,
                        end_date=end_date,
                        fields=["close"],
                        panel=False,
                    )
                    pivot = prices.pivot(index="time", columns="code", values="close")
                    sw_data[code] = pivot.mean(axis=1)
            except:
                continue

        sw_df = pd.DataFrame(sw_data)
        sw_df.index = pd.to_datetime(sw_df.index)
        index_price.index = pd.to_datetime(index_price.index)

        # 计算周收益率
        sw_pct = sw_df.pct_change(pct_window)
        index_pct = index_price.pct_change(pct_window)

        # 计算Beta
        beta_df = sw_pct.apply(lambda x: tb.BETA(x, index_pct, window))

        # Spearman秩相关
        gsisi_series = sw_pct.corrwith(beta_df, method="spearman", axis=1)

        self.results["gsisi"] = gsisi_series
        return gsisi_series

    # ==================== 6. FED指标+格雷厄姆指数 ====================
    def fed_graham(self, end_date, count=365 * 10):
        """
        FED指标和格雷厄姆指数

        FED = 1/PE - 10年国债收益率
        格雷厄姆指数 = (1/PE) / 10年国债收益率

        Returns:
            DataFrame: PE、国债收益率、FED、格雷厄姆指数
        """
        start_date = (
            (end_date - timedelta(days=count))
            if isinstance(end_date, datetime)
            else (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=count))
        )

        trade_days = get_trade_days(start_date=start_date, end_date=end_date)

        pe_list = []
        pe_dates = []

        for day in trade_days:
            try:
                stocks = get_index_stocks(self.benchmark, date=day)
                df = get_valuation(
                    stocks, start_date=None, end_date=day, fields=["pe_ratio"], count=1
                )
                if len(df) > 0:
                    pe_list.append(df["pe_ratio"].median())
                    pe_dates.append(str(day))
            except:
                continue

        result = pd.DataFrame({"pe": pe_list}, index=pe_dates)
        result.index.name = "date"

        # 获取国债收益率(简化处理，实际需从chinabond获取)
        # 这里用固定值近似
        result["bond_yield"] = 3.0  # 近似10年国债收益率

        # 计算指标
        result["fed"] = (100 / result["pe"]) - result["bond_yield"]
        result["graham"] = (100 / result["pe"]) / result["bond_yield"]

        self.results["fed_graham"] = result
        return result

    # ==================== 7. 创新高个股比例 ====================
    def new_high_ratio(self, end_date, check_days=15, window=252, gap=60):
        """
        创新高个股比例

        Args:
            end_date: 截止日期
            check_days: 检查最近N个交易日
            window: 新高统计周期(默认1年)
            gap: 新高间隔要求(默认60天)

        Returns:
            Series: 每日创新高比例(0-100)
        """
        by_date = get_trade_days(end_date=end_date, count=window + check_days)[0]
        stock_list = get_all_securities(date=by_date).index.tolist()

        prices = (
            get_price(
                stock_list,
                end_date=end_date,
                frequency="daily",
                fields="close",
                count=window + check_days,
                panel=False,
            )
            .pivot(index="time", columns="code", values="close")
            .dropna(axis=1)
        )

        newhigh_percent = pd.Series()

        for i in range(check_days):
            check_date = prices.index[window + i]
            price = prices.iloc[i + 1 : window + i + 1]

            # 创新高条件：当前是周期最高，且gap天内未创新高
            is_new_high = price.apply(
                lambda x: np.argmax(x.values) == (len(x) - 1)
                and np.argmax(x.values[:-1]) < (len(x) - 1 - gap)
            )
            new_high_count = is_new_high.sum()
            newhigh_percent.loc[check_date] = 100 * new_high_count / len(stock_list)

        self.results["new_high_ratio"] = newhigh_percent
        return newhigh_percent

    # ==================== 综合分析 ====================
    def run_all(self, end_date, start_date=None):
        """
        运行所有指标

        Args:
            end_date: 截止日期
            start_date: 开始日期(部分指标需要)

        Returns:
            dict: 所有指标结果
        """
        if start_date is None:
            start_date = (
                datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)
            ).strftime("%Y-%m-%d")

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        print("=" * 50)
        print("市场情绪综合分析报告")
        print("=" * 50)

        # 1. 市场宽度
        print("\n[1/7] 计算市场宽度...")
        breadth = self.market_breadth(end_date, count=30)
        print(f"  当前市场宽度: {breadth['overall'].iloc[-1]:.1f}%")

        # 2. 拥挤率
        print("\n[2/7] 计算拥挤率...")
        crowding = self.crowding_rate(end_date, count=60)
        print(f"  当前拥挤率: {crowding['crowding_rate'].iloc[-1]:.2f}%")

        # 3. 底部特征
        print("\n[3/7] 分析底部特征...")
        bottom = self.bottom_features(end_date, count=3000)
        print(f"  破净占比: {bottom['pb_below_1_ratio']['pb_below_1'].iloc[-1]:.2%}")
        print(f"  成交萎缩: {bottom['volume_shrinkage']['shrinkage'].iloc[-1]:.2%}")

        # 4. FED+格雷厄姆
        print("\n[4/7] 计算FED和格雷厄姆指数...")
        fed = self.fed_graham(end_dt)
        print(f"  当前PE: {fed['pe'].iloc[-1]:.2f}")
        print(f"  FED指标: {fed['fed'].iloc[-1]:.2f}")
        print(f"  格雷厄姆指数: {fed['graham'].iloc[-1]:.2f}")

        # 5. 创新高比例
        print("\n[5/7] 计算创新高比例...")
        new_high = self.new_high_ratio(end_dt)
        print(f"  最近创新高比例: {new_high.iloc[-1]:.2f}%")

        # 6. GSISI
        print("\n[6/7] 计算GSISI投资者情绪指数...")
        try:
            gsisi_val = self.gsisi(start_date, end_date)
            if gsisi_val is not None and len(gsisi_val) > 0:
                latest = gsisi_val.dropna().iloc[-1]
                print(f"  当前GSISI: {latest:.4f}")
                if latest > 0.3:
                    print("  → 偏乐观情绪")
                elif latest < -0.3:
                    print("  → 偏悲观情绪")
                else:
                    print("  → 情绪中性")
        except Exception as e:
            print(f"  GSISI计算失败: {e}")

        # 7. C-VIX(需要期权数据)
        print("\n[7/7] C-VIX需要期权数据支持，跳过...")

        # 综合判断
        print("\n" + "=" * 50)
        print("综合判断:")
        self._summary_analysis()
        print("=" * 50)

        return self.results

    def _summary_analysis(self):
        """综合分析判断"""
        signals = []

        # 市场宽度判断
        if "market_breadth" in self.results:
            breadth = self.results["market_breadth"]["overall"].iloc[-1]
            if breadth < 30:
                signals.append(("市场宽度", "极度悲观", "可能接近底部"))
            elif breadth > 70:
                signals.append(("市场宽度", "极度乐观", "注意顶部风险"))
            else:
                signals.append(("市场宽度", "中性", ""))

        # 拥挤率判断
        if "crowding_rate" in self.results:
            crowd = self.results["crowding_rate"]["crowding_rate"].iloc[-1]
            if crowd > 60:
                signals.append(("拥挤率", "偏高", "资金集中，注意轮动"))
            elif crowd < 40:
                signals.append(("拥挤率", "偏低", "资金分散，可能见底"))
            else:
                signals.append(("拥挤率", "正常", ""))

        # 创新高判断
        if "new_high_ratio" in self.results:
            new_high = self.results["new_high_ratio"].iloc[-1]
            if new_high < 1:
                signals.append(("创新高比例", "极低", "市场弱势"))
            elif new_high > 5:
                signals.append(("创新高比例", "较高", "市场强势"))

        for name, status, note in signals:
            print(f"  {name}: {status} {note}")

    def plot_all(self, figsize=(16, 20)):
        """绘制所有指标图表"""
        fig, axes = plt.subplots(5, 1, figsize=figsize)

        idx = 0
        if "market_breadth" in self.results:
            self.results["market_breadth"]["overall"].plot(
                ax=axes[idx], title="市场宽度"
            )
            axes[idx].axhline(y=30, color="g", linestyle="--", alpha=0.5)
            axes[idx].axhline(y=70, color="r", linestyle="--", alpha=0.5)
            idx += 1

        if "crowding_rate" in self.results:
            self.results["crowding_rate"].plot(ax=axes[idx], title="拥挤率")
            idx += 1

        if "fed_graham" in self.results:
            self.results["fed_graham"][["fed", "graham"]].plot(
                ax=axes[idx], title="FED & 格雷厄姆"
            )
            idx += 1

        if "new_high_ratio" in self.results:
            self.results["new_high_ratio"].plot(ax=axes[idx], title="创新高比例")
            idx += 1

        if "gsisi" in self.results and self.results["gsisi"] is not None:
            self.results["gsisi"].dropna().plot(ax=axes[idx], title="GSISI投资者情绪")
            axes[idx].axhline(y=0.3, color="r", linestyle="--", alpha=0.5)
            axes[idx].axhline(y=-0.3, color="g", linestyle="--", alpha=0.5)
            idx += 1

        plt.tight_layout()
        plt.savefig("market_sentiment.png", dpi=150, bbox_inches="tight")
        plt.show()
        print("图表已保存: market_sentiment.png")


# ==================== 独立函数接口 ====================
def quick_analysis(end_date):
    """快速分析，返回核心信号"""
    analyzer = MarketSentimentAnalyzer()

    # 只计算最核心的几个指标
    breadth = analyzer.market_breadth(end_date, count=20)
    crowding = analyzer.crowding_rate(end_date, count=30)
    new_high = analyzer.new_high_ratio(end_date, check_days=5)

    signals = {
        "date": end_date,
        "market_breadth": breadth["overall"].iloc[-1] if len(breadth) > 0 else None,
        "crowding_rate": crowding["crowding_rate"].iloc[-1]
        if len(crowding) > 0
        else None,
        "new_high_ratio": new_high.iloc[-1] if len(new_high) > 0 else None,
    }

    # 简单判断
    is_bottom = (
        (signals["market_breadth"] and signals["market_breadth"] < 30)
        and (signals["crowding_rate"] and signals["crowding_rate"] < 40)
        and (signals["new_high_ratio"] and signals["new_high_ratio"] < 1)
    )

    is_top = (signals["market_breadth"] and signals["market_breadth"] > 70) and (
        signals["new_high_ratio"] and signals["new_high_ratio"] > 5
    )

    signals["judgment"] = (
        "底部区域" if is_bottom else ("顶部区域" if is_top else "中性")
    )
    return signals


if __name__ == "__main__":
    # 测试运行
    analyzer = MarketSentimentAnalyzer()
    results = analyzer.run_all("2024-01-15")
