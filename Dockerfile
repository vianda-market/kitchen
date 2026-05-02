# Kitchen FastAPI backend for GCP Cloud Run
# Copy this to the kitchen repo root.

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Create non-root user early
RUN adduser --disabled-password --gecos "" appuser

# System dependencies
# libvips: required by pyvips for image processing pipeline (image_event / image_backfill workers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libvips \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies as root (needs write access to pip)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy code and set ownership in one layer (avoids chown -R doubling layer size)
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8080

# Cloud Run uses port 8080; --host 0.0.0.0 is required (not localhost)
# RUN_MODE selector (see scripts/entrypoint.sh):
#   unset / "api"           → uvicorn (default, this image)
#   "image_event"           → Pub/Sub image-event listener stub
#   "image_backfill"        → image backfill worker stub
CMD ["bash", "scripts/entrypoint.sh"]
