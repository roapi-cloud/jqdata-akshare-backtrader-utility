"""Thread-safe disk-based data cache with TTL support."""

import hashlib
import logging
import os
import pickle
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """Disk-based cache for market data with TTL (time-to-live) support.

    Supports both pickle (for arbitrary Python objects) and parquet
    (for pandas DataFrames) serialization formats. All operations are
    thread-safe via a reentrant lock.

    Attributes:
        cache_dir: Root directory for cached files.
        ttl_seconds: Default time-to-live in seconds. None means no expiry.
        format: Default serialization format ("pickle" or "parquet").
    """

    def __init__(
        self,
        cache_dir: str = ".cache/data",
        ttl_seconds: Optional[int] = 86400,
        format: str = "parquet",
    ) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cached files.
            ttl_seconds: Time-to-live in seconds. None disables expiry.
            format: Default format - "pickle" or "parquet".
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.format = format
        self._lock = threading.RLock()
        self._memory_cache: dict[str, tuple[Any, float]] = {}

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a deterministic cache key from arguments.

        Args:
            *args: Positional arguments to hash.
            **kwargs: Keyword arguments to hash.

        Returns:
            Hexadecimal MD5 hash string safe for use as a filename.
        """
        raw = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str, fmt: Optional[str] = None) -> Path:
        """Resolve the full file path for a cache key.

        Args:
            key: Cache key (MD5 hex string).
            fmt: File format override. Defaults to self.format.

        Returns:
            Full path to the cache file.
        """
        fmt = fmt or self.format
        ext = "pkl" if fmt == "pickle" else "parquet"
        return self.cache_dir / f"{key}.{ext}"

    def _is_expired(self, path: Path) -> bool:
        """Check whether a cached file has exceeded its TTL.

        Args:
            path: Path to the cached file.

        Returns:
            True if the file is expired or does not exist.
        """
        if self.ttl_seconds is None:
            return False
        if not path.exists():
            return True
        age = time.time() - path.stat().st_mtime
        return age > self.ttl_seconds

    def get(
        self,
        key: str,
        fmt: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve a value from the cache.

        Args:
            key: Cache key (MD5 hex string).
            fmt: Format override. Defaults to self.format.

        Returns:
            Cached value, or None if not found or expired.
        """
        fmt = fmt or self.format

        with self._lock:
            if key in self._memory_cache:
                value, cached_at = self._memory_cache[key]
                if (
                    self.ttl_seconds is None
                    or (time.time() - cached_at) <= self.ttl_seconds
                ):
                    logger.debug("Memory cache hit: %s", key)
                    return value
                else:
                    del self._memory_cache[key]

        path = self._cache_path(key, fmt)

        with self._lock:
            if not path.exists():
                return None
            if self._is_expired(path):
                logger.debug("Disk cache expired: %s", path)
                path.unlink(missing_ok=True)
                return None

            try:
                if fmt == "parquet":
                    data = pd.read_parquet(path)
                else:
                    with open(path, "rb") as f:
                        data = pickle.load(f)

                with self._lock:
                    self._memory_cache[key] = (data, time.time())

                logger.debug("Disk cache hit: %s", path)
                return data
            except Exception as e:
                logger.warning("Cache read error (%s): %s", path, e)
                path.unlink(missing_ok=True)
                return None

    def put(
        self,
        key: str,
        value: Any,
        fmt: Optional[str] = None,
    ) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key (MD5 hex string).
            value: Value to cache (DataFrame or picklable object).
            fmt: Format override. Defaults to self.format.
        """
        fmt = fmt or self.format

        with self._lock:
            self._memory_cache[key] = (value, time.time())

        path = self._cache_path(key, fmt)

        with self._lock:
            try:
                if fmt == "parquet" and isinstance(value, pd.DataFrame):
                    value.to_parquet(path, index=False)
                else:
                    with open(path, "wb") as f:
                        pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
                logger.debug("Cache write: %s", path)
            except Exception as e:
                logger.warning("Cache write error (%s): %s", path, e)

    def get_or_compute(
        self,
        compute_fn,
        *args: Any,
        fmt: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Get from cache or compute and store the result.

        Convenience method that generates a key from the arguments,
        checks the cache, and calls compute_fn() on a cache miss.

        Args:
            compute_fn: Callable that produces the data.
            *args: Positional arguments (used for cache key).
            fmt: Format override.
            **kwargs: Keyword arguments (used for cache key).

        Returns:
            Cached or freshly computed value.
        """
        key = self._make_key(compute_fn.__name__, *args, **kwargs)
        result = self.get(key, fmt=fmt)
        if result is not None:
            return result

        logger.info("Cache miss, computing: %s", key)
        result = compute_fn(*args, **kwargs)
        if result is not None:
            self.put(key, result, fmt=fmt)
        return result

    def clear(self) -> int:
        """Remove all cached files.

        Returns:
            Number of files deleted.
        """
        count = 0
        with self._lock:
            self._memory_cache.clear()
            for path in self.cache_dir.iterdir():
                if path.is_file():
                    try:
                        path.unlink()
                        count += 1
                    except OSError as e:
                        logger.warning("Failed to delete %s: %s", path, e)
        logger.info("Cleared %d cached files", count)
        return count

    def size(self) -> int:
        """Count the number of cached files.

        Returns:
            Number of files in the cache directory.
        """
        with self._lock:
            return sum(1 for p in self.cache_dir.iterdir() if p.is_file())
