"""The contract every geocoding backend satisfies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from geocoding_tool.budget import Budget
from geocoding_tool.cache import GeocodeCache


class GeocodingError(Exception):
    """Base class for every error this package raises."""


class GeocoderConfigError(GeocodingError):
    """A backend was asked to run without the configuration it requires."""


class GeocodeBudgetExceeded(GeocodingError):  # noqa: N818 - reads better than ...Error
    """The hard per-run cap on live provider calls was hit."""


class UnknownProviderError(GeocodingError):
    """A provider name that no backend is registered under."""


@dataclass(frozen=True)
class GeocodeResult:
    """One geocoding outcome. A miss or a failure is still a result."""

    query: str
    provider: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    raw: dict | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def as_dict(self) -> dict:
        return asdict(self)


class BaseGeocoder(ABC):
    """Shared cache / budget / error handling around a provider call.

    Subclasses implement :meth:`_geocode_one`, which may raise freely — the
    batching here converts a failure into a ``GeocodeResult`` carrying an
    ``error``, so one bad row can never abort a long run. The one exception
    is :class:`GeocodeBudgetExceeded`, which is deliberately allowed to
    propagate: hitting the spend cap should stop the run, not be logged.
    """

    name: str = "base"

    def __init__(
        self,
        *,
        cache: GeocodeCache | None = None,
        budget: Budget | None = None,
    ) -> None:
        self.cache = cache if cache is not None else GeocodeCache()
        self.budget = budget if budget is not None else Budget()

    @abstractmethod
    def _geocode_one(self, query: str) -> GeocodeResult:
        """Make a single live call to the provider."""

    def geocode(self, query: str) -> GeocodeResult:
        """Geocode one query, serving from cache when possible."""
        query = (query or "").strip()
        if not query:
            return GeocodeResult(query=query, provider=self.name, error="empty query")

        cached = self.cache.get(self.name, query)
        if cached is not None:
            return cached

        self.budget.spend()
        try:
            result = self._geocode_one(query)
        except GeocodeBudgetExceeded:
            raise
        except Exception as exc:  # a failed row is data, not a crash
            return GeocodeResult(
                query=query,
                provider=self.name,
                error=f"{type(exc).__name__}: {exc}",
            )

        # Failures are not cached: they are usually transient (timeout, 429)
        # and caching them would poison every later run.
        if result.error is None:
            self.cache.set(result)
        return result

    def geocode_many(self, queries: Iterable[str]) -> list[GeocodeResult]:
        """Geocode a sequence of queries in order."""
        return [self.geocode(q) for q in queries]

    @property
    def attribution(self) -> str:
        from geocoding_tool.config import ATTRIBUTIONS

        return ATTRIBUTIONS.get(self.name, "")
