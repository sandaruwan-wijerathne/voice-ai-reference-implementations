FROM 157129355835.dkr.ecr.eu-west-1.amazonaws.com/docker-hub/library/python:3.12-slim

WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    cron \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
    poetry config installer.max-workers 10 && \
    poetry config installer.timeout 300 && \
    poetry lock --no-update 2>/dev/null || poetry lock && \
    poetry install --only main --no-interaction && \
    rm -rf $POETRY_CACHE_DIR

COPY . .

# Copy cron job file and make entrypoint executable
COPY scripts/backup-cron /etc/cron.d/db-backup-cron
RUN chmod 0644 /etc/cron.d/db-backup-cron && \
    chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint that starts both cron and the app
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
