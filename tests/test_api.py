import json
import pytest
from fastapi.testclient import TestClient
from forecastlab.api import create_app
from forecastlab.data import make_demo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('MLFLOW_TRACKING_URI', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with TestClient(create_app(tmp_path)) as client:
        yield client


def test_health_missing_and_static(client):
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/datasets/missing').status_code == 404
    assert client.get('/api/runs/missing').status_code == 404
    assert client.get('/').status_code == 200
    assert 'ForecastLab' in client.get('/').text
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/static/app.js').status_code == 200


def test_import_train_forecast_scenario_download(client):
    raw = make_demo(days=180).query("series_id == 'Daily orders'").to_csv(index=False)
    r = client.post('/api/datasets', files={'file':('input.csv',raw,'text/csv')}, data={'name':'Test workload'})
    assert r.status_code == 201
    identity = r.json()['id']
    assert client.get(f'/api/datasets/{identity}').json()['statistics'][0]['days'] == 180
    run = client.post('/api/runs', json={'dataset_id':identity,'horizon':7})
    assert run.status_code == 202
    run_id = run.json()['id']
    completed = client.get(f'/api/runs/{run_id}').json()
    assert completed['status'] == 'completed'
    for endpoint in ['forecast','holdout','comparison']:
        response=client.get(f'/api/runs/{run_id}/{endpoint}',params={'series_id':'Daily orders'})
        assert response.status_code == 200
        assert len(response.json()) == (4 if endpoint == 'comparison' else 7)
    assert client.get(f'/api/runs/{run_id}/forecast',params={'series_id':'bad'}).status_code == 404
    scenario=client.post(f'/api/runs/{run_id}/scenario',json={'series_id':'Daily orders','capacity':100})
    assert scenario.status_code == 200
    assert scenario.json()['capacity']['overloaded_days'] == 7
    assert client.post(f'/api/runs/{run_id}/scenario',json={'series_id':'Daily orders','capacity':-1}).status_code == 422
    assert client.post(f'/api/runs/{run_id}/scenario',json={'series_id':'Daily orders','lead_days':7,'review_days':7}).status_code == 422
    for kind in ['forecast','holdout','comparison','summary','manifest','input']:
        download = client.get(f'/api/runs/{run_id}/download/{kind}')
        assert download.status_code == 200 and 'attachment' in download.headers['content-disposition']
    assert client.get(f'/api/runs/{run_id}/download/models').status_code == 404
    assert client.get(f'/api/runs/{run_id}/download/summary').json()['horizon'] == 7


def test_demo_is_idempotent_and_bad_csv_is_clear(client):
    a=client.post('/api/datasets/demo').json()
    b=client.post('/api/datasets/demo').json()
    assert a['id'] == b['id']
    invalid=client.post('/api/datasets',files={'file':('bad.csv','foo,bar\n1,2','text/csv')})
    assert invalid.status_code == 422 and 'Required columns' in invalid.json()['detail']
    assert client.post('/api/runs',json={'dataset_id':a['id'],'horizon':100}).status_code == 422


def test_zero_series_api_does_not_emit_nan(client):
    df=make_demo(days=130).query("series_id == 'Daily orders'")
    df['value']=0
    identity=client.post('/api/datasets',files={'file':('zero.csv',df.to_csv(index=False),'text/csv')}).json()['id']
    run=client.post('/api/runs',json={'dataset_id':identity,'horizon':7}).json()['id']
    response=client.get(f'/api/runs/{run}/comparison',params={'series_id':'Daily orders'})
    assert response.status_code == 200
    assert all(row['wape'] is None for row in response.json())
    json.dumps(response.json(),allow_nan=False)


def test_interrupted_runs_marked_failed_on_restart(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        dataset=c.post('/api/datasets/demo').json()['id']
        identity=app.state.store.create_run(dataset,7)
    with TestClient(create_app(tmp_path)) as c:
        assert c.get(f'/api/runs/{identity}').json()['status']=='failed'
