"""最小文件缓存实现（pickle + TTL）"""

import hashlib
import os
import pickle
import time
from typing import Any, Optional


class FileCache:
    def __init__(self, cache_dir: str, ttl_seconds: int = 86400):
        self.cache_dir = cache_dir
        self.ttl = ttl_seconds
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{safe}.pkl")

    def get(self, key: str) -> Any:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        if self.ttl > 0 and time.time() - os.path.getmtime(path) > self.ttl:
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        with open(path, "wb") as f:
            pickle.dump(value, f)
