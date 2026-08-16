"""Nominatim / OpenStreetMap backend.

The OSM usage policy is enforced here rather than merely documented:

* **1 request/second maximum** — a ``RateLimiter`` with a 1.1s floor wraps
  every call, so bulk runs cannot burst.
* **A valid, unique User-Agent** — required, and placeholder values are
  rejected at construction time.
* **Attribution** — ``ATTRIBUTION_OSM`` must be displayed alongside any
  published output; :func:`geocoding_tool.batch.write_attribution` writes it
  next to exported files.

Policy: https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim as GeopyNominatim

from geocoding_tool.base import BaseGeocoder, GeocoderConfigError, GeocodeResult
from geocoding_tool.config import (
    NOMINATIM_MIN_DELAY_SECONDS,
    PLACEHOLDER_USER_AGENTS,
    get_env,
)


class NominatimGeocoder(BaseGeocoder):
    """Free OSM geocoding, rate limited to stay inside the usage policy."""

    name = "nominatim"

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        min_delay_seconds: float = NOMINATIM_MIN_DELAY_SECONDS,
        timeout: float = 10.0,
        country_codes: str | None = None,
        language: str | None = None,
        cache=None,
        budget=None,
    ) -> None:
        super().__init__(cache=cache, budget=budget)

        user_agent = user_agent or get_env("NOMINATIM_USER_AGENT")
        if user_agent is None or user_agent.strip().casefold() in {
            p.casefold() for p in PLACEHOLDER_USER_AGENTS
        }:
            raise GeocoderConfigError(
                "Nominatim requires a unique User-Agent identifying your "
                "application (OSM usage policy). Set NOMINATIM_USER_AGENT in "
                ".env to something like "
                "'my-project/1.0 (you@example.com)' — the placeholder from "
                ".env.example is not accepted."
            )
        self.user_agent = user_agent
        self.country_codes = country_codes or get_env("NOMINATIM_COUNTRY_CODES")
        self.language = language or get_env("NOMINATIM_LANGUAGE")

        self._client = GeopyNominatim(user_agent=user_agent, timeout=timeout)
        # swallow_exceptions=False so BaseGeocoder.geocode owns error shaping
        # and every failure ends up in GeocodeResult.error with its real type.
        self._call = RateLimiter(
            self._client.geocode,
            min_delay_seconds=min_delay_seconds,
            max_retries=2,
            error_wait_seconds=5.0,
            swallow_exceptions=False,
        )

    def _geocode_one(self, query: str) -> GeocodeResult:
        kwargs: dict = {"exactly_one": True, "addressdetails": True}
        if self.country_codes:
            kwargs["country_codes"] = self.country_codes
        if self.language:
            kwargs["language"] = self.language

        location = self._call(query, **kwargs)
        if location is None:
            return GeocodeResult(
                query=query, provider=self.name, error="no match found"
            )
        return GeocodeResult(
            query=query,
            provider=self.name,
            latitude=location.latitude,
            longitude=location.longitude,
            address=location.address,
            raw=dict(location.raw) if location.raw else None,
        )
