"""
策略文件扫描与分类模块

扫描指定目录下的所有策略文件（.txt 和 .py），自动识别策略类型，
提取策略元数据，并生成策略清单 JSON 文件。
"""

import os
import re
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class StrategyScanner:
    """策略扫描器，负责扫描、分类和提取策略元数据。"""

    STRATEGY_EXTENSIONS = {".txt", ".py"}

    JOINQUANT_PATTERNS = [
        re.compile(r"\bdef\s+initialize\s*\("),
        re.compile(r"\bdef\s+handle_data\s*\("),
        re.compile(r"\bdef\s+before_trading_start\s*\("),
        re.compile(r"\bdef\s+after_trading_end\s*\("),
        re.compile(r"\brun_daily\s*\("),
        re.compile(r"\bset_option\s*\("),
        re.compile(r"\bset_benchmark\s*\("),
        re.compile(r"\bfrom\s+jqdata\s+import"),
        re.compile(r"\bfrom\s+jqlib\."),
        re.compile(r"\bfrom\s+jqfactor\s+import"),
        re.compile(r"\bcontext\.portfolio\b"),
        re.compile(r"\border_target_value\s*\("),
        re.compile(r"\border_value\s*\("),
        re.compile(r"\bget_price\s*\("),
        re.compile(r"\bget_current_data\s*\("),
    ]

    BACKTRADER_PATTERNS = [
        re.compile(r"\bimport\s+backtrader\b"),
        re.compile(r"\bfrom\s+backtrader\s+import"),
        re.compile(r"class\s+\w+\(.*bt\.Strategy"),
        re.compile(r"class\s+\w+\(.*Strategy\).*:"),
        re.compile(r"\bself\.data\b"),
        re.compile(r"\bself\.broker\b"),
        re.compile(r"\bself\.cerebro\b"),
        re.compile(r"\bnext\s*\(\s*self\s*\)"),
        re.compile(r"\bnotify_order\s*\(\s*self"),
        re.compile(r"\bnotify_trade\s*\(\s*self"),
    ]

    REBALANCE_KEYWORDS = {
        "daily": [r"run_daily", r"每天", r"每日", r"daily", r"day"],
        "weekly": [r"run_weekly", r"每周", r"weekly", r"week"],
        "monthly": [r"run_monthly", r"每月", r"monthly", r"month"],
        "intraday": [r"run_daily.*minute", r"分钟", r"minute", r"intraday"],
    }

    STOCK_POOL_PATTERNS = [
        (re.compile(r"get_all_securities\s*\(\s*\[?\s*['\"](.*?)['\"]"), "sector"),
        (re.compile(r"index_stocks\s*\(\s*['\"](.*?)['\"]"), "index"),
        (re.compile(r"get_index_stocks\s*\(\s*['\"](.*?)['\"]"), "index"),
        (re.compile(r"(?:000300|000905|000852|399006)[.XSHGXSHE]*"), "index_code"),
        (re.compile(r"全A|全市场|all_stocks|全部A股"), "全市场"),
        (re.compile(r"小市值|小盘|micro.?cap|small.?cap|微盘"), "小市值"),
        (re.compile(r"大市值|大盘|large.?cap|蓝筹"), "大市值"),
        (re.compile(r"ETF|etf|基金"), "ETF"),
        (re.compile(r"北向|北上|港资|外资|hk_connect"), "北向资金"),
        (re.compile(r"创业板|GEM|ChiNext"), "创业板"),
        (re.compile(r"科创板|STAR"), "科创板"),
        (re.compile(r"中证500|ZZ500|000905"), "中证500"),
        (re.compile(r"沪深300|HS300|000300"), "沪深300"),
        (re.compile(r"高股息|红利|dividend|高股息率"), "高股息"),
        (re.compile(r"涨停|打板|连板|limit.?up"), "涨停"),
        (re.compile(r"期货|CTA|future|股指"), "期货"),
        (re.compile(r"债券|bond|国债|转债"), "债券"),
    ]

    STRATEGY_NAME_PATTERNS = [
        re.compile(r"#\s*标题[：:]\s*(.+)", re.MULTILINE),
        re.compile(r"#\s*title[：:]\s*(.+)", re.IGNORECASE | re.MULTILINE),
        re.compile(r"#\s*策略名称[：:]\s*(.+)", re.MULTILINE),
        re.compile(r"#\s*name[：:]\s*(.+)", re.IGNORECASE | re.MULTILINE),
    ]

    def __init__(self, strategy_dir: str, cache_dir: str):
        self.strategy_dir = Path(strategy_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "scan_cache.json"
        self._cache: Dict = self._load_cache()

    def _load_cache(self) -> Dict:
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"version": "1.0", "files": {}}

    def _save_cache(self):
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _compute_file_hash(self, file_path: Path) -> str:
        h = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except IOError:
            return ""
        return h.hexdigest()

    def _is_cached(self, file_path: Path, file_hash: str) -> Optional[Dict]:
        key = str(file_path)
        cached = self._cache.get("files", {}).get(key)
        if cached and cached.get("hash") == file_hash:
            return cached.get("metadata")
        return None

    def _update_cache(self, file_path: Path, file_hash: str, metadata: Dict):
        key = str(file_path)
        if "files" not in self._cache:
            self._cache["files"] = {}
        self._cache["files"][key] = {
            "hash": file_hash,
            "metadata": metadata,
            "updated_at": datetime.now().isoformat(),
        }

    def _remove_deleted_from_cache(self, current_files: set):
        if "files" not in self._cache:
            return
        to_remove = [k for k in self._cache["files"] if k not in current_files]
        for k in to_remove:
            del self._cache["files"][k]

    def _collect_strategy_files(self) -> List[Path]:
        files = []
        if not self.strategy_dir.exists():
            return files
        for ext in self.STRATEGY_EXTENSIONS:
            files.extend(self.strategy_dir.rglob(f"*{ext}"))
        files.sort()
        return files

    def _detect_strategy_type(self, content: str) -> str:
        jq_score = sum(1 for p in self.JOINQUANT_PATTERNS if p.search(content))
        bt_score = sum(1 for p in self.BACKTRADER_PATTERNS if p.search(content))

        if bt_score >= 2:
            return "backtrader"
        if jq_score >= 2:
            return "joinquant"
        if bt_score == 1 and jq_score == 0:
            return "backtrader"
        if jq_score == 1 and bt_score == 0:
            return "joinquant"
        return "other"

    def _extract_strategy_name(self, content: str, file_path: Path) -> str:
        for pattern in self.STRATEGY_NAME_PATTERNS:
            m = pattern.search(content)
            if m:
                name = m.group(1).strip().rstrip("#").strip()
                if name:
                    return name

        name_from_file = file_path.stem.strip()
        name_parts = re.split(r"\s+", name_from_file)
        if name_parts and re.match(r"^\d+$", name_parts[0]):
            name_parts = name_parts[1:]
        return " ".join(name_parts) if name_parts else file_path.name

    def _extract_rebalance_cycle(self, content: str) -> str:
        for cycle, patterns in self.REBALANCE_KEYWORDS.items():
            for p in patterns:
                if re.search(p, content, re.IGNORECASE):
                    return cycle
        return "unknown"

    def _extract_stock_pool(self, content: str) -> List[str]:
        pools = []
        seen = set()

        for pattern, label in self.STOCK_POOL_PATTERNS:
            matches = pattern.findall(content)
            for m in matches:
                if isinstance(m, tuple):
                    m = m[0]
                m = m.strip()
                if m and m not in seen:
                    seen.add(m)
                    pools.append(
                        m if label in ("index", "sector", "index_code") else label
                    )

        if not pools:
            pools = ["未识别"]
        return pools

    def _extract_author(self, content: str) -> str:
        m = re.search(r"#\s*作者[：:]\s*(.+)", content)
        if m:
            return m.group(1).strip().rstrip("#").strip()
        return "未知"

    def _extract_url(self, content: str) -> str:
        m = re.search(r"#\s*原文网址[：:]\s*(https?://\S+)", content)
        if m:
            return m.group(1).strip()
        return ""

    def get_strategy_metadata(self, file_path: str) -> Dict:
        fp = Path(file_path)
        if not fp.exists():
            return {
                "file_path": str(fp),
                "error": "File not found",
                "strategy_name": fp.stem,
                "strategy_type": "unknown",
            }

        file_hash = self._compute_file_hash(fp)
        cached = self._is_cached(fp, file_hash)
        if cached:
            return cached

        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except IOError:
            return {
                "file_path": str(fp),
                "error": "Cannot read file",
                "strategy_name": fp.stem,
                "strategy_type": "unknown",
            }

        strategy_type = self._detect_strategy_type(content)
        strategy_name = self._extract_strategy_name(content, fp)
        rebalance_cycle = self._extract_rebalance_cycle(content)
        stock_pool = self._extract_stock_pool(content)
        author = self._extract_author(content)
        url = self._extract_url(content)

        file_size = fp.stat().st_size
        line_count = content.count("\n") + 1

        metadata = {
            "strategy_name": strategy_name,
            "file_path": str(fp),
            "file_name": fp.name,
            "strategy_type": strategy_type,
            "rebalance_cycle": rebalance_cycle,
            "stock_pool": stock_pool,
            "author": author,
            "source_url": url,
            "file_size_bytes": file_size,
            "line_count": line_count,
            "file_hash": file_hash,
            "scanned_at": datetime.now().isoformat(),
        }

        self._update_cache(fp, file_hash, metadata)
        return metadata

    def scan_all_strategies(self) -> List[Dict]:
        files = self._collect_strategy_files()
        total = len(files)
        if total == 0:
            print("[StrategyScanner] No strategy files found.")
            return []

        print(f"[StrategyScanner] Found {total} strategy files. Scanning...")
        results = []
        current_file_paths = set(str(f) for f in files)

        for idx, fp in enumerate(files, 1):
            if idx % 50 == 0 or idx == total:
                progress = idx / total * 100
                print(f"  Progress: {idx}/{total} ({progress:.1f}%)")

            metadata = self.get_strategy_metadata(str(fp))
            results.append(metadata)

        self._remove_deleted_from_cache(current_file_paths)
        self._save_cache()

        type_counts = {}
        for r in results:
            t = r.get("strategy_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        print(f"[StrategyScanner] Scan complete. {total} files processed.")
        print(f"  Type distribution: {type_counts}")

        return results

    def load_cached_list(self) -> List[Dict]:
        if "files" not in self._cache:
            return []
        results = []
        for key, entry in self._cache["files"].items():
            meta = entry.get("metadata", {})
            fp = Path(key)
            if fp.exists():
                current_hash = self._compute_file_hash(fp)
                if current_hash == entry.get("hash"):
                    results.append(meta)
        return results

    def save_strategy_list(self, output_path: str):
        strategy_list = self.scan_all_strategies()

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "scan_time": datetime.now().isoformat(),
            "total_count": len(strategy_list),
            "type_distribution": {},
            "strategies": strategy_list,
        }

        for s in strategy_list:
            t = s.get("strategy_type", "unknown")
            summary["type_distribution"][t] = summary["type_distribution"].get(t, 0) + 1

        with open(output, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"[StrategyScanner] Strategy list saved to: {output}")
        return summary


def main():
    strategy_dir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"
    cache_dir = (
        r"E:\jqdata_akshare_backtrader_utility\strategy_to_factor_pipeline\cache"
    )
    output_path = (
        r"E:\jqdata_akshare_backtrader_utility\output\mappings\strategy_list.json"
    )

    scanner = StrategyScanner(strategy_dir=strategy_dir, cache_dir=cache_dir)

    cached = scanner.load_cached_list()
    if cached:
        print(f"[Main] Found {len(cached)} cached strategies.")

    summary = scanner.save_strategy_list(output_path)

    print(f"\n[Main] Summary:")
    print(f"  Total strategies: {summary['total_count']}")
    print(f"  Types: {summary['type_distribution']}")


if __name__ == "__main__":
    main()
