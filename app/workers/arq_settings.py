# app/workers/arq_settings.py
"""
ARQ worker configuration. Shared Redis queue for all ads platform tasks.

Run locally:  arq app.workers.arq_settings.WorkerSettings
Run in Docker: see docker-compose.yml
"""
from arq.connections import RedisSettings

from app.config.settings import settings
from app.workers.conversion_worker import upload_conversion


def _parse_redis_settings() -> RedisSettings:
    """Parse REDIS_URL into ARQ RedisSettings."""
    url = settings.REDIS_URL
    # arq RedisSettings.from_dsn handles redis://host:port and redis://:password@host:port
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    """ARQ WorkerSettings consumed by the arq CLI."""
    functions = [upload_conversion]
    redis_settings = _parse_redis_settings()
    max_tries = settings.ARQ_MAX_RETRIES
    job_timeout = settings.ARQ_JOB_TIMEOUT
    health_check_interval = 30
