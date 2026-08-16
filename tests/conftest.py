"""Test fixtures.

Everything here is offline. ``block_network`` is autouse, so no test can
reach the internet or spend Google quota even by accident.
"""

from __future__ import annotations

import socket

import pandas as pd
import pytest

from geocoding_tool.base import BaseGeocoder, GeocodeResult
from geocoding_tool.budget import Budget
from geocoding_tool.cache import GeocodeCache

TOWNS = {
    "tvedestrand": (58.6228, 8.9316, "Tvedestrand, Agder, Norge"),
    "lillesand": (58.2497, 8.3776, "Lillesand, Agder, Norge"),
    "oslo": (59.9133, 10.7389, "Oslo, Norge"),
}


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Make any real socket connection fail loudly."""

    def _blocked(*args, **kwargs):
        raise RuntimeError("network access is not allowed in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test from a known-empty environment."""
    for var in (
        "NOMINATIM_USER_AGENT",
        "NOMINATIM_COUNTRY_CODES",
        "NOMINATIM_LANGUAGE",
        "GOOGLE_MAPS_API_KEY",
        "GOOGLE_GEOCODING_CONFIRM",
        "GOOGLE_REGION",
        "GOOGLE_COMPONENT_COUNTRY",
        "GOOGLE_LANGUAGE",
        "MAX_REQUESTS_PER_RUN",
        "GEOCODE_CACHE_PATH",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def cache():
    c = GeocodeCache(":memory:")
    yield c
    c.close()


class FakeGeocoder(BaseGeocoder):
    """Stands in for a provider. Records every live call it receives."""

    name = "nominatim"

    def __init__(self, *, fail_on=(), **kwargs):
        super().__init__(**kwargs)
        self.calls: list[str] = []
        self.fail_on = set(fail_on)

    def _geocode_one(self, query: str) -> GeocodeResult:
        self.calls.append(query)
        if query in self.fail_on:
            raise TimeoutError("provider timed out")
        hit = TOWNS.get(query.split(",")[0].strip().casefold())
        if hit is None:
            return GeocodeResult(
                query=query, provider=self.name, error="no match found"
            )
        lat, lon, address = hit
        return GeocodeResult(
            query=query,
            provider=self.name,
            latitude=lat,
            longitude=lon,
            address=address,
            raw={"place_id": query},
        )


@pytest.fixture
def fake_geocoder(cache):
    return FakeGeocoder(cache=cache, budget=Budget(limit=100))


@pytest.fixture
def sample_frame():
    return pd.DataFrame(
        {
            "local_branch": [
                "Tvedestrand Røde Kors",
                "Lillesand Røde Kors",
                "Oslo Røde Kors",
            ],
            "organizational_town": ["TVEDESTRAND", "LILLESAND", "OSLO"],
            "district": ["Agder Røde Kors", "Agder Røde Kors", "Oslo Røde Kors"],
        }
    )
