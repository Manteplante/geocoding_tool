"""Environment-driven configuration, defaults and data attribution notices."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Attribution required when redistributing OpenStreetMap-derived coordinates.
ATTRIBUTION_OSM = (
    "Geocoding by Nominatim / OpenStreetMap. "
    "Data © OpenStreetMap contributors, available under the Open Database "
    "License (ODbL): https://www.openstreetmap.org/copyright"
)
ATTRIBUTION_GOOGLE = (
    "Geocoding by the Google Geocoding API. "
    "Results are subject to the Google Maps Platform Terms of Service: "
    "https://cloud.google.com/maps-platform/terms"
)
ATTRIBUTIONS = {"nominatim": ATTRIBUTION_OSM, "google": ATTRIBUTION_GOOGLE}

# Nominatim's usage policy caps clients at 1 request/second. We sit just above
# that so clock jitter can never push us over the line.
NOMINATIM_MIN_DELAY_SECONDS = 1.1
GOOGLE_MIN_DELAY_SECONDS = 0.2

# The public Nominatim instance is free, shared infrastructure and slows down
# under load -- a plain GeocoderTimedOut here doesn't mean the query is bad.
# These are looser than Google's (paid, dedicated infra) on purpose.
NOMINATIM_TIMEOUT_SECONDS = 20.0
NOMINATIM_MAX_RETRIES = 4
NOMINATIM_ERROR_WAIT_SECONDS = 8.0

GOOGLE_TIMEOUT_SECONDS = 10.0
GOOGLE_MAX_RETRIES = 2
GOOGLE_ERROR_WAIT_SECONDS = 5.0

# Rejected as a user agent: it identifies nobody, which is the whole point.
PLACEHOLDER_USER_AGENTS = {
    "",
    "geocoding-tool",
    "geocoding-tool/0.1 (you@example.com)",
    "specify_your_app_name_here",
}

DEFAULT_MAX_REQUESTS_PER_RUN = 400
DEFAULT_CACHE_PATH = Path(".cache/geocode.sqlite")


def load_env(dotenv_path: str | Path | None = None) -> None:
    """Load a ``.env`` file if present. Existing env vars always win."""
    load_dotenv(dotenv_path, override=False)


def get_env(name: str, default: str | None = None) -> str | None:
    """Read an env var, treating whitespace-only values as unset."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def max_requests_per_run() -> int:
    raw = get_env("MAX_REQUESTS_PER_RUN")
    if raw is None:
        return DEFAULT_MAX_REQUESTS_PER_RUN
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"MAX_REQUESTS_PER_RUN must be an integer, got {raw!r}"
        ) from exc


def cache_path() -> Path:
    return Path(get_env("GEOCODE_CACHE_PATH") or DEFAULT_CACHE_PATH)


def project_root() -> Path:
    """Repo root, so notebooks resolve ``data/`` the same from any cwd."""
    return Path(__file__).resolve().parents[2]
