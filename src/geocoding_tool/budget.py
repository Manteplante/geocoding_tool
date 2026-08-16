"""Hard cap on live provider calls per run.

This is the guard that makes an accidental "geocode the whole file with
Google" impossible. It counts *live* calls only — cache hits are free and
never touch it.
"""

from __future__ import annotations

from geocoding_tool.config import max_requests_per_run


class Budget:
    """Counts live provider calls and refuses to go past ``limit``."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = max_requests_per_run() if limit is None else limit
        if self.limit < 0:
            raise ValueError(f"budget limit must be >= 0, got {self.limit}")
        self.spent = 0

    @property
    def remaining(self) -> int:
        return max(self.limit - self.spent, 0)

    def spend(self, n: int = 1) -> None:
        """Record ``n`` live calls, or raise if that would exceed the cap."""
        from geocoding_tool.base import GeocodeBudgetExceeded

        if self.spent + n > self.limit:
            raise GeocodeBudgetExceeded(
                f"request budget exhausted: {self.spent}/{self.limit} calls "
                f"already used. Raise MAX_REQUESTS_PER_RUN if this is "
                f"intentional, or clear fewer rows per run."
            )
        self.spent += n

    def __repr__(self) -> str:
        return f"Budget(spent={self.spent}, limit={self.limit})"
