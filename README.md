# ForecastLab

**An end-to-end forecasting and decision support platform.** Import daily data, compare four forecasting methods, evaluate an untouched holdout, generate future predictions, and explore capacity or inventory scenarios.

Built as a general data science / ML engineering portfolio project. It works with nonnegative daily signals such as orders, traffic, rentals, or service requests.

![ForecastLab dashboard](docs/screenshots/overview.png)

## Start in five minutes

Requires **Python 3.11 or 3.12**. Python 3.12 is the tested version. No Node.js, AWS account, API key, or database server is required for the application.

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -c requirements.lock -e '.[dev]'
forecastlab demo
forecastlab serve
```

Open **http://127.0.0.1:8000**. The CLI prints a run summary when training finishes. Alternatively, start the server with an empty workspace, click **Load demo data**, then **Run forecast**.

If port 8000 is occupied: `forecastlab serve --port 8080`.

The `demo` command creates deterministic synthetic data and a complete 14-day training run. Local artifacts live in `data/`, which is excluded from Git. Repeating the CLI command creates another snapshot/run; the UI's Load demo action reuses an existing demo dataset.

### macOS XGBoost setup

If XGBoost reports `libomp.dylib` missing, install the OpenMP runtime with `brew install libomp`, then retry. The Docker image installs the Linux equivalent, `libgomp1`.

## What is implemented

- Strict CSV validation: daily frequency, nonnegative finite values, unique keys, contiguous dates, bounded upload size, and minimum history.
- SQL storage and summaries: SQLite by default; PostgreSQL supported with SQLAlchemy.
- Models: seasonal naive, recursive moving average, standardized Ridge regression, and XGBoost.
- Three rolling model-selection windows, two later calibration windows, and an untouched final holdout.
- MAE, RMSE, WAPE, bias, baseline comparison, and measured interval coverage.
- Nominal 80% empirical residual bands, with limitations shown in the UI.
- Recursive multi-step forecasts with model artifacts, normalized input snapshots, dependency versions, and source hashes.
- Responsive dashboard with series/run filters, charts, model comparison, validation feedback, source preview, and CSV/JSON exports.
- Capacity scenarios and periodic order-up-to inventory recommendations.
- FastAPI service and interactive OpenAPI documentation at `/docs`.
- Optional MLflow experiment logging and explicit S3 artifact upload.
- Docker Compose with PostgreSQL, automated tests, browser smoke checks, and a GitHub Actions workflow.

This is a working **local portfolio application**, not a claim of production readiness or guaranteed forecasting accuracy. Authentication, distributed training workers, and managed cloud deployment are not included.

## Use your own data

```csv
date,series_id,value
2025-01-01,Website visits,420
2025-01-02,Website visits,438
2025-01-03,Website visits,407
```

Use **Data workspace → Validate & import**, or:

```bash
forecastlab train path/to/data.csv --name 'Website demand' --horizon 14
```

- Dates must be `YYYY-MM-DD`, with a daily observation for every date in each series.
- Zero means an observed zero; missing observations must be resolved explicitly before importing.
- Series identifiers: 1–64 letters, digits, spaces, underscores, dots, or hyphens.
- Limit: 5 MiB, 30,000 rows, 12 series, values no greater than 1 billion.
- Minimum rows **per series**: `84 + 6 × horizon` (126 / 168 / 252 for 7 / 14 / 28 days).
- Extra CSV columns are ignored. No future weather, prices, promotion flags, or other covariates are modeled in v1.
- Series may have different dates; each is evaluated against its own most recent windows. Do not treat differently scaled or differently dated series as one business aggregate.

## Reproduce the public-data example

A transformed public dataset is included at `examples/bike-rentals.csv`, with citation, license, transformation details, retrieval time, and source archive hash in the adjacent JSON file.

```bash
forecastlab train examples/bike-rentals.csv \
  --name 'UCI bike rentals (2011–2012)' \
  --provenance examples/bike-rentals.source.json \
  --horizon 14
```

To independently re-download it:

```bash
python scripts/fetch_public_data.py
```

Source: Fanaee-T, H. (2013), [Bike Sharing, UCI Machine Learning Repository](https://doi.org/10.24432/C5W894), **CC BY 4.0**. We retain only daily dates and total rental counts and add a series identifier. The source's weather and same-day casual/registered counts are excluded. The latter sum to the target and would create leakage if used as future-known predictors.

The real-data holdout is deliberately retained even though performance is weak. See [the measured results and limitations](docs/EVALUATION.md). Forecast dates following the 2012 observations are a historical example, not current rental forecasts.

## How evaluation avoids leakage

```text
Time ──────────────────────────────────────────────────────────────────────→
Initial history | Select 1 | Select 2 | Select 3 | Cal 1 | Cal 2 | Holdout
                └── four candidates, three expanding-window origins ──┘
                                                   └── selected model ──┘
                                                                  └─ test
All observed history ─────────────────────────────────────────────→ refit
                                                                   Future
