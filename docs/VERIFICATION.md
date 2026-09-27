# Verification record

Verified on this workspace with Python 3.12.14. Exact installed Python dependencies are in `requirements.lock`.

## Public deployment verification — 28 September 2026

- [GitHub Actions run](https://github.com/cyash24f3/forecastlab/actions/runs/36344759092) passed: 36 automated tests and Docker image build.
- [Live application](https://yash-forecastlab.onrender.com) deployed on Render Free; health endpoint and primary interactive workflow verified.
- Public mutation restrictions were checked; full editing/admin features remain available when running the repository privately.
- Free demo instances can sleep and reset their temporary data. This is a portfolio deployment, not a production availability claim.
- PostgreSQL integration passed in the GitHub Actions service container.

## Completed locally

- **35 automated tests passed**, covering data validation, feature construction, recursive prediction, hand-calculated metrics, interval rank selection, holdout isolation, serialization, capacity/inventory arithmetic, API routes, artifact exports, zero-demand JSON handling, and interrupted-run recovery.
- Optional MLflow and S3 integration **contract tests passed with mocked clients**. No data was sent to live cloud services.
- Ruff checks passed for application code, tests, and scripts.
- Browser JavaScript syntax check passed.
- Browser smoke test passed: empty-state demo loading, training, series selection, comparison tables, six temporal folds, file download, capacity scenarios, invalid inventory horizon, malformed CSV rejection, valid CSV import, zero-demand retraining, all navigation pages, and mobile viewport checks.
- No browser JavaScript errors were observed during those checks.
- Dashboard screenshots were inspected at 1440px desktop and 390px mobile widths. Chart text scales with the available viewport; mobile pages do not overflow horizontally.
- Synthetic demo training and the public UCI dataset training completed, generating inspectable artifacts.
- A serialized model's predictions were reproduced and compared numerically with its exported forecasts.
- Exported holdout MAE and WAPE were independently recomputed in tests.
- Docker Compose configuration validation passed.
- Python wheel built successfully; packaged application modules and frontend assets were checked.
- Installed dependency consistency check passed (`pip check`).

## Not established by these checks

- **PostgreSQL runtime:** one integration test was skipped because no running test database was configured. This test subsequently passed in remote CI, as recorded above.
- **Docker image/runtime:** Docker was installed, but its daemon was unavailable. The image was not built or executed in this workspace. Compose syntax validation is not a container runtime test.
- **MLflow server and S3:** the implemented API contracts were tested with mocks, not a live tracking server or AWS credentials.
- **Production operation:** the Render demo does not establish authentication, high availability, sustained load capacity, an SLA, or real business impact.
- **Dependency warning:** Starlette's test client currently emits a deprecation warning about its httpx adapter. Tests pass; this is a future maintenance item, not an application failure.

See `EVALUATION.md` for actual statistical results. Passing software tests does not imply that the forecasts are accurate enough for operational decisions.
