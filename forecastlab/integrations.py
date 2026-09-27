"""Opt-in integrations. Nothing leaves the local machine unless explicitly configured."""
import os


def log_mlflow(run_id, summary, artifacts, dataset):
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        return None
    from mlflow import MlflowClient
    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("ForecastLab")
    experiment_id = experiment.experiment_id if experiment else client.create_experiment("ForecastLab")
    run = client.create_run(experiment_id, tags={"forecastlab.run_id": run_id,
                            "dataset.sha256": dataset["quality"]["sha256"], "dataset.source": dataset["source"]})
    identity = run.info.run_id
    client.log_param(identity, "horizon", summary["horizon"])
    client.log_param(identity, "selection_folds", 3)
    for key, value in summary["aggregate_holdout"].items():
        if value is not None:
            client.log_metric(identity, f"holdout_{key}", float(value))
    client.log_metric(identity, "holdout_coverage", summary["holdout_coverage"])
    for name in ("summary.json", "comparison.csv", "holdout.csv", "forecasts.csv", "manifest.json"):
        client.log_artifact(identity, str(artifacts / name))
    client.set_terminated(identity)
    return identity


def upload_s3(directory, bucket, prefix):
    import boto3
    client = boto3.client("s3")
    uploaded = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            key = f"{prefix.strip('/')}/{path.name}"
            client.upload_file(str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
            uploaded.append(f"s3://{bucket}/{key}")
    return uploaded
