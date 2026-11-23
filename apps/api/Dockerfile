# Read-only API image (also runs Alembic migrations as the one-shot "migrate" service).
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api/src apps/api/src
RUN pip install --no-cache-dir . "sqlalchemy>=2.0,<3" "psycopg[binary]>=3.2,<4" "alembic>=1.13,<2"

COPY database database

RUN useradd --system --uid 10001 api
USER api
EXPOSE 8000
# WEB_CONCURRENCY sets the number of worker processes (stateless API; 4 by default).
CMD ["sh", "-c", "exec uvicorn raster_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-4}"]
