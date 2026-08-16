"""A failing row must become data, never a crash."""

from __future__ import annotations

from geocoding_tool.base import GeocodeResult


def test_provider_exception_becomes_error_field(fake_geocoder):
    fake_geocoder.fail_on = {"Oslo"}
    result = fake_geocoder.geocode("Oslo")

    assert result.error is not None
    assert "TimeoutError" in result.error
    assert result.ok is False


def test_batch_completes_despite_one_failure(fake_geocoder):
    fake_geocoder.fail_on = {"Lillesand"}
    results = fake_geocoder.geocode_many(["Tvedestrand", "Lillesand", "Oslo"])

    assert len(results) == 3
    assert [r.ok for r in results] == [True, False, True]


def test_no_match_is_reported_not_raised(fake_geocoder):
    result = fake_geocoder.geocode("Nowhere At All")
    assert result.error == "no match found"


def test_empty_query_costs_nothing(fake_geocoder):
    result = fake_geocoder.geocode("   ")

    assert result.error == "empty query"
    assert fake_geocoder.calls == []
    assert fake_geocoder.budget.spent == 0


def test_result_ok_property():
    assert GeocodeResult("q", "nominatim", 1.0, 2.0).ok is True
    assert GeocodeResult("q", "nominatim", error="boom").ok is False
