#!/bin/bash
# Database Backup Cron Job Setup for ECS
# This script should be added to your ECS task definition as a scheduled task
# or run via AWS EventBridge scheduled rules

# Set working directory to the application root
cd /app || exit 1

# Load environment variables if needed
export PYTHONPATH=/app:$PYTHONPATH

# Run the backup using poetry
poetry run python utils/backup_db_cli.py

# Exit with the backup script's exit code
exit $?

