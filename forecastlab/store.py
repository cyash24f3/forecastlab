"""Portable SQL persistence for SQLite and PostgreSQL."""
from datetime import datetime, timezone
import uuid
import pandas as pd
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Float, Integer,
                        Text, ForeignKey, UniqueConstraint, select, func, text)

metadata = MetaData()
datasets = Table("datasets", metadata,
    Column("id", String(32), primary_key=True), Column("name", String(100), nullable=False),
    Column("source", String(30), nullable=False), Column("created_at", String(40)),
    Column("quality_json", Text, nullable=False))
observations = Table("observations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dataset_id", String(32), ForeignKey("datasets.id"), nullable=False),
    Column("series_id", String(64), nullable=False), Column("date", String(10), nullable=False),
    Column("value", Float, nullable=False), UniqueConstraint("dataset_id", "series_id", "date"))
runs = Table("runs", metadata,
    Column("id", String(32), primary_key=True), Column("dataset_id", String(32), ForeignKey("datasets.id")),
    Column("horizon", Integer), Column("status", String(20)), Column("message", Text),
    Column("created_at", String(40)), Column("summary_json", Text))


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, url):
        import json
        self.json = json
        self.engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
                                    pool_pre_ping=True)
        metadata.create_all(self.engine)

    def add_dataset(self, name, source, df, quality):
        identity = uuid.uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(datasets.insert().values(id=identity, name=name, source=source,
                         created_at=now(), quality_json=self.json.dumps(quality)))
            rows = df.copy()
            rows["date"] = rows.date.dt.strftime("%Y-%m-%d")
            rows["dataset_id"] = identity
            conn.execute(observations.insert(), rows.to_dict("records"))
        return identity

    def list_datasets(self):
        with self.engine.connect() as conn:
            records = conn.execute(select(datasets).order_by(datasets.c.created_at.desc())).mappings().all()
        return [self.dataset_dict(r) for r in records]

    def dataset_dict(self, row):
        result = dict(row)
        result["quality"] = self.json.loads(result.pop("quality_json"))
        return result

    def get_dataset(self, identity):
        with self.engine.connect() as conn:
            row = conn.execute(select(datasets).where(datasets.c.id == identity)).mappings().first()
        return self.dataset_dict(row) if row else None

    def frame(self, identity):
        with self.engine.connect() as conn:
            rows = conn.execute(select(observations.c.date, observations.c.series_id, observations.c.value)
                                .where(observations.c.dataset_id == identity)
                                .order_by(observations.c.series_id, observations.c.date)).mappings().all()
        df = pd.DataFrame(rows, columns=["date", "series_id", "value"])
        df["date"] = pd.to_datetime(df.date)
        return df

    def statistics(self, identity):
        q = select(observations.c.series_id, func.count().label("days"),
                   func.min(observations.c.date).label("start"), func.max(observations.c.date).label("end"),
                   func.sum(observations.c.value).label("total"), func.avg(observations.c.value).label("mean"),
                   func.min(observations.c.value).label("minimum"), func.max(observations.c.value).label("maximum"))
        q = q.where(observations.c.dataset_id == identity).group_by(observations.c.series_id)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(q).mappings()]

    def create_run(self, dataset_id, horizon):
        identity = uuid.uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(runs.insert().values(id=identity, dataset_id=dataset_id, horizon=horizon,
                         status="queued", message="Waiting for training", created_at=now()))
        return identity

    def update_run(self, identity, **fields):
        with self.engine.begin() as conn:
            conn.execute(runs.update().where(runs.c.id == identity).values(**fields))

    def list_runs(self):
        with self.engine.connect() as conn:
            records = conn.execute(select(runs).order_by(runs.c.created_at.desc())).mappings().all()
        return [self.run_dict(r) for r in records]

    def get_run(self, identity):
        with self.engine.connect() as conn:
            row = conn.execute(select(runs).where(runs.c.id == identity)).mappings().first()
        return self.run_dict(row) if row else None

    def run_dict(self, row):
        d = dict(row)
        d["summary"] = self.json.loads(d.pop("summary_json") or "null")
        return d

    def recover_interrupted(self):
        with self.engine.begin() as conn:
            conn.execute(runs.update().where(runs.c.status.in_(["queued", "running"]))
                         .values(status="failed", message="Server stopped during training. Start a new run."))

    def healthy(self):
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
