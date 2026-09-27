from public_guard import protect
from forecastlab.api import create_app

app = protect(create_app(), "forecastlab", lambda p: p.startswith("/api/runs/") and p.endswith("/scenario"))
