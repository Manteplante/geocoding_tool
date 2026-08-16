"""The cache is what makes re-runs free."""

from __future__ import annotations

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


def test_disabled_cache_never_serves_hits(fake_geocoder):
    fake_geocoder.cache = GeocodeCache(":memory:", enabled=False)
    fake_geocoder.geocode("Oslo")
    fake_geocoder.geocode("Oslo")

    assert fake_geocoder.calls == ["Oslo", "Oslo"]
