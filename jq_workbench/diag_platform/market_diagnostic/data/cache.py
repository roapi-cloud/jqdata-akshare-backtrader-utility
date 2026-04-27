"""
Data Cache for Market Diagnostic System

Implements in-memory caching with date-based keys and 20-minute TTL.
Cache entries are stored in memory with timestamps for TTL tracking.

Requirements: 23.1, 23.2
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Default cache TTL in seconds (20 minutes)
DEFAULT_CACHE_TTL = 1200


@dataclass
class CacheEntry:
    """A single cache entry with value and expiration time."""
    value: Any
    timestamp: float


class DiagnosticDataCache:
    """
    In-memory cache for market diagnostic data.

    Stores data with date-based keys and 20-minute TTL by default.
    Entries older than TTL are considered expired and will be refreshed.

    Example:
        cache = DiagnosticDataCache()
        cache.set("index_series", "2024-01-15", data)
        data = cache.get("index_series", "2024-01-15")
    """

    def __init__(self, ttl: int = DEFAULT_CACHE_TTL) -> None:
        """
        Initialize the cache.

        Args:
            ttl: Time-to-live in seconds (default: 1200 = 20 minutes)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = ttl
        logger.debug(f"[DiagnosticDataCache] Initialized with TTL={ttl}s")

    def _make_key(self, key: str, date: str) -> str:
        """
        Create a cache key from key name and date.

        Args:
            key: Data identifier (e.g., "index_series", "breadth")
            date: Date string in 'YYYY-MM-DD' format

        Returns:
            Combined cache key
        """
        return f"{date}_{key}"

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if a cache entry has expired based on TTL."""
        age = time.time() - entry.timestamp
        return age > self._ttl

    def has(self, key: str, date: str) -> bool:
        """
        Check whether a non-expired cache entry exists.

        Args:
            key: Data identifier (e.g., "index_series", "breadth")
            date: Date string in 'YYYY-MM-DD' format

        Returns:
            True if entry exists and has not expired, False otherwise
        """
        cache_key = self._make_key(key, date)
        entry = self._cache.get(cache_key)

        if entry is None:
            logger.debug(f"[DiagnosticDataCache] Cache miss (key not found): {cache_key}")
            return False

        if self._is_expired(entry):
            logger.debug(f"[DiagnosticDataCache] Cache expired: {cache_key}")
            del self._cache[cache_key]
            return False

        logger.debug(f"[DiagnosticDataCache] Cache hit: {cache_key}")
        return True

    def get(self, key: str, date: str) -> Optional[Any]:
        """
        Retrieve cached data for the given key and date.

        Args:
            key: Data identifier
            date: Date string in 'YYYY-MM-DD' format

        Returns:
            The cached Python object, or None if not found or expired
        """
        cache_key = self._make_key(key, date)
        entry = self._cache.get(cache_key)

        if entry is None:
            logger.debug(f"[DiagnosticDataCache] Cache miss: {cache_key}")
            return None

        if self._is_expired(entry):
            logger.debug(f"[DiagnosticDataCache] Cache expired: {cache_key}")
            del self._cache[cache_key]
            return None

        age = time.time() - entry.timestamp
        logger.debug(f"[DiagnosticDataCache] Cache hit: {cache_key} (age: {age:.0f}s)")
        return entry.value

    def set(self, key: str, date: str, data: Any) -> None:
        """
        Store data in the cache under the given key and date.

        Args:
            key: Data identifier
            date: Date string in 'YYYY-MM-DD' format
            data: Python object to cache
        """
        cache_key = self._make_key(key, date)
        self._cache[cache_key] = CacheEntry(value=data, timestamp=time.time())
        logger.debug(f"[DiagnosticDataCache] Cached: {cache_key}")

    def clear(self, key: str, date: str) -> bool:
        """
        Remove a specific cache entry.

        Args:
            key: Data identifier
            date: Date string in 'YYYY-MM-DD' format

        Returns:
            True if entry was removed, False if it didn't exist
        """
        cache_key = self._make_key(key, date)
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(f"[DiagnosticDataCache] Cleared: {cache_key}")
            return True
        return False

    def clear_all(self) -> int:
        """
        Remove all cache entries.

        Returns:
            Number of entries removed
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[DiagnosticDataCache] Cleared all {count} entries")
        return count

    def clear_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of expired entries removed
        """
        removed = 0
        expired_keys = []

        for cache_key, entry in self._cache.items():
            if self._is_expired(entry):
                expired_keys.append(cache_key)

        for cache_key in expired_keys:
            del self._cache[cache_key]
            removed += 1

        if removed > 0:
            logger.info(f"[DiagnosticDataCache] Cleared {removed} expired entries")

        return removed

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total = len(self._cache)
        expired = sum(1 for e in self._cache.values() if self._is_expired(e))
        active = total - expired

        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": expired,
            "ttl_seconds": self._ttl,
        }
