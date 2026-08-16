"""The cache is what makes re-runs free."""

from __future__ import annotations

import pytest

from geocoding_tool.base import GeocodeResult
from geocoding_tool.budget import Budget
from geocoding_tool.cache import GeocodeCache, normalize_query
from tests.conftest import FakeGeocoder


def test_second_identical_query_makes_no_call(fake_geocoder):
    fake_geocoder.geocode("Tvedestrand")
    fake_geocoder.geocode("Tvedestrand")

    assert fake_geocoder.calls == ["Tvedestrand"]
    assert fake_geocoder.cache.hits == 1


def test_normalisation_collapses_case_and_whitespace():
    assert normalize_query("  Oslo   Sentrum ") == "oslo sentrum"
    assert normalize_query("OSLO") == normalize_query("oslo")


def test_failures_are_not_cached(fake_geocoder):
    fake_geocoder.fail_on = {"Oslo"}
    fake_geocoder.geocode("Oslo")
    fake_geocoder.fail_on = set()
    result = fake_geocoder.geocode("Oslo")

    assert result.ok is True
    assert fake_geocoder.calls == ["Oslo", "Oslo"]


def test_cache_is_per_provider(cache):
    nominatim = FakeGeocoder(cache=cache, budget=Budget(limit=10))
    google = FakeGeocoder(cache=cache, budget=Budget(limit=10))
    google.name = "google"

    nominatim.geocode("Oslo")
    google.geocode("Oslo")

    assert google.calls == ["Oslo"]
    assert len(cache) == 2


def test_persists_across_instances(tmp_path):
    path = tmp_path / "geocode.sqlite"
    first = FakeGeocoder(cache=GeocodeCache(path), budget=Budget(limit=10))
    first.geocode("Oslo")
    first.cache.close()

    second = FakeGeocoder(cache=GeocodeCache(path), budget=Budget(limit=10))
    result = second.geocode("Oslo")

    assert second.calls == []
    assert result.latitude == 59.9133
    second.cache.close()


@pytest.mark.parametrize(
    "payload",
    [
        "Oslo'); DROP TABLE geocode_cache; --",
        "' OR '1'='1",
        "Oslo'; UPDATE geocode_cache SET latitude = 0; --",
        'Oslo" OR ""="',
    ],
)
def test_query_text_cannot_inject_sql(cache, payload):
    """Query strings come from user data and must stay inert.

    Every statement in cache.py binds its values with ``?`` placeholders, so a
    payload round-trips as literal text and the table survives. This test is
    the guard against someone later rewriting a query with an f-string.
    """
    cache.set(GeocodeResult("Oslo", "nominatim", 59.9133, 10.7389, "Oslo, Norge"))
    cache.set(GeocodeResult(payload, "nominatim", 1.0, 2.0, "payload"))

    stored = cache.get("nominatim", payload)
    assert stored is not None
    assert stored.query == payload  # kept verbatim, not executed
    assert stored.latitude == 1.0

    untouched = cache.get("nominatim", "Oslo")
    assert untouched is not None, "table was dropped"
    assert untouched.latitude == 59.9133, "row was tampered with"
    assert len(cache) == 2


def test_provider_name_cannot_inject_sql(cache):
    cache.set(GeocodeResult("Oslo", "nominatim", 59.9133, 10.7389, "Oslo, Norge"))
    cache.set(
        GeocodeResult("Oslo", "nominatim'; DROP TABLE geocode_cache; --", 1.0, 2.0, "p")
    )

    assert len(cache) == 2
    assert cache.get("nominatim", "Oslo").latitude == 59.9133


def test_disabled_cache_never_serves_hits(fake_geocoder):
    fake_geocoder.cache = GeocodeCache(":memory:", enabled=False)
    fake_geocoder.geocode("Oslo")
    fake_geocoder.geocode("Oslo")

    assert fake_geocoder.calls == ["Oslo", "Oslo"]
