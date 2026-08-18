# geocoding-tool

Geocode a table of addresses with either **Nominatim (OpenStreetMap)** or the
**Google Geocoding API**, driven from a single notebook. Switching provider is
one string.

Usable two ways: clone it as a template, or add it to another project as a
dependency — `uv add git+https://github.com/<you>/geocoding_tool`.

Full command reference: [`CHEATSHEET.md`](CHEATSHEET.md). Contributing —
including an AI agent — start with [`AGENTS.md`](AGENTS.md).

## Quick start

```bash
make install-dev          # uv sync --group dev
make hooks                # install pre-commit hooks
cp .env.example .env      # then set NOMINATIM_USER_AGENT
make smoke                # offline end-to-end check
make geocoder-notebook    # runs the 5-town example end-to-end, live Nominatim
```

## Example pipeline

A small, real, self-contained demo: five Norwegian towns (Otta, Vinstra,
Lørenskog, Stryn, Bodø) in `data/input/example.csv`, deliberately messy
(stray whitespace, inconsistent casing, a trailing "kommune") so the cleaning
step does real work. This is the only CSV in `data/` that's tracked in git —
everything else in `data/input/` and `data/output/` is gitignored, since it's
either large/sensitive source data or regenerable output.

```bash
make clean-notebook    # data/cleaner_example.ipynb   -> data/output/example_clean.csv
make geocoder-notebook # geocoding/geocoder_example.ipynb -> data/output/example_geocoded.{csv,gpkg}
```

`make geocoder-notebook` runs `clean-notebook` first automatically. Both
execute the notebook end-to-end via `jupyter nbconvert --execute --inplace`
against the project's own kernel (see below) and write real output files —
no jupyter server, no browser.

Kernel communication is forced onto IPC (Unix domain sockets) rather than
Jupyter's default loopback TCP — the latter is what triggers ipykernel's
"running over TCP without encryption" warning, since anything else on the
host can in principle see that traffic. IPC sockets live under
`.cache/jupyter-runtime/` (gitignored) and are filesystem-permission gated,
so there's no network-visible channel at all. This only covers execution
through these `make` targets; a notebook opened directly in VS Code or
another Jupyter frontend uses that tool's own kernel launcher, outside this
repo's control.

## Providers

| | Nominatim (OSM) | Google Geocoding API |
|---|---|---|
| Cost | Free | 10,000 free calls/month, then $5.00 / 1,000 |
| Rate limit | 1 req/s, **enforced** at 1.1s | throttled to 5 req/s here |
| Required config | `NOMINATIM_USER_AGENT` | `GOOGLE_MAPS_API_KEY` **and** `GOOGLE_GEOCODING_CONFIRM=1` |
| Attribution | ODbL, required | Google Maps Platform ToS |

Both are `geopy` 2.5 backends, so they share one interface, one rate limiter
and one exception hierarchy. (The `googlemaps` package was rejected: its last
release was January 2023.)

### Nominatim usage policy

The [OSM policy](https://operations.osmfoundation.org/policies/nominatim/) is
enforced in code, not just documented:

- **Max 1 request/second** — every call goes through a `RateLimiter` with a
  1.1s floor, so bulk runs cannot burst.
- **A valid, unique User-Agent** — required at construction; the placeholder
  from `.env.example` is rejected.
- **Attribution** — `write_attribution()` drops the ODbL notice next to every
  export, and the notebook calls it on the way out.

### Google spend guards

Three things stand between you and a surprise bill:

1. **Explicit opt-in.** The API key alone does nothing; `GOOGLE_GEOCODING_CONFIRM=1`
   must also be set. A stray `PROVIDER = "google"` cannot bill you.
2. **Hard per-run cap.** `MAX_REQUESTS_PER_RUN` (default 200) raises
   `GeocodeBudgetExceeded` mid-run rather than continuing silently.
3. **Persistent cache.** Results are stored in `.cache/geocode.sqlite`, keyed by
   normalised query, so a re-run costs zero calls. Duplicate rows are also
   collapsed to one lookup before any call is made.

CI never sees a credential, so no workflow can make a billable call.

## Usage

```python
from geocoding_tool import build_query, geocode_dataframe, get_geocoder, load_env

load_env()
geocoder = get_geocoder("nominatim")  # or "google"

df["query"] = build_query(df, ["organizational_town"], suffix="Norway")
out = geocode_dataframe(df, "query", geocoder)
# -> geo_latitude, geo_longitude, geo_address, geo_provider, geo_error
```

Keep the query columns to *place* names. Folding an organisation column into
the query makes Nominatim miss — on the sample data, `["organizational_town",
"district"]` matched 0/5 rows against the live service while
`["organizational_town"]` matched 5/5. Every miss still costs a request, so
check a small slice before running the whole file.

Failures never raise: a bad row gets a `geo_error` string and the run
continues. The one exception is the budget cap, which is meant to stop you.

## Layout

```
src/geocoding_tool/
  base.py        contract: GeocodeResult, BaseGeocoder, cache/budget/error handling
  registry.py    get_geocoder("nominatim" | "google")
  nominatim/     OSM backend + usage-policy enforcement
  google/        Google backend + spend guards
  batch.py       build_query, geocode_dataframe, to_geodataframe, write_attribution
  cache.py       SQLite result cache
  budget.py      per-run call cap
  config.py      env loading, defaults, attribution notices
geocoding/geocoder.ipynb          the driver notebook
geocoding/geocoder_example.ipynb  self-contained 5-town Nominatim demo
data/cleaner.ipynb                the driver cleaning notebook
data/cleaner_example.ipynb        cleans data/input/example.csv
data/input/example.csv            the only CSV tracked in git
data/input/, data/output/         everything else here is gitignored
tests/                            fully offline suite
scripts/new_notebook.py           `make notebook` scaffolder
```

## Notebooks & kernel

`make notebook` scaffolds a new notebook — no Jupyter server, no browser. It
registers the project's `.venv` as a named Jupyter kernel (`register-kernel`,
idempotent — installs into `~/.local/share/jupyter/kernels/`), then prompts
you interactively for `data/` or `geocoding/` and a filename, and writes a
blank notebook wired to that kernel. Open the resulting file in your editor
or Jupyter frontend; the kernel is already registered and selectable.

```bash
make notebook           # prompts for folder + name, creates the file locally
make register-kernel    # just (re-)register the kernel, on its own
```

## Development

```bash
make help              # all targets, grouped
make check             # format + autofix before committing
make ci                # exactly what GitHub Actions runs
make test               # full offline suite
make smoke              # fast wiring check only
make clean-notebook     # run data/cleaner_example.ipynb end-to-end
make geocoder-notebook  # run geocoding/geocoder_example.ipynb end-to-end (live Nominatim)
make clean-cache        # drop cached results (forces fresh, billable lookups)
```

The test suite blocks sockets outright, so no test can reach the network or
spend quota. CI runs pre-commit (ruff + nbstripout), pytest on Python 3.12 and
3.14, and verifies the built wheel imports cleanly — that last job is the gate
on the git-dependency path being usable.

## Attribution

Output derived from Nominatim carries the OpenStreetMap ODbL notice; it is
written to `<output>.attribution.txt` automatically and must accompany
anything you publish.
