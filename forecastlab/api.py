from contextlib import asynccontextmanager
from pathlib import Path
import os
import threading
import logging
import time
import uuid
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from .data import MAX_BYTES, validate_csv, make_demo
from .store import Store
from .pipeline import validate_training
from .service import train_run
from .decisions import capacity_plan, inventory_plan

logger = logging.getLogger(__name__)


class TrainRequest(BaseModel):
    dataset_id: str
    horizon: int = Field(default=14, ge=7, le=28)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    series_id: str
    capacity: float = Field(default=500, ge=0, le=1e12)
    multiplier: float = Field(default=1, ge=.1, le=3)
    on_hand: float = Field(default=1000, ge=0, le=1e12)
    on_order: float = Field(default=0, ge=0, le=1e12)
    lead_days: int = Field(default=3, ge=1, le=28)
    review_days: int = Field(default=4, ge=0, le=28)
    safety_stock: float = Field(default=100, ge=0, le=1e12)


def create_app(data_dir=None, database_url=None):
    root = Path(data_dir or os.getenv("FORECASTLAB_DATA_DIR", "data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    store = Store(database_url or os.getenv("DATABASE_URL", f"sqlite:///{root / 'forecastlab.db'}"))
    training_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover_interrupted()
        yield
        store.engine.dispose()

    app = FastAPI(title="ForecastLab API", version="1.0.0", lifespan=lifespan,
                  description="Daily nonnegative forecasting, honest backtesting, and decision scenarios.")
    app.state.store = store
    app.state.data_dir = root

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.1f", request_id,
                    request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
        return response

    def require_dataset(identity):
        item = store.get_dataset(identity)
        if not item:
            raise HTTPException(404, "Dataset not found")
        return item

    def require_run(identity, complete=False):
        item = store.get_run(identity)
        if not item:
            raise HTTPException(404, "Run not found")
        if complete and item["status"] != "completed":
            raise HTTPException(409, "Run is not complete")
        return item

    def read_rows(identity, name, series=None):
        require_run(identity, True)
        frame = pd.read_csv(root / "runs" / identity / name, dtype={"series_id": str})
        if series is not None:
            frame = frame[frame.series_id == series]
            if frame.empty:
                raise HTTPException(404, "Series not found")
        return frame.astype(object).where(pd.notnull(frame), None).to_dict("records")

    @app.get("/api/health")
    def health():
        try:
            store.healthy()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/datasets")
    def list_datasets():
        return store.list_datasets()

    @app.post("/api/datasets/demo", status_code=201)
    def demo():
        # Idempotent creation makes the first-run action safe to repeat.
        for item in store.list_datasets():
            if item["source"] == "synthetic-demo":
                return item
        df, quality = validate_csv(make_demo().to_csv(index=False).encode())
        identity = store.add_dataset("Demo · digital demand", "synthetic-demo", df, quality)
        return store.get_dataset(identity)

    @app.post("/api/datasets", status_code=201)
    async def upload(file: UploadFile = File(...), name: str = Form("Imported daily data")):
        raw = await file.read(MAX_BYTES + 1)
        await file.close()
        if not name.strip() or len(name.strip()) > 100:
            raise HTTPException(422, "Dataset name must be 1–100 characters")
        try:
            df, quality = validate_csv(raw)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        identity = store.add_dataset(name.strip(), "user-upload", df, quality)
        return store.get_dataset(identity)

    @app.get("/api/datasets/{identity}")
    def dataset(identity: str):
        item = require_dataset(identity)
        return {**item, "statistics": store.statistics(identity)}

    @app.get("/api/datasets/{identity}/history")
    def history(identity: str, series_id: str = Query(...), limit: int = Query(90, ge=7, le=2000)):
        require_dataset(identity)
        df = store.frame(identity)
        g = df[df.series_id == series_id].tail(limit).copy()
        if g.empty:
            raise HTTPException(404, "Series not found")
        g["date"] = g.date.dt.strftime("%Y-%m-%d")
        return g.to_dict("records")

    @app.get("/api/runs")
    def list_runs():
        return store.list_runs()

    @app.post("/api/runs", status_code=202)
    def train(body: TrainRequest, background: BackgroundTasks):
        require_dataset(body.dataset_id)
        try:
            validate_training(store.frame(body.dataset_id), body.horizon)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not training_lock.acquire(blocking=False):
            raise HTTPException(409, "Another training run is active. Wait for it to finish.")
        try:
            identity = store.create_run(body.dataset_id, body.horizon)
        except Exception:
            training_lock.release()
            raise
        def task():
            try:
                train_run(store, root, identity)
            finally:
                training_lock.release()
        background.add_task(task)
        return store.get_run(identity)

    @app.get("/api/runs/{identity}")
    def run(identity: str):
        return require_run(identity)

    @app.get("/api/runs/{identity}/forecast")
    def forecast(identity: str, series_id: str = Query(...)):
        return read_rows(identity, "forecasts.csv", series_id)

    @app.get("/api/runs/{identity}/comparison")
    def comparison(identity: str, series_id: str = Query(...)):
        return read_rows(identity, "comparison.csv", series_id)

    @app.get("/api/runs/{identity}/holdout")
    def holdout(identity: str, series_id: str = Query(...)):
        return read_rows(identity, "holdout.csv", series_id)

    @app.post("/api/runs/{identity}/scenario")
    def scenario(identity: str, body: ScenarioRequest):
        rows = read_rows(identity, "forecasts.csv", body.series_id)
        try:
            return {"capacity": capacity_plan(rows, body.capacity, body.multiplier),
                    "inventory": inventory_plan(rows, body.on_hand, body.on_order, body.lead_days,
                                                 body.review_days, body.safety_stock, body.multiplier)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/runs/{identity}/download/{kind}")
    def download(identity: str, kind: str):
        require_run(identity, True)
        allowed = {"forecast": "forecasts.csv", "holdout": "holdout.csv", "comparison": "comparison.csv",
                   "summary": "summary.json", "manifest": "manifest.json", "input": "input.csv"}
        if kind not in allowed:
            raise HTTPException(404, "Unknown artifact")
        path = root / "runs" / identity / allowed[kind]
        return FileResponse(path, filename=f"forecastlab-{identity[:8]}-{path.name}")

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app
