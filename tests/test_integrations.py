"""Integration contracts tested without sending data to external services."""
import sys
from types import SimpleNamespace
from forecastlab.integrations import log_mlflow, upload_s3


def test_tracking_disabled_without_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv('MLFLOW_TRACKING_URI', raising=False)
    assert log_mlflow('run', {}, tmp_path, {}) is None


def test_mlflow_logging_contract(monkeypatch, tmp_path):
    calls = []
    class Client:
        def __init__(self, tracking_uri):
            assert tracking_uri == 'http://tracking.example.invalid'
        def get_experiment_by_name(self, name):
            return None
        def create_experiment(self, name):
            return 'experiment'
        def create_run(self, experiment_id, tags):
            calls.append(('tags', tags))
            return SimpleNamespace(info=SimpleNamespace(run_id='remote-run'))
        def log_param(self, *args):
            calls.append(('parameter', args))
        def log_metric(self, *args):
            calls.append(('metric', args))
        def log_artifact(self, *args):
            calls.append(('artifact', args))
        def set_terminated(self, *args, **kwargs):
            calls.append(('terminated', args))
    monkeypatch.setitem(sys.modules, 'mlflow', SimpleNamespace(MlflowClient=Client))
    monkeypatch.setenv('MLFLOW_TRACKING_URI', 'http://tracking.example.invalid')
    summary = {'horizon':14,'aggregate_holdout':{'mae':2,'wape':None},'holdout_coverage':.75}
    dataset = {'quality':{'sha256':'hash'},'source':'synthetic-demo'}
    assert log_mlflow('local-run',summary,tmp_path,dataset) == 'remote-run'
    assert len([c for c in calls if c[0]=='artifact']) == 5
    assert len([c for c in calls if c[0]=='metric']) == 2
    assert calls[-1][0]=='terminated'


def test_s3_upload_contract(monkeypatch, tmp_path):
    calls=[]
    class Client:
        def upload_file(self, path, bucket, key, ExtraArgs):
            calls.append((path,bucket,key,ExtraArgs))
    monkeypatch.setitem(sys.modules, 'boto3', SimpleNamespace(client=lambda service:Client()))
    (tmp_path/'summary.json').write_text('{}')
    (tmp_path/'nested').mkdir()
    assert upload_s3(tmp_path,'chosen-bucket','/runs/example/') == ['s3://chosen-bucket/runs/example/summary.json']
    assert calls[0][1:]==('chosen-bucket','runs/example/summary.json',{'ServerSideEncryption':'AES256'})
