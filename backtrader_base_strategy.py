import backtrader as bt
import akshare as ak
import pandas as pd
import numpy as np
import math
import os
import statsmodels.api as sm
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime
from types import SimpleNamespace
import collections

matplotlib.rcParams["font.family"] = "Microsoft YaHei"


# ====== 数据加载与缓存 ======
def get_akshare_etf_data(symbol, start, end, cache_dir="etf_cache", force_update=False):
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{symbol}.pkl")
    start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
    need_download = force_update or (not os.path.exists(cache_file))

    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
            df["date"] = pd.to_datetime(df["日期"])
            if df["date"].min() > start_dt or df["date"].max() < end_dt:
                print(
                    f"缓存时间段不全：{df['date'].min().date()} ~ {df['date'].max().date()}，需要重新下载"
                )
                need_download = True
        except Exception as e:
            print(f"读取缓存失败：{e}")
            need_download = True

    if need_download:
        print(f"下载 ETF 数据: {symbol}")
        df = ak.fund_etf_hist_em(symbol=symbol)
        if df.empty:
            raise ValueError(f"No data returned from AkShare for symbol {symbol}")
        df["date"] = pd.to_datetime(df["日期"])
        df.to_pickle(cache_file)

    df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
    if df.empty:
        raise ValueError(f"数据时间范围内无可用数据: {start} ~ {end}")

    df.rename(
        columns={
            "date": "datetime",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        },
        inplace=True,
    )
    df = df[["datetime", "open", "high", "low", "close", "volume"]]
    df["openinterest"] = 0

    data = bt.feeds.PandasData(
        dataname=df,
        datetime="datetime",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
        name=symbol,
    )
    return data


def format_stock_symbol_for_akshare(symbol):
    """
    将聚宽风格的股票代码（sh600000、600000.XSHG、600000、sz000001、000001.XSHE、000001）统一转为6位数字字符串。
    """
    if symbol.startswith("sh") or symbol.startswith("sz"):
        symbol = symbol[2:]
    if symbol.endswith(".XSHG") or symbol.endswith(".XSHE"):
        symbol = symbol[:6]
    return symbol.zfill(6)


def get_akshare_stock_data(
    symbol, start, end, cache_dir="stock_cache", force_update=False, adjust="qfq"
):
    """
    获取A股股票日线行情数据，支持缓存
    symbol: 股票代码，如 'sz000001' 或 'sh600000'
    start, end: 'YYYY-MM-DD'
    adjust: 复权方式，'qfq' 前复权，'hfq' 后复权，None 不复权
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{symbol}_stock_{adjust}.pkl")
    start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
    start_str = start_dt.strftime("%Y%m%d")
    end_str = end_dt.strftime("%Y%m%d")
    need_download = force_update or (not os.path.exists(cache_file))

    akshare_symbol = format_stock_symbol_for_akshare(symbol)

    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
            df["date"] = pd.to_datetime(df["日期"])
            if df["date"].min() > start_dt or df["date"].max() < end_dt:
                print(
                    f"股票缓存时间段不全：{df['date'].min().date()} ~ {df['date'].max().date()}，需要重新下载"
                )
                need_download = True
        except Exception as e:
            print(f"读取股票缓存失败：{e}")
            need_download = True

    if need_download:
        print(f"下载股票数据: {symbol} (akshare symbol: {akshare_symbol})")
        df = ak.stock_zh_a_hist(
            symbol=akshare_symbol,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust=adjust,
        )
        print("下载返回数据：", df.head(), df.shape)  # 新增调试
        if df.empty:
            raise ValueError(f"No data returned from AkShare for symbol {symbol}")
        df["date"] = pd.to_datetime(df["日期"])
        df.to_pickle(cache_file)

    df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
    if df.empty:
        raise ValueError(f"股票数据时间范围内无可用数据: {start} ~ {end}")

    df.rename(
        columns={
            "date": "datetime",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        },
        inplace=True,
    )
    df = df[["datetime", "open", "high", "low", "close", "volume"]]
    df["openinterest"] = 0

    data = bt.feeds.PandasData(
        dataname=df,
        datetime="datetime",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
        name=symbol,
    )
    return data


def get_index_nav(symbol, start, end):
    df = ak.index_zh_a_hist(symbol=symbol, period="daily")
    df["date"] = pd.to_datetime(df["日期"])
    df = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))]
    df = df.sort_values("date")
    df["nav"] = df["收盘"] / df["收盘"].iloc[0]
    return df.set_index("date")["nav"]


def get_price(
    symbols,
    start_date,
    end_date,
    frequency="daily",
    adjust="qfq",
    fields=None,
    cache_dir="stock_cache",
    force_update=False,
):
    """
    统一A股行情数据获取接口，兼容单只/多只股票，聚宽风格
    symbols: str 或 list[str]，如 'sh600519' 或 ['sh600519', 'sz000001']
    start_date, end_date: 'YYYY-MM-DD'
    frequency: 'daily'（后续可扩展'minute'等）
    adjust: 'qfq'/'hfq'/''，复权方式
    fields: None 或 ['open','close',...]，默认全字段
    返回: dict[symbol] -> pd.DataFrame，字段标准化（datetime, open, high, low, close, volume, openinterest）
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    result = {}
    for symbol in symbols:
        akshare_symbol = format_stock_symbol_for_akshare(symbol)
        cache_file = os.path.join(cache_dir, f"{symbol}_stock_{adjust}.pkl")
        start_dt, end_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")
        os.makedirs(cache_dir, exist_ok=True)
        need_download = force_update or (not os.path.exists(cache_file))
        if not need_download:
            try:
                df = pd.read_pickle(cache_file)
                df["date"] = pd.to_datetime(df["日期"])
                if df["date"].min() > start_dt or df["date"].max() < end_dt:
                    need_download = True
            except Exception:
                need_download = True
        if need_download:
            df = ak.stock_zh_a_hist(
                symbol=akshare_symbol,
                period=frequency,
                start_date=start_str,
                end_date=end_str,
                adjust=adjust,
            )
            if df.empty:
                raise ValueError(f"No data for {symbol}")
            df["date"] = pd.to_datetime(df["日期"])
            df.to_pickle(cache_file)
        df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
        df.rename(
            columns={
                "date": "datetime",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
            },
            inplace=True,
        )
        df = df[["datetime", "open", "high", "low", "close", "volume"]]
        df["openinterest"] = 0
        if fields:
            keep = ["datetime"] + [f for f in fields if f in df.columns]
            if "openinterest" in fields:
                keep.append("openinterest")
            df = df[keep]
        result[symbol] = df.reset_index(drop=True)
    return result if len(result) > 1 else result[symbols[0]]


