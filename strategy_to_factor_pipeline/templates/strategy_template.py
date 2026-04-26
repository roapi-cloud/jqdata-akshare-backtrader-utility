# -*- coding: utf-8 -*-
"""
策略转因子计算脚本模板
========================
本模板用于将聚宽策略转换为可独立运行的因子计算脚本。
支持数据源：聚宽 JQData / AkShare
输出格式：Parquet / CSV

使用说明：
1. 替换模板中的占位符（以 {{ }} 标记）
2. 根据策略类型选择数据源（jqdata 或 akshare）
3. 运行脚本即可生成因子信号

占位符说明：
    {{STRATEGY_NAME}}    - 策略名称
    {{STRATEGY_DESC}}    - 策略描述
    {{DATA_SOURCE}}      - 数据源：jqdata / akshare
    {{OUTPUT_FORMAT}}    - 输出格式：parquet / csv
    {{OUTPUT_PATH}}      - 输出文件路径
    {{START_DATE}}       - 回测开始日期
    {{END_DATE}}         - 回测结束日期
    {{UNIVERSE}}         - 股票池（如：000300.XSHG / 全市场）
    {{FACTOR_COLUMNS}}   - 因子列名（逗号分隔）
    {{FILTER_CONDITIONS}} - 过滤条件代码块
    {{SCORING_LOGIC}}    - 选股/评分逻辑代码块
    {{SIGNAL_GENERATION}} - 信号生成代码块
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("{{STRATEGY_NAME}}")

# ============================================================
# 配置参数
# ============================================================
CONFIG = {
    "strategy_name": "{{STRATEGY_NAME}}",
    "strategy_desc": "{{STRATEGY_DESC}}",
    "data_source": "{{DATA_SOURCE}}",
    "output_format": "{{OUTPUT_FORMAT}}",
    "output_path": "{{OUTPUT_PATH}}",
    "start_date": "{{START_DATE}}",
    "end_date": "{{END_DATE}}",
    "universe": "{{UNIVERSE}}",
    "factor_columns": ["{{FACTOR_COLUMNS}}"],
}


# ============================================================
# 数据加载层
# ============================================================
class DataLoader:
    """
    统一数据加载器，支持聚宽 JQData 和 AkShare 两种数据源。
    内置本地缓存机制，避免重复请求。
    """

    def __init__(self, source: str = "jqdata", cache_dir: str = ".data_cache"):
        self.source = source
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._price_cache = {}
        self._fundamental_cache = {}
        self._security_list_cache = None

        if source == "jqdata":
            self._init_jqdata()
        elif source == "akshare":
            self._init_akshare()
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def _init_jqdata(self):
        """初始化聚宽 JQData 连接"""
        try:
            from jqdatasdk import auth

            # 从环境变量读取账号密码，避免硬编码
            jq_user = os.environ.get("JQDATA_USER", "")
            jq_pass = os.environ.get("JQDATA_PASSWORD", "")
            if jq_user and jq_pass:
                auth(jq_user, jq_pass)
                logger.info("JQData 认证成功")
            else:
                logger.warning("未设置 JQDATA_USER/JQDATA_PASSWORD 环境变量")
        except ImportError:
            logger.error("未安装 jqdatasdk，请运行: pip install jqdatasdk")
            raise

    def _init_akshare(self):
        """初始化 AkShare（无需认证）"""
        try:
            import akshare as ak

            self._ak = ak
            logger.info("AkShare 初始化成功")
        except ImportError:
            logger.error("未安装 akshare，请运行: pip install akshare")
            raise

    def _cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_key}.parquet"

    def _load_cache(self, key: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(key)
        if path.exists():
            try:
                df = pd.read_parquet(path)
                logger.debug(f"从缓存加载: {key}")
                return df
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None

    def _save_cache(self, key: str, df: pd.DataFrame):
        path = self._cache_path(key)
        try:
            df.to_parquet(path, index=False)
            logger.debug(f"缓存保存: {key}")
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")

    # --------------------------------------------------------
    # 股票列表获取
    # --------------------------------------------------------
    def get_stock_list(self, date: str = None) -> pd.DataFrame:
        """
        获取股票列表

        Returns:
            DataFrame with columns: code, display_name, start_date, end_date, type
        """
        cache_key = f"stock_list_{date or 'all'}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        if self.source == "jqdata":
            from jqdatasdk import get_all_securities

            df = get_all_securities(types=["stock"], date=date)
            df = df.reset_index()
            df = df.rename(columns={"index": "code"})
        elif self.source == "akshare":
            df = self._ak.stock_info_a_code_name()
            df = df.rename(columns={"code": "code", "name": "display_name"})
            df["start_date"] = pd.NaT
            df["end_date"] = pd.NaT
            df["type"] = "stock"

        self._save_cache(cache_key, df)
        self._security_list_cache = df
        return df

    # --------------------------------------------------------
    # 行情数据获取
    # --------------------------------------------------------
    def get_price(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        frequency: str = "daily",
        fields: List[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        获取股票行情数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            frequency: 频率 daily/1m/5m/15m/30m/60m
            fields: 字段列表，默认 ['open', 'high', 'low', 'close', 'volume', 'money']

        Returns:
            {symbol: DataFrame} 字典
        """
        if fields is None:
            fields = ["open", "high", "low", "close", "volume", "money"]

        cache_key = (
            f"price_{','.join(sorted(symbols)[:5])}_{start_date}_{end_date}_{frequency}"
        )
        cached = self._load_cache(cache_key)
        if cached is not None:
            return {sym: cached[cached["code"] == sym] for sym in symbols}

        result = {}

        if self.source == "jqdata":
            from jqdatasdk import get_price

            for sym in symbols:
                try:
                    df = get_price(
                        sym,
                        start_date=start_date,
                        end_date=end_date,
                        frequency=frequency,
                        fields=fields,
                    )
                    if df is not None and not df.empty:
                        df = df.reset_index()
                        df["code"] = sym
                        result[sym] = df
                except Exception as e:
                    logger.warning(f"获取 {sym} 行情数据失败: {e}")

        elif self.source == "akshare":
            for sym in symbols:
                try:
                    # AkShare 使用纯数字代码
                    clean_code = sym.split(".")[0] if "." in sym else sym
                    clean_code = sym.replace("sh", "").replace("sz", "")
                    df = self._ak.stock_zh_a_hist(
                        symbol=clean_code,
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust="qfq",
                    )
                    if df is not None and not df.empty:
                        df = df.rename(
                            columns={
                                "日期": "date",
                                "开盘": "open",
                                "最高": "high",
                                "最低": "low",
                                "收盘": "close",
                                "成交量": "volume",
                                "成交额": "money",
                            }
                        )
                        df["code"] = sym
                        result[sym] = df
                except Exception as e:
                    logger.warning(f"获取 {sym} 行情数据失败: {e}")

        if result:
            combined = pd.concat(result.values(), ignore_index=True)
            self._save_cache(cache_key, combined)

        return result

    # --------------------------------------------------------
    # 财务数据获取
    # --------------------------------------------------------
    def get_fundamentals(
        self,
        symbols: List[str],
        table: str = "valuation",
        date: str = None,
        fields: List[str] = None,
    ) -> pd.DataFrame:
        """
        获取财务基本面数据

        Args:
            symbols: 股票代码列表
            table: 表名 valuation/income/balance/cash_flow/indicator
            date: 查询日期或报告期
            fields: 字段列表

        Returns:
            DataFrame
        """
        cache_key = f"fund_{table}_{','.join(sorted(symbols)[:5])}_{date or 'latest'}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        result = pd.DataFrame()

        if self.source == "jqdata":
            from jqdatasdk import (
                get_fundamentals,
                query,
                valuation,
                income,
                balance,
                cash_flow,
                indicator,
            )

            table_map = {
                "valuation": valuation,
                "income": income,
                "balance": balance,
                "cash_flow": cash_flow,
                "indicator": indicator,
            }
            tbl = table_map.get(table)
            if tbl is None:
                raise ValueError(f"不支持的财务表: {table}")

            q = query(tbl.code).filter(tbl.code.in_(symbols))
            if fields:
                q = query(*[getattr(tbl, f) for f in fields]).filter(
                    tbl.code.in_(symbols)
                )

            if date:
                result = get_fundamentals(q, date=date)
            else:
                result = get_fundamentals(q)

        elif self.source == "akshare":
            # AkShare 财务数据按个股获取
            for sym in symbols[:50]:  # 限制数量避免请求过多
                try:
                    clean_code = sym.split(".")[0] if "." in sym else sym
                    clean_code = sym.replace("sh", "").replace("sz", "")

                    if table == "income":
                        df = self._ak.stock_financial_report_sina(
                            stock=clean_code, symbol="利润表"
                        )
                    elif table == "balance":
                        df = self._ak.stock_financial_report_sina(
                            stock=clean_code, symbol="资产负债表"
                        )
                    elif table == "cash_flow":
                        df = self._ak.stock_financial_report_sina(
                            stock=clean_code, symbol="现金流量表"
                        )
                    else:
                        continue

                    if df is not None and not df.empty:
                        df["code"] = sym
                        result = pd.concat([result, df], ignore_index=True)
                except Exception as e:
                    logger.warning(f"获取 {sym} 财务数据失败: {e}")

        self._save_cache(cache_key, result)
        return result

    # --------------------------------------------------------
    # 指数数据获取
    # --------------------------------------------------------
    def get_index_stocks(self, index_code: str, date: str = None) -> List[str]:
        """获取指数成分股"""
        cache_key = f"index_{index_code}_{date or 'latest'}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached["code"].tolist()

        if self.source == "jqdata":
            from jqdatasdk import get_index_stocks

            stocks = get_index_stocks(index_code, date=date)
        elif self.source == "akshare":
            # 映射指数代码
            index_map = {
                "000300.XSHG": "000300",
                "000905.XSHG": "000905",
                "000016.XSHG": "000016",
                "399006.XSHE": "399006",
            }
            ak_code = index_map.get(index_code, index_code.split(".")[0])
            df = self._ak.index_stock_cons(symbol=ak_code)
            stocks = df["品种代码"].tolist() if "品种代码" in df.columns else []

        result_df = pd.DataFrame({"code": stocks})
        self._save_cache(cache_key, result_df)
        return stocks

    # --------------------------------------------------------
    # 技术指标计算
    # --------------------------------------------------------
    @staticmethod
    def calc_ma(series: pd.Series, window: int) -> pd.Series:
        """移动平均线"""
        return series.rolling(window=window, min_periods=1).mean()

    @staticmethod
    def calc_momentum(series: pd.Series, window: int) -> pd.Series:
        """动量指标：当前价格 / N日前价格 - 1"""
        return series.pct_change(periods=window)

    @staticmethod
    def calc_volatility(series: pd.Series, window: int = 20) -> pd.Series:
        """波动率"""
        return series.pct_change().rolling(window=window, min_periods=5).std()

    @staticmethod
    def calc_rsi(series: pd.Series, window: int = 14) -> pd.Series:
        """RSI 相对强弱指标"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=window, min_periods=1).mean()
        avg_loss = loss.rolling(window=window, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calc_macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 指标"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = 2 * (dif - dea)
        return dif, dea, macd


# ============================================================
# 因子计算引擎
# ============================================================
class FactorEngine:
    """
    因子计算引擎
    根据策略规则计算因子信号
    """

    def __init__(self, data_loader: DataLoader, config: Dict):
        self.loader = data_loader
        self.config = config
        self.logger = logging.getLogger(f"{config['strategy_name']}.engine")

    def run(self) -> pd.DataFrame:
        """
        执行完整的因子计算流程

        Returns:
            DataFrame with columns: date, code, factor_signal, [factor_columns...]
        """
        self.logger.info(f"开始计算因子: {self.config['strategy_name']}")
        self.logger.info(f"数据源: {self.config['data_source']}")
        self.logger.info(f"股票池: {self.config['universe']}")
        self.logger.info(
            f"日期范围: {self.config['start_date']} ~ {self.config['end_date']}"
        )

        # Step 1: 获取股票池
        stock_pool = self._get_stock_pool()
        self.logger.info(f"股票池数量: {len(stock_pool)}")

        # Step 2: 获取行情数据
        price_data = self._get_price_data(stock_pool)
        self.logger.info(f"获取到 {len(price_data)} 只股票的行情数据")

        # Step 3: 获取财务数据（如需要）
        fundamental_data = self._get_fundamental_data(stock_pool)

        # Step 4: 应用过滤条件
        filtered_stocks = self._apply_filters(stock_pool, price_data, fundamental_data)
        self.logger.info(f"过滤后股票数量: {len(filtered_stocks)}")

        # Step 5: 计算因子信号
        signals = self._calculate_signals(filtered_stocks, price_data, fundamental_data)
        self.logger.info(f"生成信号数量: {len(signals)}")

        return signals

    def _get_stock_pool(self) -> List[str]:
        """获取股票池"""
        universe = self.config["universe"]

        # 判断是否为指数代码
        if any(x in universe for x in ["XSHG", "XSHE", "000300", "000905", "399006"]):
            stocks = self.loader.get_index_stocks(universe)
        elif universe.lower() == "all":
            df = self.loader.get_stock_list()
            stocks = df["code"].tolist()
        else:
            stocks = [universe] if isinstance(universe, str) else universe

        return stocks

    def _get_price_data(self, stocks: List[str]) -> Dict[str, pd.DataFrame]:
        """获取行情数据"""
        return self.loader.get_price(
            symbols=stocks,
            start_date=self.config["start_date"],
            end_date=self.config["end_date"],
            frequency="daily",
        )

    def _get_fundamental_data(self, stocks: List[str]) -> pd.DataFrame:
        """获取财务数据"""
        return pd.DataFrame()

    def _apply_filters(
        self,
        stocks: List[str],
        price_data: Dict[str, pd.DataFrame],
        fundamental_data: pd.DataFrame,
    ) -> List[str]:
        """
        应用过滤条件

        默认过滤：ST、停牌、新股、涨跌停
        可在此添加策略特定的过滤逻辑
        """
        filtered = []

        for stock in stocks:
            # 检查是否有行情数据
            if stock not in price_data or price_data[stock].empty:
                continue

            df = price_data[stock]
            latest = df.iloc[-1]

            # 过滤停牌（成交量为0）
            if latest.get("volume", 0) == 0:
                continue

            # 过滤涨跌停（收盘价等于最高价或最低价）
            if latest.get("high", 0) == latest.get("low", 0):
                continue

            filtered.append(stock)

        # ============================================================
        # 策略特定过滤条件
        # ============================================================
        {{FILTER_CONDITIONS}}

        return filtered

    def _calculate_signals(
        self,
        stocks: List[str],
        price_data: Dict[str, pd.DataFrame],
        fundamental_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        计算因子信号

        Returns:
            DataFrame with columns: date, code, factor_signal, [其他因子列]
        """
        all_signals = []

        for stock in stocks:
            if stock not in price_data or price_data[stock].empty:
                continue

            df = price_data[stock].copy()
            df["code"] = stock

            # 计算基础技术指标
            df["ma5"] = DataLoader.calc_ma(df["close"], 5)
            df["ma10"] = DataLoader.calc_ma(df["close"], 10)
            df["ma20"] = DataLoader.calc_ma(df["close"], 20)
            df["momentum_20"] = DataLoader.calc_momentum(df["close"], 20)
            df["volatility_20"] = DataLoader.calc_volatility(df["close"], 20)
            df["rsi_14"] = DataLoader.calc_rsi(df["close"], 14)

            # ============================================================
            # 策略特定评分/选股逻辑
            # ============================================================
            {{SCORING_LOGIC}}

            all_signals.append(df)

        if not all_signals:
            self.logger.warning("未生成任何信号")
            return pd.DataFrame()

        result = pd.concat(all_signals, ignore_index=True)

        # 确保日期列存在
        if "date" not in result.columns and "datetime" in result.columns:
            result = result.rename(columns={"datetime": "date"})

        # 信号生成
        result = self._generate_final_signal(result)

        return result

    def _generate_final_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成最终因子信号

        默认信号：factor_signal = 1 (买入) / 0 (观望) / -1 (卖出)
        """
        # ============================================================
        # 策略特定信号生成逻辑
        # ============================================================
        {{SIGNAL_GENERATION}}

        # 确保 factor_signal 列存在
        if "factor_signal" not in df.columns:
            df["factor_signal"] = 0

        # 选择输出列
        output_cols = ["date", "code", "factor_signal"]
        factor_cols = self.config.get("factor_columns", [])
        for col in factor_cols:
            if col in df.columns and col not in output_cols:
                output_cols.append(col)

        return df[[c for c in output_cols if c in df.columns]]


# ============================================================
# 结果保存
# ============================================================
class ResultSaver:
    """结果保存器，支持 Parquet 和 CSV 格式"""

    def __init__(self, output_path: str, output_format: str = "parquet"):
        self.output_path = Path(output_path)
        self.output_format = output_format

        # 确保输出目录存在
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, df: pd.DataFrame, metadata: Dict = None) -> str:
        """
        保存因子计算结果

        Args:
            df: 因子数据 DataFrame
            metadata: 元数据（策略名称、计算时间等）

        Returns:
            保存的文件路径
        """
        if df.empty:
            logger.warning("数据为空，跳过保存")
            return ""

        # 添加元数据
        if metadata:
            for key, value in metadata.items():
                df[f"meta_{key}"] = value

        if self.output_format == "parquet":
            return self._save_parquet(df)
        elif self.output_format == "csv":
            return self._save_csv(df)
        else:
            raise ValueError(f"不支持的输出格式: {self.output_format}")

    def _save_parquet(self, df: pd.DataFrame) -> str:
        """保存为 Parquet 格式"""
        path = str(self.output_path)
        if not path.endswith(".parquet"):
            path += ".parquet"

        df.to_parquet(path, index=False)
        logger.info(f"结果已保存至: {path} ({len(df)} 行)")
        return path

    def _save_csv(self, df: pd.DataFrame) -> str:
        """保存为 CSV 格式"""
        path = str(self.output_path)
        if not path.endswith(".csv"):
            path += ".csv"

        df.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info(f"结果已保存至: {path} ({len(df)} 行)")
        return path


# ============================================================
# 主流程
# ============================================================
def main():
    """
    主函数：执行完整的因子计算流程
    """
    logger.info("=" * 60)
    logger.info(f"策略因子计算: {CONFIG['strategy_name']}")
    logger.info(f"描述: {CONFIG['strategy_desc']}")
    logger.info("=" * 60)

    start_time = datetime.now()

    try:
        # 1. 初始化数据加载器
        loader = DataLoader(
            source=CONFIG["data_source"],
            cache_dir=".data_cache",
        )

        # 2. 初始化因子引擎
        engine = FactorEngine(loader, CONFIG)

        # 3. 执行因子计算
        signals = engine.run()

        # 4. 保存结果
        saver = ResultSaver(
            output_path=CONFIG["output_path"],
            output_format=CONFIG["output_format"],
        )
        output_file = saver.save(
            signals,
            metadata={
                "strategy": CONFIG["strategy_name"],
                "calc_time": start_time.isoformat(),
                "data_source": CONFIG["data_source"],
            },
        )

        # 5. 输出统计信息
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info("因子计算完成")
        logger.info(f"耗时: {elapsed:.1f} 秒")
        logger.info(f"信号数量: {len(signals)}")
        if not signals.empty:
            logger.info(
                f"信号分布: {signals['factor_signal'].value_counts().to_dict()}"
            )
        logger.info(f"输出文件: {output_file}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"因子计算失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
