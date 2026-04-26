"""Custom exceptions for the signal pipeline."""


class InsufficientDataError(Exception):
    """Raised when market data does not meet the minimum length required by an indicator."""

    def __init__(
        self, required: int, actual: int, indicator: str | None = None
    ) -> None:
        self.required = required
        self.actual = actual
        self.indicator = indicator
        msg = (
            f"Indicator '{indicator}' requires at least {required} bars, "
            f"but only {actual} are available."
            if indicator
            else f"Insufficient data: need {required} bars, got {actual}."
        )
        super().__init__(msg)


class IndicatorCalculationError(Exception):
    """Raised when an indicator fails during computation."""

    def __init__(self, indicator: str, detail: str | None = None) -> None:
        self.indicator = indicator
        self.detail = detail
        msg = f"Indicator '{indicator}' calculation failed"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class DataAlignmentError(Exception):
    """Raised when data sources cannot be aligned (mismatched timestamps, assets, etc.)."""

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        msg = "Data alignment failed"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class FusionConflictError(Exception):
    """Raised when signal fusion encounters irreconcilable conflicts."""

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        msg = "Signal fusion conflict"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
