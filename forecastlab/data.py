"""Strict daily-series contract; missing observations are never silently made zero."""
from io import BytesIO
import hashlib
import numpy as np
import pandas as pd

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 30000
MAX_SERIES = 12


def validate_csv(raw: bytes) -> tuple[pd.DataFrame, dict]:
    if len(raw) > MAX_BYTES:
        raise ValueError("CSV exceeds the 5 MiB limit.")
    try:
        df = pd.read_csv(BytesIO(raw), dtype={"series_id": str})
    except Exception as exc:
        raise ValueError("Could not read UTF-8 CSV. Expected date,series_id,value.") from exc
    if not {"date", "series_id", "value"}.issubset(df.columns):
        raise ValueError("Required columns: date, series_id, value.")
    df = df[["date", "series_id", "value"]].copy()
    if not 1 <= len(df) <= MAX_ROWS:
        raise ValueError(f"Provide 1–{MAX_ROWS:,} rows.")
    if df.isna().any().any():
        raise ValueError("Missing dates, series identifiers, or values are not allowed.")
    df["series_id"] = df.series_id.str.strip()
    if not df.series_id.str.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}").all():
        raise ValueError("Series IDs must be 1–64 letters, digits, spaces, underscores, dots or hyphens.")
    if df.series_id.nunique() > MAX_SERIES:
        raise ValueError(f"At most {MAX_SERIES} series are supported per dataset.")
    if not df.date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Dates must use YYYY-MM-DD, with one observation per day.")
    try:
        df["date"] = pd.to_datetime(df.date, format="%Y-%m-%d", errors="raise")
        df["value"] = pd.to_numeric(df.value, errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise ValueError("Dates must be valid and values must be numeric.") from exc
    if not np.isfinite(df.value).all() or (df.value < 0).any() or (df.value > 1e9).any():
        raise ValueError("Values must be finite, nonnegative, and no greater than 1 billion.")
    if df.duplicated(["series_id", "date"]).any():
        raise ValueError("Duplicate series/date keys found. Aggregate intentionally before importing.")
    df = df.sort_values(["series_id", "date"]).reset_index(drop=True)
    details = []
    for name, g in df.groupby("series_id", sort=True):
        if len(g) < 2 or not (np.diff(g.date.to_numpy(dtype="datetime64[D]")) == np.timedelta64(1, "D")).all():
            raise ValueError(f"{name}: daily dates must be contiguous. Resolve gaps before importing.")
        details.append({"series_id": name, "rows": len(g), "start": str(g.date.min().date()),
                        "end": str(g.date.max().date()), "zero_share": round(float((g.value == 0).mean()), 4)})
    quality = {"rows": len(df), "series_count": len(details), "series": details,
               "missing_values": 0, "duplicate_keys": 0, "missing_days": 0,
               "sha256": hashlib.sha256(raw).hexdigest(), "frequency": "daily",
               "warnings": ["Sales can understate demand during stockouts; this schema does not identify stockouts."]}
    if any(s["zero_share"] > .3 for s in details):
        quality["warnings"].append("Some series have many zeros. Intermittent-demand methods may be more suitable.")
    return df, quality


def make_demo(days: int = 560, seed: int = 42) -> pd.DataFrame:
    """Deterministic synthetic workloads, not observations from a real company."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end="2026-09-26", periods=days)
    t = np.arange(days)
    rows = []
    for name, base, trend, amplitude, noise in [
        ("Web traffic", 420, .20, 90, 28),
        ("Support requests", 130, .045, 38, 13),
        ("Daily orders", 240, .09, 60, 22),
    ]:
        weekly = amplitude * np.sin(2 * np.pi * dates.dayofweek.to_numpy() / 7)
        monthly = base * .05 * np.sin(2 * np.pi * t / 30.5)
        values = np.maximum(0, base + trend * t + weekly + monthly + rng.normal(0, noise, days))
        rows.extend({"date": d.strftime("%Y-%m-%d"), "series_id": name, "value": round(float(v))}
                    for d, v in zip(dates, values))
    return pd.DataFrame(rows)
