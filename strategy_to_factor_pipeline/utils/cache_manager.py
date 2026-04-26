"""
缓存管理器
管理策略扫描、因子计算等过程的缓存
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from loguru import logger


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = "./.cache", ttl: int = 86400):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl  # 缓存有效期（秒）
        self._cache_file = self.cache_dir / "cache_index.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict:
        """加载缓存索引"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"version": "1.0", "entries": {}}

    def _save_index(self):
        """保存缓存索引"""
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _compute_key(self, *args, **kwargs) -> str:
        """计算缓存键"""
        key_str = json.dumps(
            {"args": args, "kwargs": kwargs}, sort_keys=True, default=str
        )
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        entry = self._index.get("entries", {}).get(key)
        if not entry:
            return None

        # 检查是否过期
        if time.time() - entry.get("timestamp", 0) > self.ttl:
            self.delete(key)
            return None

        # 加载缓存数据
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def set(self, key: str, data: Any):
        """设置缓存"""
        self._index.setdefault("entries", {})[key] = {
            "timestamp": time.time(),
            "size": len(json.dumps(data, default=str)),
        }

        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        self._save_index()
        logger.debug(f"缓存已设置: {key[:16]}...")

    def delete(self, key: str):
        """删除缓存"""
        if key in self._index.get("entries", {}):
            del self._index["entries"][key]
            self._save_index()

        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            cache_file.unlink()

    def clear(self):
        """清空所有缓存"""
        self._index = {"version": "1.0", "entries": {}}
        self._save_index()

        for f in self.cache_dir.glob("*.json"):
            if f.name != "cache_index.json":
                f.unlink()

        logger.info("缓存已清空")

    def cleanup_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = []

        for key, entry in self._index.get("entries", {}).items():
            if now - entry.get("timestamp", 0) > self.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            self.delete(key)

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        entries = self._index.get("entries", {})
        total_size = sum(e.get("size", 0) for e in entries.values())

        return {
            "total_entries": len(entries),
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
            "ttl_seconds": self.ttl,
        }
