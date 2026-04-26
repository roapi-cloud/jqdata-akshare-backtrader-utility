"""数据缓存管理"""

import logging
import pickle
import hashlib
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataCache:
    """本地数据缓存

    使用pickle序列化存储数据，支持按天过期。
    """

    def __init__(self, cache_dir: str = "./data_cache", force_update: bool = False):
        """初始化缓存

        Args:
            cache_dir: 缓存目录路径
            force_update: 是否强制更新（忽略缓存）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.force_update = force_update
        self._index_file = self.cache_dir / "cache_index.pkl"
        self._index: dict = self._load_index()

    def _load_index(self) -> dict:
        """加载缓存索引

        Returns:
            dict: 缓存索引字典
        """
        if self._index_file.exists():
            try:
                with open(self._index_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self):
        """保存缓存索引到文件"""
        with open(self._index_file, "wb") as f:
            pickle.dump(self._index, f)

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径

        Args:
            key: 缓存键

        Returns:
            Path: 缓存文件路径
        """
        filename = hashlib.md5(key.encode()).hexdigest() + ".pkl"
        return self.cache_dir / filename

    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据

        Args:
            key: 缓存键

        Returns:
            Optional[Any]: 缓存数据，不存在或过期时返回None
        """
        if self.force_update:
            return None

        if key not in self._index:
            return None

        cache_info = self._index[key]
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if mtime < datetime.now() - timedelta(days=1):
                cache_path.unlink()
                del self._index[key]
                self._save_index()
                return None

            try:
                with open(cache_path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None

        return None

    def set(self, key: str, data: Any):
        """设置缓存数据

        Args:
            key: 缓存键
            data: 要缓存的数据
        """
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            self._index[key] = {
                "path": str(cache_path),
                "created": datetime.now().isoformat(),
            }
            self._save_index()
        except Exception as e:
            logger.warning(f"Failed to cache {key}: {e}")

    def clear(self):
        """清空所有缓存数据"""
        for path in self.cache_dir.glob("*.pkl"):
            path.unlink()
        self._index.clear()
        self._save_index()
        logger.info("Cache cleared")

    def size(self) -> str:
        """获取缓存大小

        Returns:
            str: 缓存大小（带单位）
        """
        total = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.pkl") if f.is_file()
        )
        if total < 1024:
            return f"{total}B"
        elif total < 1024 * 1024:
            return f"{total / 1024:.1f}KB"
        else:
            return f"{total / 1024 / 1024:.1f}MB"