def get_cashflow_sina(
    symbol, stat_date=None, cache_dir="stock_cache", force_update=False
):
    """
    获取A股现金流量表（新浪接口），支持缓存和stat_date筛选。
    symbol: 股票代码，如 'sh600519' 或 'sz000001'
    stat_date: 财报统计日（如'2023-03-31'），None为全部
    返回: DataFrame，字段与新浪接口一致
    """
    import akshare as ak
    import os
    import pandas as pd

    akshare_symbol = symbol.lower() if symbol.startswith(("sh", "sz")) else symbol
    cache_file = os.path.join(cache_dir, f"{akshare_symbol}_cashflow_sina.pkl")
    os.makedirs(cache_dir, exist_ok=True)
    need_download = force_update or (not os.path.exists(cache_file))
    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
        except Exception:
            need_download = True
    if need_download:
        df = ak.stock_financial_report_sina(stock=akshare_symbol, symbol="现金流量表")
        if df.empty:
            raise ValueError(f"No cashflow data for {symbol}")
        df.to_pickle(cache_file)
    if stat_date:
        date_fields = ["报告日", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
        for f in date_fields:
            if f in df.columns:
                date_col = f
                break
        else:
            raise ValueError("找不到报告日期字段")
        df = df[df[date_col] == stat_date]
    return df.reset_index(drop=True)


def get_income_ths(
    symbol, indicator="按报告期", cache_dir="stock_cache", force_update=False
):
    """
    获取A股利润表（同花顺接口），支持缓存和indicator筛选。
    symbol: 股票代码，如 'sh600519' 或 'sz000001' 或 '600519' 或 '000001'
    indicator: "按报告期"/"按单季度"/"按年度"
    返回: DataFrame，字段与同花顺接口一致
    """
    import akshare as ak
    import os
    import pandas as pd

    akshare_symbol = symbol[2:] if symbol.startswith(("sh", "sz")) else symbol
    cache_file = os.path.join(cache_dir, f"{akshare_symbol}_income_ths_{indicator}.pkl")
    os.makedirs(cache_dir, exist_ok=True)
    need_download = force_update or (not os.path.exists(cache_file))
    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
        except Exception:
            need_download = True
    if need_download:
        df = ak.stock_financial_benefit_ths(symbol=akshare_symbol, indicator=indicator)
        if df.empty:
            raise ValueError(f"No income data for {symbol}")
        df.to_pickle(cache_file)
    return df.reset_index(drop=True)


def get_balance_sina(
    symbol, stat_date=None, cache_dir="stock_cache", force_update=False
):
    """
    获取A股资产负债表（新浪接口），支持缓存和stat_date筛选。
    symbol: 股票代码，如 'sh600519' 或 'sz000001'
    stat_date: 财报统计日（如'2023-03-31'），None为全部
    返回: DataFrame，字段与新浪接口一致
    """
    import akshare as ak
    import os
    import pandas as pd

    akshare_symbol = symbol.lower() if symbol.startswith(("sh", "sz")) else symbol
    cache_file = os.path.join(cache_dir, f"{akshare_symbol}_balance_sina.pkl")
    os.makedirs(cache_dir, exist_ok=True)
    need_download = force_update or (not os.path.exists(cache_file))
    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
        except Exception:
            need_download = True
    if need_download:
        df = ak.stock_financial_report_sina(stock=akshare_symbol, symbol="资产负债表")
        if df.empty:
            raise ValueError(f"No balance data for {symbol}")
        df.to_pickle(cache_file)
    if stat_date:
        date_fields = ["报告日", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
        for f in date_fields:
            if f in df.columns:
                date_col = f
                break
        else:
            raise ValueError("找不到报告日期字段")
        df = df[df[date_col] == stat_date]
    return df.reset_index(drop=True)


def get_history_fundamentals(
    security,
    fields,
    watch_date=None,
    stat_date=None,
    count=1,
    interval="1q",
    stat_by_year=False,
    cache_dir="stock_cache",
    force_update=False,
):
    """
    聚宽风格批量财报数据获取接口，支持多股票多期，返回标准化DataFrame

    支持fields=["cash_flow.xxx", "income.xxx", "balance.xxx"]风格，自动分流，无前缀时警告并跳过。
    """
    import pandas as pd
    import re
    import warnings

    # 1. 解析security，转为akshare格式
    def jq2ak_symbol(code):
        if code.endswith(".XSHE"):
            return "sz" + code[:6]
        elif code.endswith(".XSHG"):
            return "sh" + code[:6]
        else:
            return code

    if isinstance(security, str):
        security = [security]

    # 2. 解析stat_date和期数
    def parse_stat_date(stat_date):
        if stat_date is None:
            return None
        if re.match(r"\d{4}q[1-4]", stat_date, re.I):
            y, q = stat_date[:4], stat_date[-1]
            return f"{y}-{'03-31' if q == '1' else '06-30' if q == '2' else '09-30' if q == '3' else '12-31'}"
        return stat_date

    stat_date_fmt = parse_stat_date(stat_date)
    # 3. 字段映射（现金流+利润表+资产负债表）
    field_map = {
        # cash_flow
        "cash_equivalents": "货币资金",
        "net_deposit_increase": "客户存款和同业存放款项净增加额",
        # income
        "total_operating_revenue": "营业总收入",
        "operating_revenue": "营业收入",
        "interest_income": "利息收入",
        "premiums_earned": "已赚保费",
        "commission_income": "手续费及佣金收入",
        "total_operating_cost": "营业总成本",
        "operating_cost": "营业成本",
        "interest_expense": "利息支出",
        "commission_expense": "手续费及佣金支出",
        "refunded_premiums": "退保金",
        "net_pay_insurance_claims": "赔付支出净额",
        "withdraw_insurance_contract_reserve": "提取保险合同准备金净额",
        "policy_dividend_payout": "保单红利支出",
        "reinsurance_cost": "分保费用",
        "operating_tax_surcharges": "营业税金及附加",
        "sale_expense": "销售费用",
        "administration_expense": "管理费用",
        "financial_expense": "财务费用",
        "asset_impairment_loss": "资产减值损失",
        "fair_value_variable_income": "公允价值变动收益",
        "investment_income": "投资收益",
        "invest_income_associates": "对联营企业和合营企业的投资收益",
        "exchange_income": "汇兑收益",
        "operating_profit": "营业利润",
        "non_operating_revenue": "营业外收入",
        "non_operating_expense": "营业外支出",
        "disposal_loss_non_current_liability": "非流动资产处置净损失",
        "total_profit": "利润总额",
        "income_tax_expense": "所得税费用",
        "net_profit": "净利润",
        "np_parent_company_owners": "归属于母公司股东的净利润",
        "minority_profit": "少数股东损益",
        "basic_eps": "基本每股收益",
        "diluted_eps": "稀释每股收益",
        "other_composite_income": "其他综合收益",
        "total_composite_income": "综合收益总额",
        "ci_parent_company_owners": "归属于母公司所有者的综合收益总额",
        "ci_minority_owners": "归属于少数股东的综合收益总额",
        # balance
        "total_assets": "资产总计",
        "total_liability": "负债合计",
        "total_equity": "所有者权益合计",
        "accounts_receivable": "应收账款",
        "accounts_payable": "应付账款",
    }
    # 4. 解析fields，分流到cash/income/balance
    cash_fields, income_fields, balance_fields = [], [], []
    for f in fields:
        if f.startswith("cash_flow."):
            cash_fields.append(f.split(".", 1)[1])
        elif f.startswith("income."):
            income_fields.append(f.split(".", 1)[1])
        elif f.startswith("balance."):
            balance_fields.append(f.split(".", 1)[1])
        else:
            warnings.warn(
                f"字段 {f} 未指定表前缀（cash_flow/income/balance），已跳过。建议使用如 cash_flow.xxx"
            )
    # 5. 批量获取，自动分流cash_flow/income/balance
    dfs = []
    for code in security:
        ak_code = jq2ak_symbol(code)
        out = pd.DataFrame()
        if cash_fields:
            df = get_cashflow_sina(
                ak_code, cache_dir=cache_dir, force_update=force_update
            )
            date_fields = ["报告日", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
            for f in date_fields:
                if f in df.columns:
                    date_col = f
                    break
            else:
                raise ValueError("找不到报告日期字段")
            if stat_date_fmt:
                idx = df[df[date_col] == stat_date_fmt].index
                if not idx.empty:
                    start_idx = idx[0]
                    df = df.iloc[start_idx : start_idx + count]
                else:
                    df = df.head(count)
            else:
                df = df.head(count)
            out["code"] = code
            out["statDate"] = df[date_col]
            for f in cash_fields:
                col = field_map.get(f, f)
                if col in df.columns:
                    out[f"cash_flow.{f}"] = df[col]
                else:
                    out[f"cash_flow.{f}"] = None
        if income_fields:
            df = get_income_ths(ak_code, cache_dir=cache_dir, force_update=force_update)
            date_fields = ["报告期", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
            for f in date_fields:
                if f in df.columns:
                    date_col = f
                    break
            else:
                raise ValueError("找不到报告日期字段")
            if stat_date_fmt:
                idx = df[df[date_col] == stat_date_fmt].index
                if not idx.empty:
                    start_idx = idx[0]
                    df = df.iloc[start_idx : start_idx + count]
                else:
                    df = df.head(count)
            else:
                df = df.head(count)
            if out.empty:
                out["code"] = code
                out["statDate"] = df[date_col]
            for f in income_fields:
                col = field_map.get(f, f)
                if col in df.columns:
                    out[f"income.{f}"] = df[col]
                else:
                    out[f"income.{f}"] = None
        if balance_fields:
            df = get_balance_sina(
                ak_code, cache_dir=cache_dir, force_update=force_update
            )
            date_fields = ["报告日", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
            for f in date_fields:
                if f in df.columns:
                    date_col = f
                    break
            else:
                raise ValueError("找不到报告日期字段")
            if stat_date_fmt:
                idx = df[df[date_col] == stat_date_fmt].index
                if not idx.empty:
                    start_idx = idx[0]
                    df = df.iloc[start_idx : start_idx + count]
                else:
                    df = df.head(count)
            else:
                df = df.head(count)
            if out.empty:
                out["code"] = code
                out["statDate"] = df[date_col]
            for f in balance_fields:
                col = field_map.get(f, f)
                if col in df.columns:
                    out[f"balance.{f}"] = df[col]
                else:
                    out[f"balance.{f}"] = None
        dfs.append(out)
    result = pd.concat(dfs, ignore_index=True)
    result.set_index(["code", "statDate"], inplace=True)
    return result


# ====== 统计分析 ======
def analyze_performance(strategy_nav, benchmark_nav):
    strategy_nav = pd.Series(strategy_nav)
    benchmark_nav = (
        pd.Series(benchmark_nav).reindex(strategy_nav.index).fillna(method="ffill")
    )

    strategy_ret = strategy_nav.pct_change().dropna()
    benchmark_ret = benchmark_nav.pct_change().dropna()
    benchmark_ret.name = "benchmark"
    benchmark_ret = benchmark_ret.reindex(strategy_ret.index).fillna(0)

    days = len(strategy_ret)
    total_return = strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1
    annual_return = (strategy_nav.iloc[-1] / strategy_nav.iloc[0]) ** (252 / days) - 1
    excess_ret = strategy_ret - benchmark_ret

    sharpe_ratio = strategy_ret.mean() / strategy_ret.std() * np.sqrt(252)
    info_ratio = (
        excess_ret.mean() / excess_ret.std() * np.sqrt(252)
        if excess_ret.std() != 0
        else np.nan
    )

    X = sm.add_constant(benchmark_ret)
    model = sm.OLS(strategy_ret, X).fit()
    alpha = model.params["const"] * 252
    beta = model.params[benchmark_ret.name]

    def max_drawdown(nav):
        roll_max = nav.cummax()
        drawdown = (nav - roll_max) / roll_max
        return drawdown.min()

    max_dd = max_drawdown(strategy_nav)

    def downside_std(ret):
        neg_ret = ret[ret < 0]
        return np.sqrt(np.mean(neg_ret**2)) if len(neg_ret) > 0 else 0

    sortino_ratio = strategy_ret.mean() / downside_std(strategy_ret) * np.sqrt(252)

    print(f"策略总收益率: {total_return:.2%}")
    print(f"策略年化收益率: {annual_return:.2%}")
    print(f"夏普比率: {sharpe_ratio:.3f}")
    print(f"信息比率: {info_ratio:.3f}")
    print(f"阿尔法(年化): {alpha:.3%}")
    print(f"贝塔: {beta:.3f}")
    print(f"最大回撤: {max_dd:.2%}")
    print(f"索提诺比率: {sortino_ratio:.3f}")


# ====== 通用策略基类 ======
class PortfolioCompat:
    """兼容聚宽 context.portfolio 风格"""

    def __init__(self, strategy):
        self._s = strategy

    @property
    def positions(self):
        # 返回dict: code -> position对象
        pos = {}
        for data in self._s.datas:
            p = self._s.getposition(data)
            if p.size != 0:
                pos[data._name] = p
        return pos

    @property
    def cash(self):
        return self._s.broker.getcash()

    @property
    def available_cash(self):
        return self._s.broker.getcash()

    @property
    def total_value(self):
        return self._s.broker.getvalue()

    @property
    def positions_value(self):
        return sum([p.size * p.price for p in self.positions.values()])


class JQ2BTBaseStrategy(bt.Strategy):
    params = (
        ("printlog", True),
        ("log_dir", "logs"),
    )

    def __init__(self):
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.navs = []
        os.makedirs(self.params.log_dir, exist_ok=True)
        self.trade_log_file = open(
            os.path.join(self.params.log_dir, "trade_log.txt"), "w", encoding="utf-8"
        )
        self.position_log_file = open(
            os.path.join(self.params.log_dir, "position_log.txt"), "w", encoding="utf-8"
        )
        # g对象，支持g.xxx风格
        self.g = SimpleNamespace()
        # 定时任务注册表
        self._scheduled_tasks = []
        self._bar_count = 0
        self._last_date = None
        # context兼容层，允许context.xxx风格
        self.context = self
        self.current_dt = None
        self.previous_date = None
        self.portfolio = PortfolioCompat(self)
        # 可在context.g/context.run_daily等方式访问

    def log(self, txt, dt=None, log_type="info"):
        if not self.params.printlog:
            return
        dt = dt or self.datas[0].datetime.date(0)
        line = f"{dt.isoformat()}, {txt}\n"
        if log_type == "trade":
            self.trade_log_file.write(line)
        elif log_type == "position":
            self.position_log_file.write(line)
        else:
            print(line, end="")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.log(
                f"ORDER EXECUTED, {order.data._name}, {order.executed.price:.2f}",
                log_type="trade",
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(
                f"ORDER FAILED, {order.data._name}, Status: {order.Status[order.status]}",
                log_type="trade",
            )

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(
            f"TRADE PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}",
            log_type="trade",
        )

    # ====== 定时任务注册API，支持聚宽风格时间字符串 ======
    def run_daily(self, func, time_str=None):
        """
        注册定时任务。支持'14:50'、'before_open'、'after_close'、'every_bar'等聚宽风格。
        """
        self._scheduled_tasks.append((func, time_str))

    def _should_run(self, time_str, bar_idx, bars_in_day):
        if time_str is None:
            return True
        if time_str == "every_bar":
            return True
        if time_str == "before_open":
            return bar_idx == 0
        if time_str == "after_close":
            return bar_idx == bars_in_day - 1
        # 具体时间如'14:50'
        dt = self.datas[0].datetime.datetime(0)
        if isinstance(dt, float):
            dt = bt.num2date(dt)
        if isinstance(time_str, str) and len(time_str) == 5 and ":" in time_str:
            h, m = map(int, time_str.split(":"))
            return dt.hour == h and dt.minute == m
        return False

    def next(self):
        self.navs.append(self.broker.getvalue())
        self._bar_count += 1
        # 取当前bar的日期和时间，自动维护context.current_dt/previous_date
        dt = self.datas[0].datetime.date(0)
        dt_time = self.datas[0].datetime.datetime(0)
        self.previous_date = getattr(self, "current_dt", None)
        self.current_dt = dt_time
        self.context = self
        # 统计今日bar数
        if not hasattr(self, "_bars_today") or self._last_date != dt:
            self._bars_today = []
            self._last_date = dt
        self._bars_today.append(self._bar_count)
        bars_in_day = len(self._bars_today)
        bar_idx = bars_in_day - 1
        # 执行所有定时任务
        for func, time_str in self._scheduled_tasks:
            if self._should_run(time_str, bar_idx, bars_in_day):
                func(self.context)
        # 策略主逻辑可在子类next中继续扩展

    def stop(self):
        self.trade_log_file.close()
        self.position_log_file.close()
        pd.Series(self.navs).to_csv(
            os.path.join(self.params.log_dir, "strategy_nav.csv"), index=False
        )

    # ====== 通用下单API，兼容聚宽风格 ======
    def order_value(self, code, value):
        # code: 股票代码或data对象
        data = self._find_data(code)
        price = data.close[0]
        size = int(value // price)
        if size == 0:
            return None
        return (
            self.buy(data=data, size=size)
            if value > 0
            else self.sell(data=data, size=abs(size))
        )

    def order_target(self, code, amount):
        data = self._find_data(code)
        pos = self.getposition(data).size
        diff = amount - pos
        if diff == 0:
            return None
        return (
            self.buy(data=data, size=diff)
            if diff > 0
            else self.sell(data=data, size=abs(diff))
        )

    def order_target_value(self, code, value):
        data = self._find_data(code)
        price = data.close[0]
        target_size = int(value // price)
        return self.order_target(code, target_size)

    def _find_data(self, code):
        # 支持传入股票代码或data对象
        if isinstance(code, bt.feeds.PandasData):
            return code
        for data in self.datas:
            if data._name == code or getattr(data, "code", None) == code:
                return data
        raise ValueError(f"找不到数据源: {code}")


# ====== 事件驱动调仓系统 ======
from abc import ABC, abstractmethod


class EventTrigger(ABC):
    """事件触发器基类"""

    def __init__(self, name=None):
        self.name = name or self.__class__.__name__
        self._last_check_date = None
        self._cooldown_days = 0  # 冷却天数，防止连续触发
        self._last_fire_date = None

    def set_cooldown(self, days):
        self._cooldown_days = days
        return self

    def _check_cooldown(self, current_date):
        if self._last_fire_date is None:
            return True
        return (current_date - self._last_fire_date).days >= self._cooldown_days

    @abstractmethod
    def check(self, strategy, dt):
        """返回 True 表示触发事件"""
        pass

    def fire(self, strategy, dt):
        self._last_fire_date = dt


class FinancialReportTrigger(EventTrigger):
    """
    财报发布事件触发器
    检测持仓股是否有新财报发布（季报/年报），触发调仓

    用法:
        trigger = FinancialReportTrigger(
            stock_codes=['sh600519', 'sz000333'],
            report_types=['q1', 'q2', 'q3', 'annual']
        )
        strategy.add_trigger(trigger)
    """

    def __init__(
        self, stock_codes=None, report_types=None, check_interval=5, name=None
    ):
        super().__init__(name or "财报发布事件")
        self.stock_codes = stock_codes  # None 表示监控所有持仓股
        self.report_types = report_types or ["q1", "q2", "q3", "annual"]
        self.check_interval = check_interval  # 每N天检查一次财报（避免每天查API）
        self._last_report_dates = {}  # {code: last_stat_date}
        self._day_count = 0

    def check(self, strategy, dt):
        self._day_count += 1
        if self._day_count % self.check_interval != 0:
            return False
        if not self._check_cooldown(dt):
            return False

        codes_to_check = self.stock_codes
        if codes_to_check is None:
            codes_to_check = list(strategy.portfolio.positions.keys())
        if not codes_to_check:
            return False

        for code in codes_to_check:
            try:
                ak_code = format_stock_symbol_for_akshare(code)
                prefixed = ("sz" if ak_code.startswith(("0", "3")) else "sh") + ak_code
                df = get_income_ths(prefixed, cache_dir="stock_cache")
                if df is None or df.empty:
                    continue
                date_col = None
                for f in ["报告期", "报告日期"]:
                    if f in df.columns:
                        date_col = f
                        break
                if date_col is None:
                    continue
                latest_report_date = str(df[date_col].iloc[0])
                # 检查是否是新财报
                if code not in self._last_report_dates:
                    self._last_report_dates[code] = latest_report_date
                    continue
                if latest_report_date != self._last_report_dates[code]:
                    self._last_report_dates[code] = latest_report_date
                    strategy.log(f"[事件] {code} 发布新财报: {latest_report_date}")
                    return True
            except Exception as e:
                strategy.log(f"[事件] {code} 财报检查失败: {e}")
        return False


class TechnicalSignalTrigger(EventTrigger):
    """
    技术信号事件触发器
    支持: 均线交叉、成交量异常、价格突破

    用法:
        # 均线上穿
        trigger = TechnicalSignalTrigger(
            signal_type='ma_cross',
            stock_code='sh000300',  # 用指数判断大势
            fast_period=5,
            slow_period=20,
            direction='up'
        )

        # 放量突破
        trigger = TechnicalSignalTrigger(
            signal_type='volume_spike',
            stock_code='sh000300',
            volume_ratio=2.0  # 成交量是均量的2倍
        )
    """

    def __init__(
        self,
        signal_type="ma_cross",
        stock_code=None,
        fast_period=5,
        slow_period=20,
        direction="up",
        volume_ratio=2.0,
        price_break_pct=0.03,
        name=None,
    ):
        super().__init__(name or f"技术信号:{signal_type}")
        self.signal_type = signal_type
        self.stock_code = stock_code
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.direction = direction  # 'up' or 'down'
        self.volume_ratio = volume_ratio
        self.price_break_pct = price_break_pct
        self._triggered = False  # 防止同一信号连续触发

    def check(self, strategy, dt):
        if not self._check_cooldown(dt):
            return False

        # 找到对应的数据源
        data = None
        if self.stock_code:
            for d in strategy.datas:
                if d._name == self.stock_code:
                    data = d
                    break
        else:
            data = strategy.datas[0]  # 默认用第一个数据源

        if data is None:
            return False

        if len(data) < self.slow_period + 1:
            return False

        triggered = False

        if self.signal_type == "ma_cross":
            triggered = self._check_ma_cross(data)
        elif self.signal_type == "volume_spike":
            triggered = self._check_volume_spike(data)
        elif self.signal_type == "price_break":
            triggered = self._check_price_break(data)
        elif self.signal_type == "rsi_overbought":
            triggered = self._check_rsi(data, overbought=True)
        elif self.signal_type == "rsi_oversold":
            triggered = self._check_rsi(data, overbought=False)

        if triggered:
            self._triggered = True
            self._last_fire_date = dt
        else:
            self._triggered = False

        return triggered

    def _check_ma_cross(self, data):
        fast_now = (
            sum(data.close[-i] for i in range(self.fast_period)) / self.fast_period
        )
        fast_prev = (
            sum(data.close[-(i + 1)] for i in range(self.fast_period))
            / self.fast_period
        )
        slow_now = (
            sum(data.close[-i] for i in range(self.slow_period)) / self.slow_period
        )
        slow_prev = (
            sum(data.close[-(i + 1)] for i in range(self.slow_period))
            / self.slow_period
        )

        if self.direction == "up":
            return fast_prev <= slow_prev and fast_now > slow_now
        else:
            return fast_prev >= slow_prev and fast_now < slow_now

    def _check_volume_spike(self, data):
        if len(data.volume) < 20:
            return False
        avg_vol = sum(data.volume[-i] for i in range(1, 21)) / 20
        if avg_vol == 0:
            return False
        return data.volume[0] > avg_vol * self.volume_ratio

    def _check_price_break(self, data):
        if len(data) < 20:
            return False
        high_20 = max(data.high[-i] for i in range(20))
        if self.direction == "up":
            return data.close[0] > high_20 * (1 + self.price_break_pct)
        else:
            low_20 = min(data.low[-i] for i in range(20))
            return data.close[0] < low_20 * (1 - self.price_break_pct)

    def _check_rsi(self, data, period=14, overbought=True):
        if len(data) < period + 1:
            return False
        gains, losses = [], []
        for i in range(1, period + 1):
            change = data.close[-i + 1] - data.close[-(i + 1)]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        if overbought:
            return rsi > 70
        else:
            return rsi < 30


class CustomTrigger(EventTrigger):
    """
    自定义事件触发器
    传入一个函数，返回 True 就触发

    用法:
        # 当大盘跌幅超过3%触发
        trigger = CustomTrigger(
            condition=lambda strategy, dt: strategy.datas[0].close[0] < strategy.datas[0].close[-1] * 0.97,
            name='大盘暴跌'
        )
    """

    def __init__(self, condition, name=None):
        super().__init__(name or "自定义事件")
        self.condition = condition

    def check(self, strategy, dt):
        if not self._check_cooldown(dt):
            return False
        try:
            return self.condition(strategy, dt)
        except Exception:
            return False


# 扩展 JQ2BTBaseStrategy，添加事件驱动能力
def _extend_base_strategy():
    """给 JQ2BTBaseStrategy 添加事件系统方法"""

    _orig_init = JQ2BTBaseStrategy.__init__
    _orig_next = JQ2BTBaseStrategy.next

    def _new_init(self):
        _orig_init(self)
        self._event_triggers = []
        self._event_handlers = []  # [(handler_func, trigger_name_or_None)]
        self._event_log = []

    def add_trigger(self, trigger):
        """注册一个事件触发器"""
        self._event_triggers.append(trigger)
        return trigger

    def on_event(self, handler, trigger_name=None):
        """
        注册事件处理函数
        handler: func(strategy, dt, trigger_name)
        trigger_name: 只处理指定名称的触发器，None 表示处理所有
        """
        self._event_handlers.append((handler, trigger_name))

    def _fire_event(self, trigger, dt):
        """触发事件，调用所有匹配的处理函数"""
        self.log(f"[事件触发] {trigger.name} @ {dt}")
        self._event_log.append({"date": dt, "trigger": trigger.name})
        trigger.fire(self, dt)
        for handler, name in self._event_handlers:
            if name is None or name == trigger.name:
                try:
                    handler(self, dt, trigger.name)
                except Exception as e:
                    self.log(f"[事件处理异常] {trigger.name}: {e}")

    def _check_all_triggers(self, dt):
        """检查所有触发器"""
        for trigger in self._event_triggers:
            try:
                if trigger.check(self, dt):
                    self._fire_event(trigger, dt)
            except Exception as e:
                self.log(f"[触发器检查异常] {trigger.name}: {e}")

    def get_event_log(self):
        return self._event_log

    def _new_next(self):
        _orig_next(self)
        dt = self.datas[0].datetime.date(0)
        self._check_all_triggers(dt)

    # 猴子补丁
    JQ2BTBaseStrategy.__init__ = _new_init
    JQ2BTBaseStrategy.next = _new_next
    JQ2BTBaseStrategy.add_trigger = add_trigger
    JQ2BTBaseStrategy.on_event = on_event
    JQ2BTBaseStrategy._fire_event = _fire_event
    JQ2BTBaseStrategy._check_all_triggers = _check_all_triggers
    JQ2BTBaseStrategy.get_event_log = get_event_log


_extend_base_strategy()


# ====== 框架主流程 ======
def run_bt_framework(
    strategy_class,
    ETF_POOL,
    start_date,
    end_date,
    benchmark_symbol="000300",
    cash=1000000,
    commission=0.0002,
    slippage=0.0,
):
    # 数据加载断言
    datas = []
    for symbol in ETF_POOL.keys():
        data = get_akshare_etf_data(symbol, start_date, end_date)
        assert data is not None, f"数据加载失败: {symbol}"
        datas.append(data)
    assert len(datas) == len(ETF_POOL), "数据源数量与ETF池不符"

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(perc=slippage)
    for symbol, data in zip(ETF_POOL.keys(), datas):
        cerebro.adddata(data, name=symbol)
    cerebro.addstrategy(strategy_class)

    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    results = cerebro.run()
    strat = results[0]
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

    # 输出净值序列断言
    length = strat.datas[0].buflen()
    dates = [strat.datas[0].datetime.date(-i) for i in range(length)]
    dates.reverse()
    strategy_nav = pd.Series(strat.navs, index=dates)
    assert not strategy_nav.empty, "策略净值序列为空"
    assert strategy_nav.isnull().sum() == 0, "策略净值序列存在缺失值"

    benchmark_nav = get_index_nav(benchmark_symbol, start_date, end_date)
    assert not benchmark_nav.empty, "基准净值序列为空"
    benchmark_nav = benchmark_nav.reindex(strategy_nav.index).fillna(method="ffill")
    assert benchmark_nav.isnull().sum() == 0, "基准净值序列存在缺失值"

    analyze_performance(strategy_nav, benchmark_nav)

    plt.figure(figsize=(10, 5))
    (strategy_nav / strategy_nav.iloc[0]).plot(label="策略净值")
    (benchmark_nav / benchmark_nav.iloc[0]).plot(label="基准", linestyle="--")
    plt.legend()
    plt.title(f"{strategy_class.__name__} vs {benchmark_symbol}净值对比")
    plt.grid(True)
    plt.show()


# ====== JQData风格API适配（AkShare版） ======


def get_price_jq(
    symbols,
    start_date=None,
    end_date=None,
    frequency="daily",
    fields=None,
    adjust="qfq",
    count=None,
    panel=False,
    fill_paused=True,
    skip_paused=True,
    cache_dir="stock_cache",
    force_update=False,
):
    """
    JQData风格 get_price，AkShare适配。支持单只/多只，日线/分钟，复权，字段筛选。
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    result = {}
    for symbol in symbols:
        akshare_symbol = format_stock_symbol_for_akshare(symbol)
        cache_file = os.path.join(cache_dir, f"{symbol}_jq_{adjust}_{frequency}.pkl")
        os.makedirs(cache_dir, exist_ok=True)
        need_download = force_update or (not os.path.exists(cache_file))
        if not need_download:
            try:
                df = pd.read_pickle(cache_file)
            except Exception:
                need_download = True
        if need_download:
            try:
                if frequency in ["1d", "daily"]:
                    df = ak.stock_zh_a_hist(
                        symbol=akshare_symbol,
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust=adjust,
                    )
                elif frequency in ["1m", "5m", "15m", "30m", "60m", "minute"]:
                    period_map = {
                        "1m": "1",
                        "5m": "5",
                        "15m": "15",
                        "30m": "30",
                        "60m": "60",
                    }
                    period = period_map.get(frequency, "1")
                    df = ak.stock_zh_a_minute(symbol=akshare_symbol, period=period)
                else:
                    raise ValueError(f"不支持的frequency: {frequency}")
                if df is None or df.empty:
                    result[symbol] = pd.DataFrame()
                    continue
                df.to_pickle(cache_file)
            except Exception as e:
                warnings.warn(f"{symbol} 获取行情失败: {e}")
                result[symbol] = pd.DataFrame()
                continue
        if df is None or df.empty:
            result[symbol] = pd.DataFrame()
            continue
        # 兼容日期/时间字段
        if "日期" in df.columns:
            df["datetime"] = pd.to_datetime(df["日期"])
        elif "时间" in df.columns:
            df["datetime"] = pd.to_datetime(df["时间"])
        else:
            warnings.warn(f"{symbol} 无日期/时间字段")
            result[symbol] = pd.DataFrame()
            continue
        # 筛选日期
        if start_date and end_date:
            df = df[
                (df["datetime"] >= pd.to_datetime(start_date))
                & (df["datetime"] <= pd.to_datetime(end_date))
            ]
        # 字段映射
        col_map = {
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "money",
        }
        for k, v in col_map.items():
            if k in df.columns:
                df[v] = df[k]
        keep = ["datetime"] + [v for v in col_map.values() if v in df.columns]
        if "openinterest" in (fields or []):
            df["openinterest"] = 0
            keep.append("openinterest")
        if fields:
            keep = ["datetime"] + [
                f for f in fields if f in df.columns or f == "openinterest"
            ]
        df = df[keep] if keep else df
        result[symbol] = df.reset_index(drop=True)
    return result if len(result) > 1 else result[symbols[0]]


def get_fundamentals_jq(
    query_obj, date=None, statDate=None, cache_dir="stock_cache", force_update=False
):
    """
    JQData风格 get_fundamentals，AkShare适配。仅支持简单表名+股票+日期的场景。
    """
    # 这里只做简单适配，复杂query对象暂不支持
    if not isinstance(query_obj, dict):
        raise NotImplementedError(
            '仅支持dict类型query_obj，如{"table": "balance", "symbol": "sh600519"}'
        )
    table = query_obj.get("table")
    symbol = query_obj.get("symbol")
    if table == "balance":
        return get_balance_sina(
            symbol, stat_date=statDate, cache_dir=cache_dir, force_update=force_update
        )
    elif table == "income":
        return get_income_ths(symbol, cache_dir=cache_dir, force_update=force_update)
    elif table == "cash_flow":
        return get_cashflow_sina(
            symbol, stat_date=statDate, cache_dir=cache_dir, force_update=force_update
        )
    else:
        raise NotImplementedError(f"暂不支持的table: {table}")


def get_history_fundamentals_jq(
    security,
    fields,
    watch_date=None,
    stat_date=None,
    count=1,
    interval="1q",
    stat_by_year=False,
    cache_dir="stock_cache",
    force_update=False,
):
    """
    JQData风格 get_history_fundamentals，AkShare适配。支持多股票多期。
    """
    return get_history_fundamentals(
        security,
        fields,
        watch_date=watch_date,
        stat_date=stat_date,
        count=count,
        interval=interval,
        stat_by_year=stat_by_year,
        cache_dir=cache_dir,
        force_update=force_update,
    )


def get_all_securities_jq(
    types=["stock"], date=None, cache_dir="meta_cache", force_update=False
):
    """
    JQData风格 get_all_securities，AkShare适配。返回全市场股票元数据。
    增加缓存机制，默认每日缓存一次。
    """
    import os
    import pandas as pd
    from datetime import datetime

    os.makedirs(cache_dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    cache_file = os.path.join(cache_dir, f"securities_{today}.pkl")
    need_download = force_update or (not os.path.exists(cache_file))
    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
        except Exception:
            need_download = True
    if need_download:
        df = ak.stock_info_a_code_name()
        df["code"] = df["code"].apply(
            lambda x: (
                "sz" + x
                if x.startswith("0")
                else ("sh" + x if x.startswith("6") else x)
            )
        )
        df["jq_code"] = df["code"].apply(
            lambda x: (
                x[2:]
                + (
                    ".XSHE"
                    if x.startswith("sz")
                    else ".XSHG"
                    if x.startswith("sh")
                    else ""
                )
            )
        )
        df.to_pickle(cache_file)
    return df


def get_security_info_jq(code):
    """
    JQData风格 get_security_info，AkShare适配。返回单只股票元数据。
    兼容 df['code'] 为 6位数字 或 带前缀(sh/sz)。
    """
    df = ak.stock_info_a_code_name()
    code_num = format_stock_symbol_for_akshare(code)
    # 构造带前缀代码
    if code_num.startswith("6"):
        code_with_prefix = "sh" + code_num
    elif code_num.startswith("0") or code_num.startswith("3"):
        code_with_prefix = "sz" + code_num
    else:
        code_with_prefix = code_num  # fallback
    # 先查6位数字
    row = df[df["code"] == code_num]
    if row.empty:
        # 再查带前缀
        row = df[df["code"] == code_with_prefix]
    if row.empty:
        # 极端情况再查大小写变体
        row = df[df["code"].str.lower() == code_with_prefix.lower()]
    if row.empty:
        return None
    return row.iloc[0].to_dict()


def get_all_trade_days_jq():
    """
    JQData风格 get_all_trade_days，AkShare适配。返回所有交易日。
    """
    df = ak.tool_trade_date_hist_sina()
    return pd.to_datetime(df["trade_date"]).tolist()


def get_extras_jq(
    field,
    securities,
    start_date=None,
    end_date=None,
    df=True,
    cache_dir="extras_cache",
    force_update=False,
):
    """
    JQData风格 get_extras，AkShare适配。支持ST、停牌等。
    增加缓存机制，默认每日缓存一次。
    """
    import os
    import pandas as pd
    from datetime import datetime

    os.makedirs(cache_dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    if field == "is_st":
        cache_file = os.path.join(cache_dir, f"is_st_{today}.pkl")
        need_download = force_update or (not os.path.exists(cache_file))
        if not need_download:
            try:
                st_df = pd.read_pickle(cache_file)
            except Exception:
                need_download = True
        if need_download:
            st_df = ak.stock_zh_a_st_em()
            st_df.to_pickle(cache_file)
        if isinstance(securities, str):
            securities = [securities]
        result = st_df[
            st_df["代码"].isin(
                [s[2:] if s.startswith(("sh", "sz")) else s for s in securities]
            )
        ]
        return result
    elif field == "is_paused":
        cache_file = os.path.join(cache_dir, f"is_paused_{today}.pkl")
        need_download = force_update or (not os.path.exists(cache_file))
        if not need_download:
            try:
                stop_df = pd.read_pickle(cache_file)
            except Exception:
                need_download = True
        if need_download:
            stop_df = ak.stock_zh_a_stop_em()
            stop_df.to_pickle(cache_file)
        if isinstance(securities, str):
            securities = [securities]
        result = stop_df[
            stop_df["代码"].isin(
                [s[2:] if s.startswith(("sh", "sz")) else s for s in securities]
            )
        ]
        return result
    else:
        raise NotImplementedError(f"暂不支持的extras字段: {field}")


def get_billboard_list_jq(
    stock_list=None,
    end_date=None,
    count=30,
    cache_dir="billboard_cache",
    force_update=False,
):
    """
    JQData风格 get_billboard_list，AkShare适配。龙虎榜。
    增加缓存机制，默认每日缓存一次。
    """
    import os
    import pandas as pd
    from datetime import datetime

    os.makedirs(cache_dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    cache_file = os.path.join(cache_dir, f"billboard_{today}.pkl")
    need_download = force_update or (not os.path.exists(cache_file))
    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
        except Exception:
            need_download = True
    if need_download:
        df = ak.stock_lhb_detail_em()
        df.to_pickle(cache_file)
    if stock_list:
        if isinstance(stock_list, str):
            stock_list = [stock_list]
        df = df[
            df["代码"].isin(
                [s[2:] if s.startswith(("sh", "sz")) else s for s in stock_list]
            )
        ]
    if end_date:
        df = df[df["日期"] <= end_date]
    if count:
        df = df.tail(count)
    return df


def get_factor_values_jq(securities, factors, end_date=None, count=1):
    """
    JQData风格 get_factor_values，AkShare暂不支持，需自定义。
    """
    raise NotImplementedError("AkShare暂不支持聚宽因子库，需自定义实现")


def get_bars_jq(
    security, count, unit="1d", fields=None, include_now=False, end_dt=None
):
    """
    JQData风格 get_bars，AkShare适配。分钟/日线历史K线。
    """
    akshare_symbol = format_stock_symbol_for_akshare(security)
    try:
        if unit in ["1d", "daily"]:
            df = ak.stock_zh_a_hist(symbol=akshare_symbol, period="daily")
        else:
            period_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
            period = period_map.get(unit, "1")
            df = ak.stock_zh_a_minute(symbol=akshare_symbol, period=period)
        if df is None or df.empty:
            return pd.DataFrame()
        # 兼容日期/时间字段
        if "日期" in df.columns:
            df["datetime"] = pd.to_datetime(df["日期"])
        elif "时间" in df.columns:
            df["datetime"] = pd.to_datetime(df["时间"])
        else:
            warnings.warn(f"{security} 无日期/时间字段")
            return pd.DataFrame()
        if end_dt:
            df = df[df["datetime"] <= pd.to_datetime(end_dt)]
        if count:
            df = df.tail(count)
        col_map = {
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "money",
        }
        for k, v in col_map.items():
            if k in df.columns:
                df[v] = df[k]
        keep = ["datetime"] + [v for v in col_map.values() if v in df.columns]
        if fields:
            keep = ["datetime"] + [f for f in fields if f in df.columns]
        df = df[keep] if keep else df
        return df.reset_index(drop=True)
    except Exception as e:
        warnings.warn(f"{security} 获取bars失败: {e}")
        return pd.DataFrame()
