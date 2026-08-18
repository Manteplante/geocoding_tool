"""The hard per-run cap on live provider calls."""

from __future__ import annotations

import pytest

from geocoding_tool.base import GeocodeBudgetExceeded
from geocoding_tool.budget import Budget
from geocoding_tool.cache import GeocodeCache
from tests.conftest import FakeGeocoder


def test_cap_stops_the_run(cache):
    geocoder = FakeGeocoder(cache=cache, budget=Budget(limit=2))

    geocoder.geocode("Tvedestrand")
    geocoder.geocode("Lillesand")
    with pytest.raises(GeocodeBudgetExceeded, match="budget exhausted"):
        geocoder.geocode("Oslo")

    assert geocoder.calls == ["Tvedestrand", "Lillesand"]


def test_cache_hits_do_not_consume_budget(cache):
    geocoder = FakeGeocoder(cache=cache, budget=Budget(limit=1))

    geocoder.geocode("Oslo")
    geocoder.geocode("Oslo")
    geocoder.geocode("oslo")  # normalised to the same key

    assert geocoder.budget.spent == 1
    assert geocoder.budget.remaining == 0


def test_failures_still_consume_budget(cache):
    """A timeout costs a request even though nothing usable came back."""
    geocoder = FakeGeocoder(cache=cache, budget=Budget(limit=5), fail_on={"Oslo"})
    geocoder.geocode("Oslo")
    assert geocoder.budget.spent == 1


def test_limit_read_from_environment(monkeypatch):
    monkeypatch.setenv("MAX_REQUESTS_PER_RUN", "7")
    assert Budget().limit == 7


def test_default_limit_is_conservative():
    assert Budget().limit == 400


def test_zero_limit_blocks_every_live_call():
    geocoder = FakeGeocoder(cache=GeocodeCache(":memory:"), budget=Budget(limit=0))
    with pytest.raises(GeocodeBudgetExceeded):
        geocoder.geocode("Oslo")
