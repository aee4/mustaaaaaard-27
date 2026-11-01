"""Local development only: provision private bucket. Never grant anonymous access."""

import time

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.integrations.storage import S3Storage

config = get_settings()
if config.environment == "production":
    raise SystemExit("Provision production buckets using your infrastructure tooling")
storage = S3Storage(config)
for attempt in range(30):
    try:
        storage.client.list_buckets()
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
try:
    storage.client.create_bucket(Bucket=config.s3_bucket)
except ClientError as exc:
    if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
        raise
try:
    storage.client.delete_bucket_policy(Bucket=config.s3_bucket)
except ClientError as exc:
    if exc.response["Error"]["Code"] != "NoSuchBucketPolicy":
        raise
print("Private development bucket ready")
