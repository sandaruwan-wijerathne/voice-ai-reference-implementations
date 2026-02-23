#!/usr/bin/env python3
"""
Manual database restore utility.

This script restores the database from the latest S3 backup or a specific backup.

Usage:
    # Restore latest backup:
    python -m utils.restore_db_cli
    
    # Restore latest backup without backing up current DB:
    python -m utils.restore_db_cli --no-backup
    
    # List available backups:
    python -m utils.restore_db_cli --list
    
    # Restore specific backup:
    python -m utils.restore_db_cli --backup-key "2024/01/16/10/voice-ai_2024-01-16_10-30-00.db"
"""

import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports when run directly
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db_restore import (
    restore_latest_backup,
    restore_specific_backup,
    list_backups
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_backup_info(backup: dict, index: int) -> str:
    """Format backup information for display."""
    key = backup['Key']
    last_modified = backup['LastModified']
    size_mb = backup['Size'] / (1024 * 1024)
    
    return f"  [{index}] {key}\n      Last Modified: {last_modified} | Size: {size_mb:.2f} MB"


def main():
    parser = argparse.ArgumentParser(
        description='Restore database from S3 backup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Restore latest backup:
    python -m utils.restore_db_cli
  
  List available backups:
    python -m utils.restore_db_cli --list
  
  Restore specific backup:
    python -m utils.restore_db_cli --backup-key "2024/01/16/10/voice-ai_2024-01-16_10-30-00.db"
  
  Restore without backing up current database:
    python -m utils.restore_db_cli --no-backup
        """
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available backups and exit'
    )
    
    parser.add_argument(
        '--backup-key',
        type=str,
        help='S3 key of specific backup to restore'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not backup current database before restoring'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Number of backups to list (default: 20)'
    )
    
    args = parser.parse_args()
    
    # List backups mode
    if args.list:
        logger.info(f"Fetching available backups (limit: {args.limit})...")
        backups = list_backups(limit=args.limit)
        
        if not backups:
            logger.warning("No backups found")
            return 1
        
        print(f"\n{'='*80}")
        print(f"Available backups ({len(backups)} found):")
        print(f"{'='*80}\n")
        
        for idx, backup in enumerate(backups, 1):
            print(format_backup_info(backup, idx))
            print()
        
        print(f"{'='*80}\n")
        print("To restore a specific backup, use:")
        print(f"  python -m utils.restore_db_cli --backup-key \"<S3_KEY>\"")
        print()
        
        return 0
    
    # Restore mode
    backup_current = not args.no_backup
    
    if args.backup_key:
        # Restore specific backup
        logger.info(f"Starting database restore from specific backup: {args.backup_key}")
        
        if backup_current:
            logger.warning("Current database will be backed up before restore")
        else:
            logger.warning("⚠️  Current database will NOT be backed up!")
        
        success = restore_specific_backup(args.backup_key, backup_current=backup_current)
    else:
        # Restore latest backup
        logger.info("Starting database restore from latest backup...")
        
        if backup_current:
            logger.warning("Current database will be backed up before restore")
        else:
            logger.warning("⚠️  Current database will NOT be backed up!")
        
        success = restore_latest_backup(backup_current=backup_current)
    
    if success:
        logger.info("✓ Database restore completed successfully!")
        return 0
    else:
        logger.error("✗ Database restore failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
