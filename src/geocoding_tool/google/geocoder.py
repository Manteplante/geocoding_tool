"""Google Geocoding API backend, via ``geopy``'s ``GoogleV3``.

Why geopy rather than the ``googlemaps`` package: ``geopy`` 2.5.0 (2026-07)
is actively maintained and gives both backends one interface, one rate
limiter and one exception hierarchy, whereas ``googlemaps`` 4.10.0 has not
shipped since January 2023. ``GoogleV3`` calls the same REST Geocoding API.

Billing, as of 2026: 10,000 free calls/month, then $5.00 per 1,000. Three
guards stand between you and an accidental bill:

1. ``GOOGLE_GEOCODING_CONFIRM=1`` must be set — the API key alone is not
   enough to arm this backend.
2. ``MAX_REQUESTS_PER_RUN`` caps live calls per run (see ``budget.py``).
3. Every result is cached, so re-runs cost nothing.
"""

from __future__ import annotations

from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import GoogleV3

from geocoding_tool.base import BaseGeocoder, GeocoderConfigError, GeocodeResult
from geocoding_tool.config import GOOGLE_MIN_DELAY_SECONDS, get_env


class GoogleGeocoder(BaseGeocoder):
    """Google Geocoding API, armed only when explicitly confirmed."""

    name = "google"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        confirm: bool | None = None,
        min_delay_seconds: float = GOOGLE_MIN_DELAY_SECONDS,
        timeout: float = 10.0,
        region: str | None = None,
        components: dict[str, str] | None = None,
        language: str | None = None,
        cache=None,
        budget=None,
    ) -> None:
        super().__init__(cache=cache, budget=budget)

        if confirm is None:
            confirm = get_env("GOOGLE_GEOCODING_CONFIRM") == "1"
        if not confirm:
            raise GeocoderConfigError(
                "The Google backend is billable and is disabled by default. "
                "Set GOOGLE_GEOCODING_CONFIRM=1 in .env (or pass "
                "confirm=True) to arm it. Pricing as of 2026: 10,000 free "
                "calls/month, then $5.00 per 1,000."
            )

        api_key = api_key or get_env("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise GeocoderConfigError(
                "GOOGLE_MAPS_API_KEY is not set. Copy .env.example to .env "
                "and add your key."
            )

        self.region = region if region is not None else get_env("GOOGLE_REGION")
        self.language = language or get_env("GOOGLE_LANGUAGE")
        # Restricting to a country cuts cross-continent false matches, which
        # otherwise burn quota on results you throw away.
        if components is None:
            country = get_env("GOOGLE_COMPONENT_COUNTRY") or self.region
            components = {"country": country} if country else None
        self.components = components

        self._client = GoogleV3(api_key=api_key, timeout=timeout)
        self._call = RateLimiter(
            self._client.geocode,
            min_delay_seconds=min_delay_seconds,
            max_retries=2,
            error_wait_seconds=5.0,
            swallow_exceptions=False,
        )

    def _geocode_one(self, query: str) -> GeocodeResult:
        kwargs: dict = {"exactly_one": True}
        if self.region:
            kwargs["region"] = self.region
        if self.components:
            kwargs["components"] = self.components
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
