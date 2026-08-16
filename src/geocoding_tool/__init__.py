"""Pluggable geocoding backends (Nominatim / Google) behind one interface.

Typical use from a notebook::

    from geocoding_tool import get_geocoder, geocode_dataframe, load_env

    load_env()
    geocoder = get_geocoder("nominatim")          # or "google"
    out = geocode_dataframe(df, "query", geocoder)
"""

from geocoding_tool.base import (
    BaseGeocoder,
    GeocodeBudgetExceeded,
    GeocoderConfigError,
    GeocodeResult,
    GeocodingError,
    UnknownProviderError,
)
from geocoding_tool.batch import (
    build_query,
    geocode_dataframe,
    to_geodataframe,
    write_attribution,
)
from geocoding_tool.budget import Budget
from geocoding_tool.cache import GeocodeCache
from geocoding_tool.config import (
    ATTRIBUTION_GOOGLE,
    ATTRIBUTION_OSM,
    load_env,
    project_root,
)
from geocoding_tool.registry import PROVIDERS, get_geocoder

__all__ = [
    "ATTRIBUTION_GOOGLE",
    "ATTRIBUTION_OSM",
    "PROVIDERS",
    "BaseGeocoder",
    "Budget",
    "GeocodeBudgetExceeded",
    "GeocodeCache",
    "GeocodeResult",
    "GeocoderConfigError",
    "GeocodingError",
    "UnknownProviderError",
    "build_query",
    "geocode_dataframe",
    "get_geocoder",
    "load_env",
    "project_root",
    "to_geodataframe",
    "write_attribution",
]
