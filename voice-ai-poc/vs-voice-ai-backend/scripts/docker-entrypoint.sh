#!/bin/bash
# Docker entrypoint script
# Starts both cron daemon and the FastAPI application

set -e

echo "Starting database backup cron job..."

# Install crontab
crontab /app/scripts/backup-cron
echo "✓ Crontab installed"

# Start cron daemon in background
cron
echo "✓ Cron daemon started"

# Create log file for cron output
touch /var/log/db-backup.log
echo "✓ Log file created at /var/log/db-backup.log"

# Print crontab for verification
echo "Active crontab:"
crontab -l

echo ""
echo "Starting FastAPI application..."

# Start the FastAPI application (this blocks)
exec uvicorn app:app --host 0.0.0.0 --port 8000

