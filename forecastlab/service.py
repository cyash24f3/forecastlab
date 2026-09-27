import json
import logging
from .pipeline import run_pipeline
from .integrations import log_mlflow

logger = logging.getLogger(__name__)


def train_run(store, data_dir, identity):
    run = store.get_run(identity)
    output = data_dir / "runs" / identity
    try:
        store.update_run(identity, status="running", message="Preparing daily series")
        summary = run_pipeline(store.frame(run["dataset_id"]), run["horizon"], output,
                               lambda msg: store.update_run(identity, message=msg))
        dataset = store.get_dataset(run["dataset_id"])
        manifest = {"run_id": identity, "dataset_id": dataset["id"], "dataset_name": dataset["name"],
                    "source": dataset["source"], "quality": dataset["quality"]}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
        # Retain the exact normalized input snapshot with each model run.
        store.frame(run["dataset_id"]).to_csv(output / "input.csv", index=False)
        try:
            summary["mlflow_run_id"] = log_mlflow(identity, summary, output, dataset)
        except Exception:
            logger.exception("Optional MLflow logging failed")
            summary["tracking_warning"] = "MLflow logging failed; local artifacts are complete. Check server logs."
        (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
        store.update_run(identity, status="completed", message="Forecast and evaluation ready",
                         summary_json=json.dumps(summary, allow_nan=False))
    except Exception:
        logger.exception("Training failed for %s", identity)
        store.update_run(identity, status="failed", message="Training failed. Check server logs for details.")
