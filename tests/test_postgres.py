"""Real PostgreSQL integration: enabled by POSTGRES_TEST_URL in CI."""
import os
import uuid
import pytest
from forecastlab.store import Store
from forecastlab.data import make_demo, validate_csv


@pytest.mark.skipif(not os.getenv('POSTGRES_TEST_URL'), reason='No PostgreSQL test server configured')
def test_postgres_round_trip():
    store = Store(os.environ['POSTGRES_TEST_URL'])
    frame, quality = validate_csv(make_demo(days=130).to_csv(index=False).encode())
    identity = store.add_dataset('CI '+uuid.uuid4().hex[:8], 'synthetic-test', frame, quality)
    assert len(store.frame(identity)) == 390
    assert len(store.statistics(identity)) == 3
    run = store.create_run(identity, 7)
    store.update_run(run, status='completed', message='DB round-trip only')
    assert store.get_run(run)['status'] == 'completed'
    store.engine.dispose()
