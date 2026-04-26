"""因子数据存储模块

使用 Parquet 格式存储因子信号数据，SQLite 存储元数据。
支持按策略/日期/股票查询、增量更新、因子组合查询。
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class FactorDatabase:
    """因子数据库管理类

    使用 Parquet 文件存储因子信号数据，SQLite 存储元数据。
    支持高效压缩、增量更新和多维度查询。
    """

    def __init__(self, db_path: str, data_dir: str):
        """初始化因子数据库

        Args:
            db_path: SQLite 元数据数据库路径
            data_dir: Parquet 数据存储目录
        """
        self.db_path = db_path
        self.data_dir = data_dir

        os.makedirs(data_dir, exist_ok=True)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._init_metadata_db()

    def _init_metadata_db(self):
        """初始化 SQLite 元数据表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS factor_metadata (
                factor_name TEXT PRIMARY KEY,
                factor_type TEXT,
                strategy_source TEXT,
                params_json TEXT,
                created_at TEXT,
                updated_at TEXT,
                description TEXT,
                row_count INTEGER DEFAULT 0,
                date_range_start TEXT,
                date_range_end TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS factor_partitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factor_name TEXT NOT NULL,
                partition_date TEXT,
                file_path TEXT,
                row_count INTEGER,
                created_at TEXT,
                FOREIGN KEY (factor_name) REFERENCES factor_metadata(factor_name)
            )
        """)

        conn.commit()
        conn.close()

    def _get_factor_file_path(self, factor_name: str) -> str:
        """获取因子数据文件路径"""
        safe_name = factor_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.data_dir, f"{safe_name}.parquet")

    def _get_partition_dir(self, factor_name: str) -> str:
        """获取因子分区目录路径"""
        safe_name = factor_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.data_dir, safe_name)

    def _update_metadata(self, factor_name: str, **kwargs):
        """更新因子元数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)

        if fields:
            values.append(factor_name)
            sql = (
                f"UPDATE factor_metadata SET {', '.join(fields)} WHERE factor_name = ?"
            )
            cursor.execute(sql, values)
            conn.commit()

        conn.close()

    def save_factor_signals(
        self,
        factor_name: str,
        signals_df: pd.DataFrame,
        metadata: Optional[Dict] = None,
    ):
        """保存因子信号数据

        Args:
            factor_name: 因子名称
            signals_df: 信号数据 DataFrame，需包含 date, stock_code, signal 列
            metadata: 因子元数据字典，包含 factor_type, strategy_source, params, description
        """
        required_cols = {"date", "stock_code", "signal"}
        if not required_cols.issubset(signals_df.columns):
            raise ValueError(f"DataFrame 必须包含列: {required_cols}")

        df = signals_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "stock_code"]).reset_index(drop=True)

        factor_file = self._get_factor_file_path(factor_name)

        if os.path.exists(factor_file):
            existing_df = pd.read_parquet(factor_file)
            df = pd.concat([existing_df, df], ignore_index=True)
            df = df.drop_duplicates(subset=["date", "stock_code"], keep="last")
            df = df.sort_values(["date", "stock_code"]).reset_index(drop=True)

        table = pa.Table.from_pandas(df)
        pq.write_table(table, factor_file, compression="snappy")

        metadata = metadata or {}
        now = datetime.now().isoformat()
        date_min = df["date"].min().isoformat()
        date_max = df["date"].max().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT factor_name FROM factor_metadata WHERE factor_name = ?",
            (factor_name,),
        )
        exists = cursor.fetchone()

        if exists:
            self._update_metadata(
                factor_name,
                updated_at=now,
                row_count=len(df),
                date_range_start=date_min,
                date_range_end=date_max,
            )
        else:
            cursor.execute(
                """
                INSERT INTO factor_metadata
                (factor_name, factor_type, strategy_source, params_json,
                 created_at, updated_at, description, row_count,
                 date_range_start, date_range_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    factor_name,
                    metadata.get("factor_type", "unknown"),
                    metadata.get("strategy_source", ""),
                    json.dumps(metadata.get("params", {})),
                    now,
                    now,
                    metadata.get("description", ""),
                    len(df),
                    date_min,
                    date_max,
                ),
            )

        conn.commit()
        conn.close()
        logger.info(f"保存因子 {factor_name}: {len(df)} 条记录")

    def load_factor_signals(
        self,
        factor_name: str,
        date_range: Optional[tuple] = None,
        stock_list: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """加载因子信号数据

        Args:
            factor_name: 因子名称
            date_range: 日期范围 (start_date, end_date)
            stock_list: 股票代码列表

        Returns:
            因子信号 DataFrame
        """
        factor_file = self._get_factor_file_path(factor_name)
        if not os.path.exists(factor_file):
            raise FileNotFoundError(f"因子数据文件不存在: {factor_file}")

        df = pd.read_parquet(factor_file)
        df["date"] = pd.to_datetime(df["date"])

        if date_range:
            start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            df = df[(df["date"] >= start) & (df["date"] <= end)]

        if stock_list:
            df = df[df["stock_code"].isin(stock_list)]

        return df.reset_index(drop=True)

    def get_factor_metadata(self, factor_name: str) -> Dict:
        """获取因子元数据

        Args:
            factor_name: 因子名称

        Returns:
            因子元数据字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM factor_metadata WHERE factor_name = ?", (factor_name,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise KeyError(f"因子不存在: {factor_name}")

        columns = [
            "factor_name",
            "factor_type",
            "strategy_source",
            "params_json",
            "created_at",
            "updated_at",
            "description",
            "row_count",
            "date_range_start",
            "date_range_end",
        ]
        metadata = dict(zip(columns, row))
        metadata["params"] = json.loads(metadata.pop("params_json"))
        return metadata

    def list_all_factors(self) -> List[Dict]:
        """列出所有因子

        Returns:
            因子元数据列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM factor_metadata ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()

        columns = [
            "factor_name",
            "factor_type",
            "strategy_source",
            "params_json",
            "created_at",
            "updated_at",
            "description",
            "row_count",
            "date_range_start",
            "date_range_end",
        ]

        factors = []
        for row in rows:
            metadata = dict(zip(columns, row))
            metadata["params"] = json.loads(metadata.pop("params_json"))
            factors.append(metadata)

        return factors

    def get_signals_cross_section(
        self,
        date: Union[str, datetime],
        factor_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取某日期所有股票的横截面信号

        Args:
            date: 查询日期
            factor_names: 因子名称列表，None 表示所有因子

        Returns:
            DataFrame，index=stock_code, columns=factor_names
        """
        date = pd.to_datetime(date)

        if factor_names is None:
            factors = self.list_all_factors()
            factor_names = [f["factor_name"] for f in factors]

        if not factor_names:
            return pd.DataFrame()

        result_dfs = []
        for fname in factor_names:
            try:
                df = self.load_factor_signals(fname, date_range=(date, date))
                if not df.empty:
                    df = df[["stock_code", "signal"]].copy()
                    df.columns = ["stock_code", fname]
                    result_dfs.append(df)
            except FileNotFoundError:
                continue

        if not result_dfs:
            return pd.DataFrame()

        result = result_dfs[0]
        for rdf in result_dfs[1:]:
            result = result.merge(rdf, on="stock_code", how="outer")

        result.set_index("stock_code", inplace=True)
        return result

    def get_signals_time_series(
        self,
        stock_code: str,
        factor_names: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """获取某股票在所有策略中的时序信号

        Args:
            stock_code: 股票代码
            factor_names: 因子名称列表，None 表示所有因子
            date_range: 日期范围 (start_date, end_date)

        Returns:
            DataFrame，index=date, columns=factor_names
        """
        if factor_names is None:
            factors = self.list_all_factors()
            factor_names = [f["factor_name"] for f in factors]

        if not factor_names:
            return pd.DataFrame()

        result_dfs = []
        for fname in factor_names:
            try:
                df = self.load_factor_signals(
                    fname, date_range=date_range, stock_list=[stock_code]
                )
                if not df.empty:
                    df = df[["date", "signal"]].copy()
                    df.columns = ["date", fname]
                    result_dfs.append(df)
            except FileNotFoundError:
                continue

        if not result_dfs:
            return pd.DataFrame()

        result = result_dfs[0]
        for rdf in result_dfs[1:]:
            result = result.merge(rdf, on="date", how="outer")

        result.set_index("date", inplace=True)
        result.sort_index(inplace=True)
        return result

    def update_factor(
        self,
        factor_name: str,
        new_signals_df: pd.DataFrame,
    ):
        """增量更新因子数据

        Args:
            factor_name: 因子名称
            new_signals_df: 新增信号数据 DataFrame
        """
        self.save_factor_signals(factor_name, new_signals_df)

    def delete_factor(self, factor_name: str):
        """删除因子及其数据

        Args:
            factor_name: 因子名称
        """
        factor_file = self._get_factor_file_path(factor_name)

        if os.path.exists(factor_file):
            os.remove(factor_file)
            logger.info(f"删除因子数据文件: {factor_file}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM factor_partitions WHERE factor_name = ?", (factor_name,)
        )
        cursor.execute(
            "DELETE FROM factor_metadata WHERE factor_name = ?", (factor_name,)
        )
        conn.commit()
        conn.close()

        logger.info(f"删除因子元数据: {factor_name}")

    def get_factor_combination(
        self,
        factor_names: List[str],
        weights: Optional[Dict[str, float]] = None,
        date_range: Optional[tuple] = None,
        stock_list: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取因子组合信号

        Args:
            factor_names: 因子名称列表
            weights: 因子权重字典，None 表示等权
            date_range: 日期范围
            stock_list: 股票代码列表

        Returns:
            DataFrame，包含各因子信号及组合信号
        """
        if weights is None:
            weights = {name: 1.0 / len(factor_names) for name in factor_names}

        all_signals = []
        for fname in factor_names:
            try:
                df = self.load_factor_signals(
                    fname, date_range=date_range, stock_list=stock_list
                )
                if not df.empty:
                    df = df[["date", "stock_code", "signal"]].copy()
                    df.rename(columns={"signal": fname}, inplace=True)
                    all_signals.append(df)
            except FileNotFoundError:
                logger.warning(f"因子 {fname} 无数据，跳过")

        if not all_signals:
            return pd.DataFrame()

        result = all_signals[0]
        for sig_df in all_signals[1:]:
            result = result.merge(sig_df, on=["date", "stock_code"], how="outer")

        factor_cols = [c for c in factor_names if c in result.columns]
        if not factor_cols:
            return pd.DataFrame()

        weight_series = pd.Series(
            {c: weights.get(c, 0) for c in factor_cols},
        )
        valid_weights = weight_series[weight_series > 0]
        result["combined_signal"] = (result[factor_cols] * valid_weights).sum(axis=1)

        return result

    def get_factor_correlation(
        self,
        factor_names: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """计算因子间相关性矩阵

        Args:
            factor_names: 因子名称列表，None 表示所有因子
            date_range: 日期范围

        Returns:
            相关性矩阵 DataFrame
        """
        if factor_names is None:
            factors = self.list_all_factors()
            factor_names = [f["factor_name"] for f in factors]

        all_data = []
        for fname in factor_names:
            try:
                df = self.load_factor_signals(fname, date_range=date_range)
                if not df.empty:
                    df = df[["date", "stock_code", "signal"]].copy()
                    df.rename(columns={"signal": fname}, inplace=True)
                    all_data.append(df)
            except FileNotFoundError:
                continue

        if len(all_data) < 2:
            return pd.DataFrame()

        merged = all_data[0]
        for df in all_data[1:]:
            merged = merged.merge(df, on=["date", "stock_code"], how="inner")

        factor_cols = [c for c in factor_names if c in merged.columns]
        return merged[factor_cols].corr()

    def get_factor_stats(
        self,
        factor_name: str,
        date_range: Optional[tuple] = None,
    ) -> Dict:
        """获取因子统计信息

        Args:
            factor_name: 因子名称
            date_range: 日期范围

        Returns:
            统计信息字典
        """
        df = self.load_factor_signals(factor_name, date_range=date_range)

        if df.empty:
            return {}

        stats = {
            "factor_name": factor_name,
            "count": len(df),
            "signal_mean": df["signal"].mean(),
            "signal_std": df["signal"].std(),
            "signal_min": df["signal"].min(),
            "signal_max": df["signal"].max(),
            "signal_median": df["signal"].median(),
            "unique_stocks": df["stock_code"].nunique(),
            "unique_dates": df["date"].nunique(),
            "date_range_start": df["date"].min().isoformat(),
            "date_range_end": df["date"].max().isoformat(),
        }

        return stats
