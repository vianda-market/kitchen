# Kitchen FastAPI backend for GCP Cloud Run
# Copy this to the kitchen repo root.

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Create non-root user early
RUN adduser --disabled-password --gecos "" appuser

# Install dependencies as root (needs write access to pip)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy code and set ownership in one layer (avoids chown -R doubling layer size)
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8080

# Cloud Run uses port 8080; --host 0.0.0.0 is required (not localhost)
# Entry point: application.py at repo root, app = create_app()
CMD ["uvicorn", "application:app", "--host", "0.0.0.0", "--port", "8080"]
