"""Data extraction helpers for stock_pool_filters."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


def _normalize_code(code: Any) -> str:
    return str(code).strip()


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _first_existing(config: Dict[str, Any], names: Iterable[str]) -> Any:
    for n in names:
        if n in config:
            return config[n]
    return None


def build_st_map(base_universe: List[str], config: Dict[str, Any]) -> Dict[str, bool]:
    raw = _first_existing(config, ["is_st_map", "st_map", "is_st_dict"])
    if isinstance(raw, dict):
        return {_normalize_code(k): bool(v) for k, v in raw.items()}

    raw_df = _first_existing(config, ["is_st_df", "st_df", "extras_is_st_df"])
    if isinstance(raw_df, pd.DataFrame) and not raw_df.empty:
        # Prefer explicit [code, is_st]
        if {"code", "is_st"}.issubset(raw_df.columns):
            return {
                _normalize_code(r["code"]): bool(r["is_st"])
                for _, r in raw_df.iterrows()
            }
        # AkShare ST list usually has column "代码"
        code_col = "代码" if "代码" in raw_df.columns else ("code" if "code" in raw_df.columns else None)
        if code_col:
            st_codes = set(raw_df[code_col].astype(str).tolist())
            return {
                _normalize_code(s): _normalize_code(s).split(".")[0] in st_codes
                for s in base_universe
            }

    provider = config.get("data_provider")
    if provider is not None and hasattr(provider, "get_extras"):
        try:
            df = provider.get_extras("is_st", base_universe)
            if isinstance(df, pd.DataFrame) and not df.empty:
                if {"code", "is_st"}.issubset(df.columns):
                    return {
                        _normalize_code(r["code"]): bool(r["is_st"])
                        for _, r in df.iterrows()
                    }
                code_col = "代码" if "代码" in df.columns else ("code" if "code" in df.columns else None)
                if code_col:
                    st_codes = set(df[code_col].astype(str).tolist())
                    return {
                        _normalize_code(s): _normalize_code(s).split(".")[0] in st_codes
                        for s in base_universe
                    }
        except Exception:
            return {}

    return {}


def build_name_map(base_universe: List[str], config: Dict[str, Any]) -> Dict[str, str]:
    raw = _first_existing(config, ["name_map", "display_name_map"])
    if isinstance(raw, dict):
        return {_normalize_code(k): str(v) for k, v in raw.items()}

    provider = config.get("data_provider")
    if provider is None or not hasattr(provider, "get_security_info"):
        return {}

    out: Dict[str, str] = {}
    for code in base_universe:
        try:
            info = provider.get_security_info(code)
        except Exception:
            continue
        if not info:
            continue
        name = info.get("display_name") or info.get("name")
        if name:
            out[_normalize_code(code)] = str(name)
    return out


def build_paused_map(base_universe: List[str], config: Dict[str, Any]) -> Dict[str, int]:
    raw = _first_existing(config, ["paused_map", "is_paused_map"])
    if isinstance(raw, dict):
        return {_normalize_code(k): int(v) for k, v in raw.items()}

    raw_df = _first_existing(config, ["paused_df", "is_paused_df"])
    if isinstance(raw_df, pd.DataFrame) and not raw_df.empty:
        if {"code", "paused"}.issubset(raw_df.columns):
            return {
                _normalize_code(r["code"]): int(r["paused"])
                for _, r in raw_df.iterrows()
            }
        if {"代码"}.issubset(raw_df.columns):
            paused_codes = set(raw_df["代码"].astype(str).tolist())
            return {
                _normalize_code(s): int(_normalize_code(s).split(".")[0] in paused_codes)
                for s in base_universe
            }

    provider = config.get("data_provider")
    if provider is not None and hasattr(provider, "get_extras"):
        try:
            df = provider.get_extras("is_paused", base_universe)
            if isinstance(df, pd.DataFrame) and not df.empty:
                if {"code", "paused"}.issubset(df.columns):
                    return {
                        _normalize_code(r["code"]): int(r["paused"])
                        for _, r in df.iterrows()
                    }
                code_col = "代码" if "代码" in df.columns else ("code" if "code" in df.columns else None)
                if code_col:
                    paused_codes = set(df[code_col].astype(str).tolist())
                    return {
                        _normalize_code(s): int(_normalize_code(s).split(".")[0] in paused_codes)
                        for s in base_universe
                    }
        except Exception:
            return {}

    return {}


def build_paused_history_map(config: Dict[str, Any]) -> Dict[str, List[int]]:
    raw = _first_existing(config, ["paused_history_map", "paused_series_map"])
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, List[int]] = {}
    for code, series in raw.items():
        if isinstance(series, list):
            out[_normalize_code(code)] = [int(v) for v in series]
    return out


def build_listing_date_map(base_universe: List[str], config: Dict[str, Any]) -> Dict[str, date]:
    raw = _first_existing(config, ["listing_date_map", "start_date_map"])
    if isinstance(raw, dict):
        out: Dict[str, date] = {}
        for k, v in raw.items():
            d = _to_date(v)
            if d is not None:
                out[_normalize_code(k)] = d
        return out

    provider = config.get("data_provider")
    if provider is None or not hasattr(provider, "get_security_info"):
        return {}

    out: Dict[str, date] = {}
    for code in base_universe:
        try:
            info = provider.get_security_info(code)
        except Exception:
            continue
        if not info:
            continue
        d = _to_date(info.get("start_date") or info.get("list_date"))
        if d is not None:
            out[_normalize_code(code)] = d
    return out


def build_price_map(config: Dict[str, Any]) -> Dict[str, float]:
    raw = _first_existing(config, ["price_map", "latest_price_map", "close_map"])
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[_normalize_code(k)] = float(v)
        except Exception:
            continue
    return out


def build_limit_map(config: Dict[str, Any], side: str) -> Dict[str, float]:
    if side not in {"high", "low"}:
        return {}
    keys = ["high_limit_map"] if side == "high" else ["low_limit_map"]
    raw = _first_existing(config, keys)
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[_normalize_code(k)] = float(v)
        except Exception:
            continue
    return out

