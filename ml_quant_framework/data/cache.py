import hashlib
import pickle
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


class DataCache:
    """数据缓存管理器。

    基于文件系统的 pickle 缓存，支持 TTL 过期策略。
    用于缓存数据源获取的结果，减少重复 API 调用。
    """

    def __init__(self, cache_dir: str = ".cache/data", ttl_days: int = 7):
        """初始化数据缓存。

        Args:
            cache_dir: 缓存目录路径。
            ttl_days: 缓存有效期（天）。
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(days=ttl_days)

    def _key(self, func_name: str, **kwargs: Any) -> str:
        """生成缓存键。

        基于函数名和参数的 MD5 哈希值生成唯一缓存键。

        Args:
            func_name: 函数名称。
            **kwargs: 函数参数。

        Returns:
            MD5 哈希字符串。
        """
        key_str = f"{func_name}_{sorted(kwargs.items())}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        """获取缓存文件路径。

        Args:
            key: 缓存键。

        Returns:
            缓存文件的 Path 对象。
        """
        return self.cache_dir / f"{key}.pkl"

    def get(self, func_name: str, **kwargs: Any) -> Optional[Any]:
        """获取缓存数据。

        Args:
            func_name: 函数名称。
            **kwargs: 函数参数。

        Returns:
            缓存的数据，如果缓存不存在或已过期则返回 None。
        """
        key = self._key(func_name, **kwargs)
        path = self._path(key)

        if path.exists():
            mtime = path.stat().st_mtime
            mtime_date = date.fromtimestamp(mtime)
            if date.today() - mtime_date < self.ttl:
                with open(path, "rb") as f:
                    return pickle.load(f)

        return None

    def put(self, func_name: str, data: Any, **kwargs: Any) -> None:
        """保存数据到缓存。

        Args:
            func_name: 函数名称。
            data: 要缓存的数据。
            **kwargs: 函数参数。
        """
        key = self._key(func_name, **kwargs)
        path = self._path(key)
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def clear(self) -> None:
        """清空所有缓存。"""
        for p in self.cache_dir.glob("*.pkl"):
            p.unlink()

    def invalidate(self, func_name: str, **kwargs: Any) -> None:
        """使特定缓存失效。

        Args:
            func_name: 函数名称。
            **kwargs: 函数参数。
        """
        key = self._key(func_name, **kwargs)
        path = self._path(key)
        if path.exists():
            path.unlink()
