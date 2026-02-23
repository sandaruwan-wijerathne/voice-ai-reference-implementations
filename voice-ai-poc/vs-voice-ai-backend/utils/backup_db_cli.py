#!/usr/bin/env python3
"""
Manual database backup utility.

This script triggers an immediate backup of the database to S3.

Usage:
    python -m utils.backup_db_cli
    # or from project root:
    python utils/backup_db_cli.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports when run directly
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db_backup import upload_db_to_s3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting manual database backup...")
    success = upload_db_to_s3()
    
    if success:
        logger.info("✓ Database backup completed successfully!")
        return 0
    else:
        logger.error("✗ Database backup failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

