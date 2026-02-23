import os
import logging
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv('DB_BACKUP_BUCKET', 'vs-voice-dev-db-backups')
S3_REGION = os.getenv('AWS_REGION', 'eu-west-1')

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
DB_PATH = _project_root / "data" / "voice-ai.db"


def list_backups(limit: int = 10) -> list:
    """List available database backups from S3, sorted by date (newest first)."""
    try:
        s3_client = boto3.client('s3', region_name=S3_REGION)
        
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        
        if 'Contents' not in response:
            logger.warning(f"No backups found in bucket {S3_BUCKET}")
            return []
        
        # Sort by LastModified, newest first
        backups = sorted(
            response['Contents'],
            key=lambda x: x['LastModified'],
            reverse=True
        )
        
        return backups[:limit]
        
    except ClientError as e:
        logger.error(f"Failed to list backups from S3: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error listing backups: {e}")
        return []


def get_latest_backup() -> Optional[str]:
    """Get the S3 key of the latest database backup."""
    backups = list_backups(limit=1)
    
    if not backups:
        return None
    
    return backups[0]['Key']


def download_backup_from_s3(s3_key: str, download_path: Path) -> bool:
    """Download a specific backup from S3."""
    try:
        s3_client = boto3.client('s3', region_name=S3_REGION)
        
        logger.info(f"Downloading backup from s3://{S3_BUCKET}/{s3_key}")
        s3_client.download_file(S3_BUCKET, s3_key, str(download_path))
        
        logger.info(f"Successfully downloaded backup to {download_path}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to download backup from S3: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error downloading backup: {e}")
        return False


def restore_latest_backup(backup_current: bool = True) -> bool:
    """
    Restore the latest database backup from S3.
    
    Args:
        backup_current: If True, backs up the current database before restoring
        
    Returns:
        bool: True if restore was successful, False otherwise
    """
    # Get latest backup
    latest_key = get_latest_backup()
    
    if not latest_key:
        logger.error("No backups available to restore")
        return False
    
    logger.info(f"Latest backup found: {latest_key}")
    
    # Backup current database if it exists and backup_current is True
    if backup_current and DB_PATH.exists():
        backup_timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = DB_PATH.parent / f"voice-ai_pre-restore_{backup_timestamp}.db"
        
        logger.info(f"Backing up current database to {backup_path}")
        try:
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"Current database backed up successfully")
        except Exception as e:
            logger.error(f"Failed to backup current database: {e}")
            return False
    
    # Download the backup
    temp_download_path = DB_PATH.parent / "voice-ai_restore_temp.db"
    
    if not download_backup_from_s3(latest_key, temp_download_path):
        return False
    
    # Replace current database with restored backup
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
        
        temp_download_path.rename(DB_PATH)
        logger.info(f"Database restored successfully from {latest_key}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to replace database file: {e}")
        # Try to clean up temp file
        if temp_download_path.exists():
            temp_download_path.unlink()
        return False


def restore_specific_backup(s3_key: str, backup_current: bool = True) -> bool:
    """
    Restore a specific database backup from S3.
    
    Args:
        s3_key: The S3 key of the backup to restore
        backup_current: If True, backs up the current database before restoring
        
    Returns:
        bool: True if restore was successful, False otherwise
    """
    logger.info(f"Restoring backup: {s3_key}")
    
    # Backup current database if it exists and backup_current is True
    if backup_current and DB_PATH.exists():
        backup_timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = DB_PATH.parent / f"voice-ai_pre-restore_{backup_timestamp}.db"
        
        logger.info(f"Backing up current database to {backup_path}")
        try:
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"Current database backed up successfully")
        except Exception as e:
            logger.error(f"Failed to backup current database: {e}")
            return False
    
    # Download the backup
    temp_download_path = DB_PATH.parent / "voice-ai_restore_temp.db"
    
    if not download_backup_from_s3(s3_key, temp_download_path):
        return False
    
    # Replace current database with restored backup
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
        
        temp_download_path.rename(DB_PATH)
        logger.info(f"Database restored successfully from {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to replace database file: {e}")
        # Try to clean up temp file
        if temp_download_path.exists():
            temp_download_path.unlink()
        return False
