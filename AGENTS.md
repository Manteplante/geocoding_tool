# Agent notes: geocoding-tool

Context for any AI coding agent working in this repo. Read this before
touching `src/geocoding_tool/`, the `Makefile`, `.github/workflows/ci.yml`,
or `data/.gitignore`.

## What this repo is

A small geocoding library with two interchangeable backends — Nominatim/OSM
(free) and the Google Geocoding API (billable) — driven from notebooks. It
is used **two ways, and both must keep working**:

1. **As a template**: cloned directly. The example pipeline
   (`data/cleaner_example.ipynb` → `geocoding/geocoder_example.ipynb`) runs
   standalone against the 5-town `data/input/example.csv` via
   `make clean-notebook` / `make geocoder-notebook`.
2. **As a dependency**: `uv add git+<url>` from another project, then
   `from geocoding_tool import get_geocoder, geocode_dataframe, ...`. This is
   why the package lives under `src/geocoding_tool/` (an installable layout)
   rather than at repo root, and why `[project.scripts]` was deliberately
   removed from `pyproject.toml` — this is a library + notebooks, not a CLI.
   CI's `build` job exists specifically to catch this path breaking: it
   builds the wheel and imports it from a clean venv.

See `CHEATSHEET.md` for every command. See `README.md` for user-facing docs.

## Do not mindlessly refactor

Several things here look simplifiable but exist for a specific, tested
reason. Read the reason before changing them:

- **`BaseGeocoder.geocode()` never raises**, except `GeocodeBudgetExceeded`.
  A bad row becomes `GeocodeResult.error`, not an exception — this is what
  lets `geocode_dataframe` run to completion over hundreds of rows without
  one flaky Nominatim timeout aborting the whole batch. Don't "clean up" the
  try/except in `base.py` into something that propagates provider errors.
- **Failures are never cached** (`cache.py`; see
  `if result.error is None: self.cache.set(result)` in `base.py`). Caching a
  transient timeout would poison every future run for that query.
- **The budget cap (`budget.py`) is shared across both providers on
  purpose.** It's primarily a Google billing guard, but applies uniformly so
  `get_geocoder(...)` behaves the same regardless of provider. Don't
  special-case it to skip Nominatim, even though Nominatim is free.
- **Google requires `GOOGLE_GEOCODING_CONFIRM=1` in addition to an API
  key.** Deliberate friction against an accidental billable call — see
  `google/geocoder.py`. Don't make the API key alone sufficient to arm it.
- **Nominatim's `RateLimiter` floor is 1.1s, not 1.0s**, and `user_agent`
  rejects a fixed set of placeholder values (`config.PLACEHOLDER_USER_AGENTS`).
  Both enforce the OSM usage policy in code, not just in docs. Nominatim's
  `timeout`/`max_retries`/`error_wait_seconds` defaults are also looser than
  Google's on purpose — the public instance is free, shared infrastructure
  and slows down under load; that's expected, not a bug to "fix" by
  tightening timeouts back down.
- **`Makefile`'s `clean-notebook`/`geocoder-notebook` pass
  `--KernelManager.transport=ipc --KernelManager.ip=$(JUPYTER_RUNTIME_DIR)/kernel-ipc`.**
  Removing this reintroduces ipykernel's "running over TCP without
  encryption" warning (kernel comms go out over loopback TCP instead of a
  Unix socket). The absolute path via `$(CURDIR)` is required — a relative
  path here silently breaks, because the kernel subprocess and the nbconvert
  client resolve it against different working directories. Don't simplify
  this back to a bare `--KernelManager.transport=ipc`.
- **`data/.gitignore` tracks exactly one CSV** (`input/example.csv`) and
  ignores everything else under `data/`, including all of `output/`. Real
  input data (e.g. `dim_organizational_structure.csv`) is often large or
  sensitive and shouldn't be tracked; generated output is regenerable. Run
  `git add -n data/` before staging anything there if you're unsure what
  will actually get picked up.
- **`geopy` was chosen over the official `googlemaps` package
  deliberately** — `googlemaps` hadn't shipped since Jan 2023 as of when
  this was decided, despite being the "official" client. Don't swap it back
  without re-checking its status first.

## When you DO refactor

If you change behavior in `src/geocoding_tool/`, update all of these
together — not just the code:

1. **Tests** (`tests/`) — one file per module (`test_base.py`,
   `test_cache.py`, `test_budget.py`, `test_registry.py`, `test_batch.py`),
   plus `test_smoke.py` for the end-to-end wiring check. Every test runs
   fully offline — `tests/conftest.py`'s `block_network` fixture makes any
   real socket connection fail loudly. Keep it that way: mock at the
   `geopy` client boundary (see `FakeGeocoder` / `stub_geopy` in
   `conftest.py`), not lower.
2. **CI** (`.github/workflows/ci.yml`) — new dependency, new Python
   version, new verification step: it needs to show up here too. Don't
   remove the `build` job (see "What this repo is" above).
3. **`make smoke`** (`pytest -m smoke`) must keep passing in well under a
   second, fully offline. If your refactor changes the public shape of
   `geocode_dataframe` / `get_geocoder` / `to_geodataframe`, update
   `test_smoke.py` to match — it exists to catch wiring breaks, not to be
   skipped when it's inconvenient.
4. **`README.md` and `CHEATSHEET.md`** — any added/renamed/removed `make`
   target, env var, or public function needs both updated. Update this file
   too if you touch anything in the "do not mindlessly refactor" list above.
5. **Run `make ci` and `make smoke` before calling it done.** If you touched
   notebook execution, also run `make clean-notebook` /
   `make geocoder-notebook` (the latter costs a handful of free Nominatim
   calls) to confirm end-to-end behavior, not just unit tests.

## Quick orientation

- `base.py` — the contract (`GeocodeResult`, `BaseGeocoder`) both backends
  implement; owns cache/budget/error handling.
- `registry.py` — `get_geocoder("nominatim" | "google")`, the one switch
  point.
- `nominatim/`, `google/` — the two backends; same shape, different guards.
- `cache.py` — SQLite cache, keyed on `(provider, normalized_query)`.
- `budget.py` — hard cap on live provider calls per run.
- `batch.py` — DataFrame-level helpers (`build_query`, `geocode_dataframe`,
  `to_geodataframe`, `write_attribution`).
- `config.py` — env loading, defaults, attribution notices. Single source of
  truth for tunables (timeouts, retries, delays) — don't hardcode a magic
  number in a backend that belongs here.
- `geocoding/geocoder.ipynb`, `geocoding/geocoder_example.ipynb` — driver
  notebooks (real dataset / 5-town demo).
- `data/cleaner.ipynb`, `data/cleaner_example.ipynb` — cleaning notebooks
  (real dataset / 5-town demo).
- `scripts/new_notebook.py` — backs `make notebook`.
