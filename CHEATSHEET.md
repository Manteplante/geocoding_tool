# Cheat sheet

Every command worth knowing, in one place. See `README.md` for the full
explanation of *why*; see `AGENTS.md` if you're an AI agent working in this
repo.

## Setup

```bash
make install-dev          # uv sync --group dev (ruff, pytest, ipykernel, nbconvert, ...)
make install               # runtime deps only (uv sync --no-dev) -- what a consumer gets
make hooks                 # install the pre-commit git hooks
cp .env.example .env       # then fill in NOMINATIM_USER_AGENT at minimum
```

## Quality

```bash
make format          # ruff format . (rewrites code + notebooks in place)
make format-check    # ruff format --check .  (CI uses this, doesn't rewrite)
make lint            # ruff check .
make lint-fix        # ruff check --fix .
make check           # format + lint-fix, one shot, run before committing
```

## Tests

```bash
make test            # full offline suite (pytest)
make smoke           # just the wiring check: pytest -m smoke
make cov             # pytest --cov=geocoding_tool --cov-report=term-missing

uv run pytest -k budget                 # run tests matching a name
uv run pytest tests/test_cache.py -x    # one file, stop on first failure
uv run pytest -v                        # verbose, see every test name
```

The whole suite is offline by design (`tests/conftest.py` blocks real socket
connections outright) -- if a test needs the network, something's wrong.

## CI / build

```bash
make ci               # format-check + lint + test -- exactly what GitHub Actions runs
make build             # uv build -> dist/*.whl, dist/*.tar.gz
```

CI (`.github/workflows/ci.yml`) also builds the wheel and imports it in a
clean venv, to verify the git-dependency install path actually works.

## Notebooks & kernel

```bash
make register-kernel    # register the .venv as a Jupyter kernel (idempotent)
make notebook            # scaffold a new notebook: prompts for data/ or geocoding/, then a name
make clean-notebook      # run data/cleaner_example.ipynb end-to-end -> data/output/example_clean.csv
make geocoder-notebook   # run geocoding/geocoder_example.ipynb end-to-end (live Nominatim, ~5 free calls)
```

`geocoder-notebook` runs `clean-notebook` first automatically. Both execute
headlessly via `jupyter nbconvert --execute --inplace` over IPC (not TCP) --
no server, no browser.

## Cache & budget (from inside a notebook)

```python
geocoder = get_geocoder("nominatim")

len(geocoder.cache)  # how many results are cached, total
geocoder.cache.hits  # cache hits so far this session
geocoder.budget.spent  # live provider calls made so far this run
geocoder.budget.remaining  # calls left before GeocodeBudgetExceeded
geocoder.budget.limit = 1000  # raise the cap for this session without restarting
```

```bash
make clean-cache      # rm -rf .cache/ -- forces every query to hit the provider again
sqlite3 .cache/geocode.sqlite "select provider, query, latitude, longitude from geocode_cache;"
```

## Housekeeping

```bash
make clean     # remove dist/, build artefacts, __pycache__, .pytest_cache, .ruff_cache
make help       # every target, grouped
```

## Git / pre-commit

```bash
uv run pre-commit run --all-files    # run every hook now, not just on commit
git add -n data/                     # dry-run: see exactly what data/.gitignore would let through
```

`data/.gitignore` tracks exactly one CSV (`input/example.csv`); everything
else under `data/` — real input data and all generated output — is ignored.
`git add -n <path>` before staging anything in `data/` if you're unsure.

## Environment variables (`.env`, see `.env.example`)

| Variable | Purpose | Default |
|---|---|---|
| `NOMINATIM_USER_AGENT` | Required by OSM policy; placeholder values are rejected | *(none — must be set)* |
| `GOOGLE_MAPS_API_KEY` | Google Geocoding API key | *(none)* |
| `GOOGLE_GEOCODING_CONFIRM` | Must be `1` to arm the Google backend at all | `0` |
| `GOOGLE_REGION` | Two-letter country code to bias/restrict Google results | `no` |
| `MAX_REQUESTS_PER_RUN` | Hard cap on live provider calls, shared across providers | `200` |
| `GEOCODE_CACHE_PATH` | Where the SQLite result cache lives | `.cache/geocode.sqlite` |

## Consuming this repo from another project

```bash
uv add git+https://github.com/<you>/geocoding_tool
```

```python
from geocoding_tool import build_query, geocode_dataframe, get_geocoder, load_env

load_env()
geocoder = get_geocoder("nominatim")  # or "google"
df["query"] = build_query(df, ["town"], suffix="Norway")
out = geocode_dataframe(df, "query", geocoder)
```
