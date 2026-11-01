from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config

from app.core.config import Settings


class Storage(Protocol):
    def put(self, key: str, path: Path, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def sign(self, key: str, seconds: int) -> str: ...
    def ready(self) -> None: ...
    def old_keys(self, before: datetime) -> Iterator[str]: ...


class S3Storage:
    def __init__(self, settings: Settings):
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 2},
                s3={"addressing_style": "path"},
            ),
        )
        self.signer = (
            self.client
            if not settings.s3_public_endpoint
            else boto3.client(
                "s3",
                endpoint_url=settings.s3_public_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        )

    def put(self, key: str, path: Path, content_type: str) -> None:
        with path.open("rb") as body:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                CacheControl="private, max-age=0",
            )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def sign(self, key: str, seconds: int) -> str:
        return self.signer.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=seconds
        )

    def ready(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)

    def old_keys(self, before: datetime) -> Iterator[str]:
        pages = self.client.get_paginator("list_objects_v2")
        for page in pages.paginate(
            Bucket=self.bucket, Prefix="media/", PaginationConfig={"PageSize": 100}
        ):
            for item in page.get("Contents", []):
                if item["LastModified"] < before:
                    yield item["Key"]
