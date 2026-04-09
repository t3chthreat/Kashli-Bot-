import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("kalshi_bot.db")
S3_KEY = "kalshi_bot.db"


def _client():
    import boto3
    return boto3.client("s3")


def restore_from_s3(bucket: str) -> bool:
    """Download DB from S3 if it exists. Returns True if restored."""
    if not bucket:
        return False
    try:
        s3 = _client()
        s3.download_file(bucket, S3_KEY, str(DB_PATH))
        logger.info("backup: restored %s from s3://%s/%s", DB_PATH, bucket, S3_KEY)
        return True
    except Exception as exc:
        # NoSuchKey or bucket not set — not an error, just no backup yet
        logger.info("backup: no S3 backup found (%s), starting fresh", exc)
        return False


def upload_to_s3(bucket: str) -> bool:
    """Upload current DB to S3. Returns True on success."""
    if not bucket:
        return False
    if not DB_PATH.exists():
        logger.warning("backup: %s does not exist, skipping upload", DB_PATH)
        return False
    try:
        s3 = _client()
        s3.upload_file(str(DB_PATH), bucket, S3_KEY)
        logger.info("backup: uploaded %s to s3://%s/%s", DB_PATH, bucket, S3_KEY)
        return True
    except Exception as exc:
        logger.error("backup: S3 upload failed: %s", exc)
        return False
