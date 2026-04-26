"""Data validation utilities."""

import pandas as pd


REQUIRED_OHLCV_COLS = {"open", "high", "low", "close", "volume"}


class DataValidator:
    """Validates OHLCV data for completeness and consistency."""

    @staticmethod
    def has_required_columns(df: pd.DataFrame) -> bool:
        """Check that all required OHLCV columns are present."""
        return REQUIRED_OHLCV_COLS.issubset(set(df.columns))

    @staticmethod
    def has_no_nulls(df: pd.DataFrame, cols: list[str] | None = None) -> bool:
        """Check that specified columns have no null values."""
        check_cols = cols if cols is not None else list(REQUIRED_OHLCV_COLS)
        return not df[check_cols].isnull().any().any()

    @staticmethod
    def price_positive(df: pd.DataFrame) -> bool:
        """Check that all price columns are positive."""
        for col in ["open", "high", "low", "close"]:
            if col in df.columns and (df[col] <= 0).any():
                return False
        return True

    @staticmethod
    def volume_non_negative(df: pd.DataFrame) -> bool:
        """Check that volume is non-negative."""
        if "volume" in df.columns:
            return (df["volume"] >= 0).all()
        return True

    @staticmethod
    def high_low_consistent(df: pd.DataFrame) -> bool:
        """Check that high >= low for all rows."""
        if "high" in df.columns and "low" in df.columns:
            return (df["high"] >= df["low"]).all()
        return True

    @staticmethod
    def validate(df: pd.DataFrame) -> list[str]:
        """Run all validations and return list of error messages."""
        errors = []

        if not DataValidator.has_required_columns(df):
            missing = REQUIRED_OHLCV_COLS - set(df.columns)
            errors.append(f"Missing columns: {missing}")

        if not DataValidator.has_no_nulls(df):
            errors.append("Data contains null values")

        if not DataValidator.price_positive(df):
            errors.append("Prices must be positive")

        if not DataValidator.volume_non_negative(df):
            errors.append("Volume must be non-negative")

        if not DataValidator.high_low_consistent(df):
            errors.append("High must be >= Low")

        return errors
