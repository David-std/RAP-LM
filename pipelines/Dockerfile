# Offline batch worker (profile "batch"): fusion, training, export and publication.
# Example:
#   docker compose --profile batch run --rm pipeline \
#     python -m pipelines.publication.publisher --dataset artifacts/datasets/fused-v1.0.0 \
#       --run artifacts/runs/fused-cnnlstm-2026.11-r1
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY requirements-pipeline.txt .
RUN pip install --no-cache-dir -r requirements-pipeline.txt \
 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.15.0
COPY pyproject.toml README.md ./
COPY apps/api/src apps/api/src
RUN pip install --no-cache-dir --no-deps .
COPY pipelines pipelines
COPY ml ml
COPY data/catalog data/catalog
CMD ["python", "-m", "pipelines.publication.publisher", "--help"]
