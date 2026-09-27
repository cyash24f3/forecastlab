# Portfolio and interview guide

## Project description

ForecastLab is a daily forecasting and decision support application. It validates time-series data, compares simple baselines with Ridge regression and XGBoost, uses temporally separated selection/calibration/test windows, and serves forecasts through FastAPI and an interactive dashboard. Planning tools turn predictions into explicit capacity and inventory scenarios.

## Five-minute demo

1. Open the synthetic dataset and identify its source label.
2. Switch between demand series; explain that each has its own model and unit scale.
3. Open Model lab; distinguish selection scores from holdout results.
4. Explain why a simpler Ridge model can beat a boosted-tree model.
5. Point out a series whose interval coverage falls below the nominal target.
6. In the planner, reduce capacity and show how daily overflow changes.
7. Import a malformed CSV to demonstrate validation and a helpful error.
8. Switch to the public rental dataset and discuss the weak final holdout candidly.
9. Show `/docs`, an exported `holdout.csv`, and the reproducible test suite.

## Defensible resume wording

Use only after you have run the application and can explain or modify the implementation:

- “Developed a forecasting and decision support application using Python, SQL, FastAPI, and XGBoost, with rolling model selection, separate interval calibration, and untouched holdout evaluation.”
- “Implemented CSV validation, serialized model artifacts, interactive demand scenarios, and automated tests covering temporal leakage, API workflows, and zero-demand edge cases.”
- “Packaged a local forecasting service with Docker/PostgreSQL configuration and optional MLflow and S3 integrations.”

If you have not run Docker, PostgreSQL, MLflow, or AWS yourself, describe these as **implemented integrations/configuration**, not deployed operational systems.

Do not claim business savings, production users, real-world accuracy improvements from synthetic data, a production AWS deployment, or ownership of the UCI dataset. Do not translate WAPE into “accuracy.” Quantitative resume claims need the dataset, horizon, baseline, and evaluation period.

## Questions to prepare for

**Why not random train/test splits?** They mix temporal regimes and can expose future information. Real forecasts only have past data available.

**What makes your evaluation honest?** Selection, interval calibration, and final evaluation occur in separate chronological windows. Features use only past observations, and recursive prediction never substitutes future actuals.

**Why can XGBoost lose to Ridge?** Flexible models do not automatically generalize better. Trees can struggle to extrapolate trends, and the data may favor a simpler relationship. We keep the measured winner rather than force a preferred algorithm.

**Why is public-data performance poor?** The holdout errors are measured, but their causes are not established. The model omits exogenous information, and a short holdout can be unstable. Calendar effects or a changed demand regime are hypotheses to investigate, not proven explanations.

**Why does an 80% band cover fewer than 80% of holdout days?** It is an empirical estimate from a small, earlier calibration sample. Time dependence, distribution changes, lead-time differences, and refitting can invalidate coverage assumptions.

**Is SQL doing feature engineering?** SQL powers persistence and dashboard summaries. The training implementation computes lag/rolling features in Python; `sql/analysis.sql` includes equivalent inspectable trailing-window examples. Do not claim the model trains directly from a SQL feature store.

**What would you change for production?** Authentication, authorization, durable job queues, distributed locks, deployment monitoring, data retention/backups, and ongoing real-label evaluation.

**What did AI assistance contribute?** Be straightforward: this codebase was developed with AI assistance. Your contribution should include understanding, validating, adapting, and demonstrating the system. Extend a component yourself before relying on it heavily in interviews.

## Suggested personal extensions

Pick one bounded improvement, document the hypothesis, and evaluate on new time periods:

- Add a forecasting method and compare it through the same evaluator.
- Add a well-justified calendar feature with availability checks.
- Connect a personally collected dataset and document its quality.
- Add a direct multi-horizon model and test recursion-related error.
- Run the PostgreSQL container and optional MLflow server yourself.

A working extension you can explain is more useful than adding unsupported tool names to the resume.
