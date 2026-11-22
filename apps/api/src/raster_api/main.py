"""RAP-LM read-only API (Figure 5D). No training, inference or write route."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from raster_api.config import get_settings
from raster_api.db import get_engine
from raster_api.v1 import errors
from raster_api.v1.router import router

app = FastAPI(
    title="RAP-LM API",
    version="1.0.0",
    description=(
        "Read-only API of published pedestrian-collision risk results for the 43 districts "
        "of the province of Lima. Results are produced offline by the batch pipeline."
    ),
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
errors.install(app)
app.include_router(router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Operational probe; not a product resource."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except OperationalError:
        database = "unavailable"
    return {"status": "ok", "database": database, "environment": settings.app_env}
