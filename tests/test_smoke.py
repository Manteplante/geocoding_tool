"""The `make smoke` check.

Runs the whole real code path — registry -> config guards -> cache -> budget
-> batch -> geodataframe -> attribution — with only the outermost geopy call
stubbed. If the wiring is broken, this fails; no network, no cost.
"""

from __future__ import annotations

import pytest

from geocoding_tool import (
    build_query,
    geocode_dataframe,
    get_geocoder,
    to_geodataframe,
    write_attribution,
)
from geocoding_tool.budget import Budget
from tests.conftest import TOWNS

pytestmark = pytest.mark.smoke


class FakeLocation:
    def __init__(self, latitude, longitude, address):
        self.latitude = latitude
        self.longitude = longitude
        self.address = address
        self.raw = {"display_name": address}


@pytest.fixture
def stub_geopy(monkeypatch):
    """Replace the geopy client so the backend is real but offline."""
    calls = []

    def fake_geocode(query, **kwargs):
        calls.append((query, kwargs))
        hit = TOWNS.get(query.split(",")[0].strip().casefold())
        return FakeLocation(*hit) if hit else None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.geocode = fake_geocode

    monkeypatch.setattr("geocoding_tool.nominatim.geocoder.GeopyNominatim", FakeClient)
    return calls


def test_smoke_nominatim_end_to_end(monkeypatch, stub_geopy, sample_frame, cache):
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "smoke-test/1.0 (ci@example.com)")

    geocoder = get_geocoder(
        "nominatim",
        cache=cache,
        budget=Budget(limit=10),
        min_delay_seconds=0,  # the policy delay is asserted in test_registry
    )

    sample_frame["query"] = build_query(
        sample_frame, ["organizational_town", "district"], suffix="Norway"
    )
    out = geocode_dataframe(sample_frame, "query", geocoder, verbose=False)

    assert out["geo_error"].isna().all()
    assert out["geo_provider"].unique().tolist() == ["nominatim"]

    gdf = to_geodataframe(out)
    assert len(gdf) == 3
    assert gdf.crs.to_string() == "EPSG:4326"
    # Everything should land inside Norway's bounding box.
    assert gdf.geometry.x.between(4, 32).all()
    assert gdf.geometry.y.between(57, 72).all()

    assert len(stub_geopy) == 3
    assert geocoder.budget.spent == 3


def test_smoke_rerun_is_free(monkeypatch, stub_geopy, sample_frame, cache):
    """The second pass over the same data must cost zero provider calls."""
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "smoke-test/1.0 (ci@example.com)")
    sample_frame["query"] = sample_frame["organizational_town"]

    def run():
        geocoder = get_geocoder(
            "nominatim", cache=cache, budget=Budget(limit=10), min_delay_seconds=0
        )
        geocode_dataframe(sample_frame, "query", geocoder, verbose=False)
        return geocoder

    run()
    assert len(stub_geopy) == 3

    second = run()
    assert len(stub_geopy) == 3, "re-run should have been served entirely from cache"
    assert second.budget.spent == 0


def test_smoke_exports_attribution(tmp_path, monkeypatch, stub_geopy, cache):
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "smoke-test/1.0 (ci@example.com)")
    geocoder = get_geocoder("nominatim", cache=cache, min_delay_seconds=0)

    sidecar = write_attribution(tmp_path / "out.csv", geocoder)
    assert "ODbL" in sidecar.read_text(encoding="utf-8")