```

Each window is one forecast horizon long. Each fit expands to include previously observed windows. The selected model is fixed after the first three windows. Calibration errors come only from the next two windows. The final window is not used to choose a model or interval width.

For later steps within a forecast window, lag and rolling features use **predicted**, not actual future values. Once evaluation is complete, the selected model is refit on the full dataset to forecast unseen dates.

See [methodology](docs/METHODOLOGY.md) for exact features, formulas, model settings, and interval caveats.

## Dashboard walkthrough

1. **Forecast overview:** choose a dataset, series, and saved run; inspect observed demand, forecasts, intervals, and holdout WAPE.
2. **Model lab:** compare selection-fold scores, inspect actual/predicted holdout values, and audit the time boundaries.
3. **Decision planner:** enter capacity and a demand multiplier. Optionally set inventory position, lead time, review period, and safety stock.
4. **Data workspace:** upload data, inspect validation/provenance and raw observations, and review past runs.
5. **How it works:** read the statistical assumptions and operating limits.

The training-horizon selector controls the **next run**. Existing predictions retain the horizon of the saved run selected in the Run menu.

## API examples

```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/datasets/demo
curl http://127.0.0.1:8000/api/datasets
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"COPY_DATASET_ID","horizon":14}'
curl http://127.0.0.1:8000/api/runs/COPY_RUN_ID
curl 'http://127.0.0.1:8000/api/runs/COPY_RUN_ID/forecast?series_id=Daily%20orders'
```

Training returns `202 Accepted`; poll the run until `completed` or `failed`. Only one training task can execute at a time in the server process. Restarted, interrupted tasks are marked failed rather than shown as completed.

Reproduce forecasts from a trusted model saved by your own installation:

```bash
forecastlab predict COPY_RUN_ID
```

**Never load someone else's `models.joblib` file.** Joblib uses pickle and is not an untrusted model-upload format. The API intentionally does not accept model files.

## PostgreSQL and Docker

```bash
docker compose up --build
```

Open http://127.0.0.1:8000, then load and train the demo through the UI. Compose keeps PostgreSQL on an internal network and binds the application to localhost. The database password is a visible local-development default, not a deployment secret.

```bash
docker compose down               # stops services, preserves volumes
docker compose down --volumes     # deletes this project's database/artifacts
```

For an existing PostgreSQL server:

```bash
pip install -c requirements.lock -e '.[postgres]'
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/forecastlab'
forecastlab serve
```

Set environment variables in your shell; `.env.example` is a reference and is not loaded automatically. Use only one application worker. The local background-task architecture is intentionally simple; do not use `--workers` or multiple replicas with it.

## Optional MLflow and AWS

Neither integration is required to run the app, and no uploads happen automatically.

**MLflow:** install `.[tracking]`, point `MLFLOW_TRACKING_URI` at an existing tracking server, then train a run. The project logs parameters, aggregate diagnostic metrics, provenance tags, and result artifacts. Local runs remain usable if remote tracking fails. The optional client is `mlflow-skinny`; an MLflow server is a separate deployment.

```bash
pip install -c requirements.lock -e '.[tracking]'
export MLFLOW_TRACKING_URI='http://127.0.0.1:5000'
forecastlab demo
```

**S3:** install `.[cloud]`, configure your AWS CLI profile or execution role, and explicitly choose the destination bucket. This uploads the complete run, including normalized input and model artifacts; use only a bucket authorized for that data.

```bash
pip install -c requirements.lock -e '.[cloud]'
AWS_PROFILE=your-profile forecastlab sync-s3 COPY_RUN_ID \
  --bucket YOUR_BUCKET --prefix forecastlab
```

The uploader requests server-side AES256 encryption. Scope access to `s3:PutObject` on the intended bucket/prefix. No AWS resources are provisioned or billed by the local application itself.

## Tests and development

```bash
pytest -q
ruff check forecastlab tests scripts
```

Tests cover input rejection, zero-demand handling, hand-calculated metrics and planning outputs, feature construction, recursive baselines, holdout isolation, model serialization, API workflows, SQL persistence, and recovery of interrupted runs.

Optional real PostgreSQL integration:

```bash
POSTGRES_TEST_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/TEST_DB' pytest -q
```

Use a disposable test database. The test creates datasets/runs and does not delete your tables.

Optional browser smoke suite requires Node.js 20+:

```bash
npm install
npx playwright install chromium
# Terminal 1: choose a NEW disposable data directory each time
forecastlab --data-dir data/ui-test-new serve --port 8001
# Terminal 2
npm run test:ui
```

The browser suite expects an empty workspace, creates test data, and exercises demo training, filtering, downloads, validation failures, zero-demand training, planning, and mobile layouts. Screenshots go to `data/qa/`.

## Project map

```text
forecastlab/
  data.py          CSV validation and deterministic demo generator
  models.py        Features, models, recursive prediction, metrics
  pipeline.py      Temporal evaluation, calibration, refit, artifacts
  decisions.py     Capacity and inventory scenarios
  store.py         SQLAlchemy schema and database access
  service.py       Training orchestration and provenance
  integrations.py Optional MLflow client and S3 export
  api.py           REST API, background execution, static UI
  cli.py           Command-line workflows
  static/          Browser application, styles, example CSV
examples/          Public input data, attribution, reproducible results
scripts/           Public-data adapter and browser checks
sql/               Inspectable analytical SQL
tests/            Unit and API tests, optional PostgreSQL test
docs/             Architecture, methodology, evaluation, portfolio guide
```

See [architecture](docs/ARCHITECTURE.md), [portfolio/interview guide](docs/PORTFOLIO.md), and [verification record](docs/VERIFICATION.md).

Code is MIT licensed. The included UCI dataset has its own CC BY 4.0 attribution requirement; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
