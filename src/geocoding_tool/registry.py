"""The single switch point between backends.

The notebook changes one string; everything else stays identical.
"""

from __future__ import annotations

from geocoding_tool.base import BaseGeocoder, UnknownProviderError

PROVIDERS = ("nominatim", "google")


def get_geocoder(provider: str, **kwargs) -> BaseGeocoder:
    """Build the backend named ``provider``.

    Args:
        provider: ``"nominatim"`` (free, 1 req/s) or ``"google"`` (billable,
            and disabled unless ``GOOGLE_GEOCODING_CONFIRM=1``).
        **kwargs: Passed through to the backend, e.g. ``cache=``, ``budget=``,
            ``user_agent=``, ``api_key=``, ``region=``.
    """
    key = (provider or "").strip().casefold()

    if key == "nominatim":
        from geocoding_tool.nominatim import NominatimGeocoder

        return NominatimGeocoder(**kwargs)

    if key == "google":
        from geocoding_tool.google import GoogleGeocoder

        return GoogleGeocoder(**kwargs)

    raise UnknownProviderError(
        f"unknown provider {provider!r}; expected one of {', '.join(PROVIDERS)}"
    )
