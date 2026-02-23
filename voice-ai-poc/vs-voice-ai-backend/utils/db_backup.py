import os
import logging
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv('DB_BACKUP_BUCKET', 'vs-voice-dev-db-backups')
S3_REGION = os.getenv('AWS_REGION', 'eu-west-1')

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
DB_PATH = _project_root / "data" / "voice-ai.db"


def upload_db_to_s3() -> bool:
    """Upload the SQLite database to S3 with timestamp-based folder structure."""
    if not DB_PATH.exists():
        logger.warning(f"Database file not found at {DB_PATH}")
        return False
    
    try:
        s3_client = boto3.client('s3', region_name=S3_REGION)
        
        now = datetime.utcnow()
        timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
        s3_key = f"{now.strftime('%Y/%m/%d/%H')}/voice-ai_{timestamp}.db"
        
        logger.info(f"Uploading database to s3://{S3_BUCKET}/{s3_key}")
        s3_client.upload_file(
            str(DB_PATH),
            S3_BUCKET,
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'backup-timestamp': timestamp,
                    'backup-type': 'scheduled'
                }
            }
        )
        
        logger.info(f"Successfully uploaded database to S3: {s3_key}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to upload database to S3: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during database backup: {e}")
        return False
