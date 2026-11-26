"""Private S3-compatible storage for authenticated, encrypted artifact bytes."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException

MAX_CIPHERTEXT = 10 * 1024 * 1024 + 16


def object_key(owner: str, file_id: UUID) -> str:
    # No human-readable account IDs, filenames or user-supplied paths.
    if not isinstance(owner,str) or not owner or not isinstance(file_id,UUID):
        raise ValueError("Invalid artifact identity")
    return "dz-agent/v1/" + hashlib.sha256(owner.encode()).hexdigest() + "/" + str(file_id)


class S3ArtifactStore:
    def __init__(self, client, bucket):
        if not isinstance(bucket,str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]",bucket):
            raise ValueError("Invalid private bucket")
        self.client=client
        self.bucket=bucket

    @classmethod
    def from_environment(cls):
        # No user-controlled endpoint, public bucket ACL, or credentials in
        # model context. A missing configuration is a hard storage error.
        import boto3
        from botocore.config import Config
        endpoint=os.environ.get("DRAGONZPYDER_ARTIFACT_S3_ENDPOINT","").strip()
        bucket=os.environ.get("DRAGONZPYDER_ARTIFACT_S3_BUCKET","")
        key=os.environ.get("DRAGONZPYDER_ARTIFACT_S3_ACCESS_KEY","")
        secret=os.environ.get("DRAGONZPYDER_ARTIFACT_S3_SECRET_KEY","")
        url=urlsplit(endpoint)
        if (url.scheme!="https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("","/")
                or not key or not secret):
            raise ValueError("Explicit private S3 configuration required")
        client=boto3.client("s3",endpoint_url=endpoint,
            aws_access_key_id=key,aws_secret_access_key=secret,
            region_name=os.getenv("DRAGONZPYDER_ARTIFACT_S3_REGION","us-east-1"),
            config=Config(connect_timeout=5,read_timeout=15,
                          retries={"total_max_attempts":1,"mode":"standard"},
                          s3={"addressing_style":"path"}))
        return cls(client,bucket)

    async def put_new(self,key,data):
        if type(data) is not bytes or not 17<=len(data)<=MAX_CIPHERTEXT:
            raise ValueError("Invalid ciphertext size")
        # Never replace an object. A provider without conditional-write support
        # fails closed, rather than silently risking mutable artifact versions.
        await asyncio.to_thread(self.client.put_object,Bucket=self.bucket,Key=key,
            Body=data,ContentType="application/octet-stream",IfNoneMatch="*")

    async def read(self,key,expected_size):
        if type(expected_size) is not int or not 17<=expected_size<=MAX_CIPHERTEXT:
            raise ValueError("Invalid expected ciphertext size")
        def read():
            response=self.client.get_object(Bucket=self.bucket,Key=key)
            body=response["Body"]
            try:
                if response.get("ContentLength")!=expected_size:
                    raise ValueError("Object size mismatch")
                result=body.read(expected_size+1)
                if len(result)!=expected_size:
                    raise ValueError("Object readback size mismatch")
                return result
            finally:
                body.close()
        return await asyncio.to_thread(read)

    async def delete(self,key):
        await asyncio.to_thread(self.client.delete_object,Bucket=self.bucket,Key=key)


def configured_store():
    try:
        return S3ArtifactStore.from_environment()
    except Exception:
        raise HTTPException(503,"Private artifact object storage unavailable") from None
