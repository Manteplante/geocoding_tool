"""DataFrame-level helpers: the layer the notebook actually calls."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from geocoding_tool.base import BaseGeocoder, GeocodeResult

WGS84 = "EPSG:4326"


def build_query(
    df: pd.DataFrame,
    columns: list[str],
    *,
    suffix: str | None = None,
    sep: str = ", ",
) -> pd.Series:
    """Join several columns into one query string per row.

    Blank and literal ``"null"`` values are dropped so a missing town does not
    produce a query with a dangling separator.
    """
    parts = []
    for col in columns:
        s = df[col].astype("string").str.strip()
        parts.append(s.mask(s.str.casefold().isin(["null", "nan", "none", ""])))

    stacked = pd.concat(parts, axis=1)
    joined = stacked.apply(
        lambda row: sep.join(v for v in row if pd.notna(v) and v), axis=1
    )

    if suffix:
        joined = joined.mask(joined != "", joined + sep + suffix)
    return joined.fillna("")


def results_to_frame(results: list[GeocodeResult], prefix: str = "geo") -> pd.DataFrame:
    """Turn results into a frame of ``{prefix}_*`` columns."""
    return pd.DataFrame(
        {
            f"{prefix}_latitude": [r.latitude for r in results],
            f"{prefix}_longitude": [r.longitude for r in results],
            f"{prefix}_address": [r.address for r in results],
            f"{prefix}_provider": [r.provider for r in results],
            f"{prefix}_error": [r.error for r in results],
        }
    )


def geocode_dataframe(
    df: pd.DataFrame,
    query_col: str,
    geocoder: BaseGeocoder,
    *,
    prefix: str = "geo",
    verbose: bool = True,
) -> pd.DataFrame:
    """Geocode ``query_col`` and return ``df`` with ``{prefix}_*`` columns added.

    Unique queries are looked up once each, then broadcast back to every row
    that shares them — on the sample organisational data that alone cuts 367
    rows to well under half as many calls.
    """
    queries = df[query_col].fillna("").astype(str)
    unique = queries[queries.str.strip() != ""].unique().tolist()

    if verbose:
        print(
            f"{len(df)} rows -> {len(unique)} unique queries "
            f"| provider={geocoder.name} "
            f"| budget={geocoder.budget.remaining} calls remaining"
        )

    lookup = {q: geocoder.geocode(q) for q in unique}
    results = [
        lookup.get(
            q, GeocodeResult(query=q, provider=geocoder.name, error="empty query")
        )
        for q in queries
    ]

    if verbose:
        failed = sum(1 for r in lookup.values() if r.error)
        print(
            f"cache hits: {geocoder.cache.hits} "
            f"| live calls: {geocoder.budget.spent} "
            f"| budget remaining: {geocoder.budget.remaining} "
            f"| failed queries: {failed}/{len(unique)}"
        )

    out = df.reset_index(drop=True).copy()
    return pd.concat([out, results_to_frame(results, prefix)], axis=1)


def to_geodataframe(
    df: pd.DataFrame, *, prefix: str = "geo", dropna: bool = True
) -> gpd.GeoDataFrame:
    """Attach WGS84 point geometry built from the geocoded columns."""
    lat, lon = f"{prefix}_latitude", f"{prefix}_longitude"
    frame = df.dropna(subset=[lat, lon]) if dropna else df
    return gpd.GeoDataFrame(
        frame.copy(),
        geometry=gpd.points_from_xy(frame[lon], frame[lat]),
        crs=WGS84,
    )


def write_attribution(path: str | Path, geocoder: BaseGeocoder) -> Path:
    """Write the provider's required attribution next to an exported file.

    Nominatim output carries an ODbL obligation; this makes honouring it the
    default rather than something you have to remember.
    """
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".attribution.txt")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(geocoder.attribution + "\n", encoding="utf-8")
    return sidecar
