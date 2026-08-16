"""DataFrame helpers."""

from __future__ import annotations

import pandas as pd

from geocoding_tool.batch import (
    build_query,
    geocode_dataframe,
    to_geodataframe,
    write_attribution,
)


def test_build_query_joins_columns(sample_frame):
    queries = build_query(sample_frame, ["organizational_town", "district"])
    assert queries.iloc[0] == "TVEDESTRAND, Agder Røde Kors"


def test_build_query_drops_null_placeholders():
    df = pd.DataFrame({"town": ["OSLO", "null", None], "region": ["Oslo", "Agder", ""]})
    queries = build_query(df, ["town", "region"])

    assert queries.tolist() == ["OSLO, Oslo", "Agder", ""]


def test_build_query_appends_suffix(sample_frame):
    queries = build_query(sample_frame, ["organizational_town"], suffix="Norway")
    assert queries.iloc[0] == "TVEDESTRAND, Norway"


def test_geocode_dataframe_adds_columns(sample_frame, fake_geocoder):
    sample_frame["query"] = sample_frame["organizational_town"]
    out = geocode_dataframe(sample_frame, "query", fake_geocoder, verbose=False)

    assert len(out) == 3
    for col in ("latitude", "longitude", "address", "provider", "error"):
        assert f"geo_{col}" in out.columns
    assert out["geo_latitude"].tolist() == [58.6228, 58.2497, 59.9133]
    assert out["geo_error"].isna().all()


def test_duplicate_queries_are_looked_up_once(fake_geocoder):
    df = pd.DataFrame({"query": ["OSLO", "OSLO", "LILLESAND", "OSLO"]})
    out = geocode_dataframe(df, "query", fake_geocoder, verbose=False)

    assert fake_geocoder.calls == ["OSLO", "LILLESAND"]
    assert out["geo_latitude"].tolist() == [59.9133, 59.9133, 58.2497, 59.9133]


def test_original_columns_are_preserved(sample_frame, fake_geocoder):
    sample_frame["query"] = sample_frame["organizational_town"]
    out = geocode_dataframe(sample_frame, "query", fake_geocoder, verbose=False)
    assert list(sample_frame.columns) == list(out.columns)[: len(sample_frame.columns)]


def test_to_geodataframe_uses_wgs84(sample_frame, fake_geocoder):
    sample_frame["query"] = sample_frame["organizational_town"]
    out = geocode_dataframe(sample_frame, "query", fake_geocoder, verbose=False)
    gdf = to_geodataframe(out)

    assert gdf.crs.to_string() == "EPSG:4326"
    assert gdf.geometry.iloc[0].x == 8.9316
    assert gdf.geometry.iloc[0].y == 58.6228


def test_to_geodataframe_drops_ungeocoded_rows(fake_geocoder):
    df = pd.DataFrame({"query": ["OSLO", "Nowhere At All"]})
    out = geocode_dataframe(df, "query", fake_geocoder, verbose=False)

    assert len(to_geodataframe(out)) == 1


def test_write_attribution_creates_sidecar(tmp_path, fake_geocoder):
    target = tmp_path / "geocoded.csv"
    sidecar = write_attribution(target, fake_geocoder)

    assert sidecar.name == "geocoded.csv.attribution.txt"
    assert "OpenStreetMap" in sidecar.read_text(encoding="utf-8")
