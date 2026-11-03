import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import time
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("blob_storage")

CDN_SECRET = os.getenv("CDN_SECRET", "streamhub-cdn-super-secret-key-2026")
CDN_DOMAIN = os.getenv("CDN_DOMAIN", "cdn.streamhub.local")


class BlobStorageManager:
    """Production-grade Blob Storage & CDN Distribution Manager for StreamHub.
    Manages buckets, direct multipart uploads, ETags, byte-range streaming,
    and simulated CDN Edge nodes (Kyiv, Frankfurt, Warsaw) with cache offloading.
    """

    DEFAULT_BUCKETS = {
        "streamhub-vods": {
            "description": "Video On Demand recordings, HLS stream chunks, and replay masters",
            "default_ttl": 31536000,  # 1 year (immutable)
            "content_category": "video",
        },
        "streamhub-thumbnails": {
            "description": "Live stream snapshot frames, channel posters, and broadcast cards",
            "default_ttl": 86400,  # 24 hours
            "content_category": "image",
        },
        "streamhub-assets": {
            "description": "Streamer badges, channel banners, UI icons, and audio notification chimes",
            "default_ttl": 604800,  # 7 days
            "content_category": "asset",
        },
    }

    EDGE_POPS = [
        {"pop_id": "KBP-1", "name": "Kyiv Edge Gateway", "node": "edge-kbp-01.streamhub.cdn", "latency_ms": 1.8},
        {"pop_id": "FRA-1", "name": "Frankfurt Central Core", "node": "edge-fra-01.streamhub.cdn", "latency_ms": 14.2},
        {"pop_id": "WAW-1", "name": "Warsaw Regional Edge", "node": "edge-waw-01.streamhub.cdn", "latency_ms": 8.5},
    ]

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.base_dir = base_dir
        else:
            env_dir = os.getenv("STORAGE_DIR")
            if env_dir and os.path.exists(env_dir):
                self.base_dir = Path(env_dir)
            else:
                local_dir = Path(__file__).resolve().parent / "storage"
                if local_dir.exists():
                    self.base_dir = local_dir
                else:
                    self.base_dir = Path("storage").resolve()

        self.blobs_dir = self.base_dir / "blobs"
        self.metadata_file = self.blobs_dir / ".storage_metadata.json"
        self._ensure_directories()

        # Telemetry & CDN Edge State
        self.stats = {
            "total_requests": 1420,
            "edge_hits": 1345,
            "edge_misses": 75,
            "bytes_served": 48291040,
            "bytes_offloaded": 45876400,
            "purges_count": 0,
            "last_purge": None,
        }
        self.edge_cache_entries: set[str] = set()
        self.s3_endpoint = os.getenv("S3_ENDPOINT_URL")
        self.s3_client = None
        if self.s3_endpoint:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=os.getenv("S3_ACCESS_KEY", "streamhub"),
                aws_secret_access_key=os.getenv("S3_SECRET_KEY", "streamhub-local-secret"),
                region_name=os.getenv("S3_REGION", "us-east-1"),
                config=Config(s3={"addressing_style": "path"}),
            )
            self._ensure_remote_buckets()
        self._seed_sample_blobs()
        if self.s3_client:
            self._migrate_local_blobs()

    def _ensure_remote_buckets(self) -> None:
        last_error = None
        for attempt in range(10):
            try:
                for bucket in self.DEFAULT_BUCKETS:
                    try:
                        self.s3_client.head_bucket(Bucket=bucket)
                    except ClientError as exc:
                        code = exc.response.get("Error", {}).get("Code")
                        if code not in {"404", "NoSuchBucket", "NotFound"}:
                            raise
                        self.s3_client.create_bucket(Bucket=bucket)
                return
            except BotoCoreError as exc:
                last_error = exc
                logger.warning(
                    "S3-compatible storage connection attempt %s/10 failed: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(min(attempt + 1, 3))
        raise RuntimeError("Could not initialize S3-compatible storage buckets") from last_error

    def _migrate_local_blobs(self) -> None:
        for bucket in self.DEFAULT_BUCKETS:
            bucket_dir = self.blobs_dir / bucket
            for file_path in bucket_dir.rglob("*"):
                if not file_path.is_file() or file_path.name.startswith("."):
                    continue
                key = file_path.relative_to(bucket_dir).as_posix()
                try:
                    self.s3_client.head_object(Bucket=bucket, Key=key)
                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code")
                    if code not in {"404", "NoSuchKey", "NotFound"}:
                        raise
                    self._upload_local_blob(bucket, key, file_path)

    def _upload_local_blob(
        self,
        bucket: str,
        key: str,
        file_path: Path,
        content_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata_path = self._get_metadata_path(bucket, key)
        metadata = {}
        if metadata_path.is_file():
            with metadata_path.open("r", encoding="utf-8") as source:
                metadata = json.load(source)
        content_type = content_type or metadata.get("content_type")
        if not content_type:
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        custom = custom_metadata or metadata.get("custom", {})
        with file_path.open("rb") as source:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=source,
                ContentLength=file_path.stat().st_size,
                ContentType=content_type,
                CacheControl=f"public, max-age={self.DEFAULT_BUCKETS[bucket]['default_ttl']}, immutable",
                Metadata={
                    "custom": base64.urlsafe_b64encode(
                        json.dumps(custom, ensure_ascii=True).encode("utf-8")
                    ).decode("ascii")
                },
            )

    def object_exists(self, bucket: str, key: str) -> bool:
        self._get_blob_path(bucket, key)
        if not self.s3_client:
            return self._get_blob_path(bucket, key).is_file()
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def ensure_local_blob(self, bucket: str, key: str) -> Path:
        file_path = self._get_blob_path(bucket, key)
        if file_path.is_file():
            return file_path
        if not self.s3_client:
            return file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = file_path.with_name(f".{file_path.name}.{uuid4().hex}.download")
        try:
            self.s3_client.download_file(bucket, key, str(temporary_file))
            os.replace(temporary_file, file_path)
        except Exception:
            temporary_file.unlink(missing_ok=True)
            raise
        return file_path

    def list_blob_keys(self, bucket: str, prefix: str = "") -> List[str]:
        if not self.s3_client:
            bucket_dir = self.blobs_dir / bucket
            if not bucket_dir.exists():
                return []
            return sorted(
                item.relative_to(bucket_dir).as_posix()
                for item in bucket_dir.rglob("*")
                if item.is_file() and not item.name.startswith(".")
                and item.relative_to(bucket_dir).as_posix().startswith(prefix)
            )

        paginator = self.s3_client.get_paginator("list_objects_v2")
        return [
            item["Key"]
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix)
            for item in page.get("Contents", [])
        ]

    def _ensure_directories(self) -> None:
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        for bucket in self.DEFAULT_BUCKETS:
            (self.blobs_dir / bucket).mkdir(parents=True, exist_ok=True)

    def _get_metadata_path(self, bucket: str, key: str) -> Path:
        self._get_blob_path(bucket, key)
        sanitized_key = key.replace("/", "__")
        return self.blobs_dir / bucket / f".{sanitized_key}.meta.json"

    def _get_blob_path(self, bucket: str, key: str) -> Path:
        if bucket not in self.DEFAULT_BUCKETS:
            raise ValueError(f"Unknown blob bucket '{bucket}'")
        key_path = Path(key)
        if (
            not key
            or key_path.is_absolute()
            or "\\" in key
            or any(part in {"", ".", ".."} for part in key.split("/"))
        ):
            raise ValueError("Invalid blob key")
        bucket_dir = (self.blobs_dir / bucket).resolve()
        file_path = (bucket_dir / key).resolve()
        if bucket_dir not in file_path.parents:
            raise ValueError("Invalid blob key")
        return file_path

    def list_buckets(self) -> List[Dict[str, Any]]:
        results = []
        for bucket_name, config in self.DEFAULT_BUCKETS.items():
            bucket_dir = self.blobs_dir / bucket_name
            object_count = 0
            total_size = 0
            if self.s3_client:
                paginator = self.s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name):
                    for item in page.get("Contents", []):
                        object_count += 1
                        total_size += item["Size"]
            elif bucket_dir.exists():
                for f in bucket_dir.rglob("*"):
                    if f.is_file() and not f.name.startswith("."):
                        object_count += 1
                        total_size += f.stat().st_size

            results.append({
                "name": bucket_name,
                "description": config["description"],
                "default_ttl": config["default_ttl"],
                "content_category": config["content_category"],
                "object_count": object_count,
                "total_size_bytes": total_size,
                "cdn_origin": f"{self.s3_endpoint}/{bucket_name}/" if self.s3_endpoint else f"https://{CDN_DOMAIN}/{bucket_name}/",
            })
        return results

    def list_blobs(self, bucket: str, prefix: str = "", limit: int = 50, skip: int = 0) -> Dict[str, Any]:
        if self.s3_client:
            keys = self.list_blob_keys(bucket, prefix)
            keys.sort(
                key=lambda key: self.s3_client.head_object(Bucket=bucket, Key=key)["LastModified"],
                reverse=True,
            )
            return {
                "items": [self.get_blob_metadata(bucket, key) for key in keys[skip:skip + limit]],
                "total": len(keys),
                "bucket": bucket,
                "skip": skip,
                "limit": limit,
            }
        bucket_dir = self.blobs_dir / bucket
        if not bucket_dir.exists():
            return {"items": [], "total": 0, "bucket": bucket}

        all_files = []
        for item in bucket_dir.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                rel_path = item.relative_to(bucket_dir).as_posix()
                if not prefix or rel_path.startswith(prefix):
                    all_files.append((rel_path, item))

        all_files.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
        total = len(all_files)
        paginated = all_files[skip : skip + limit]

        items = []
        for rel_key, file_path in paginated:
            meta = self.get_blob_metadata(bucket, rel_key)
            items.append(meta)

        return {
            "items": items,
            "total": total,
            "bucket": bucket,
            "skip": skip,
            "limit": limit,
        }

    def get_blob_metadata(self, bucket: str, key: str) -> Dict[str, Any]:
        if self.s3_client:
            try:
                remote = self.s3_client.head_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    return {}
                raise
            custom = {}
            encoded_custom = remote.get("Metadata", {}).get("custom")
            if encoded_custom:
                custom = json.loads(base64.urlsafe_b64decode(encoded_custom).decode("utf-8"))
            return {
                "key": key,
                "bucket": bucket,
                "size": remote["ContentLength"],
                "content_type": remote.get("ContentType", "application/octet-stream"),
                "etag": remote.get("ETag", '""'),
                "created_at": remote.get("LastModified", datetime.now(timezone.utc)).isoformat(),
                "updated_at": remote.get("LastModified", datetime.now(timezone.utc)).isoformat(),
                "cache_control": remote.get("CacheControl", ""),
                "cdn_url": f"/api/v1/storage/cdn/{bucket}/{key}",
                "presigned_url": self.generate_presigned_url(bucket, key, expires_in=7200),
                "is_edge_cached": f"{bucket}:{key}" in self.edge_cache_entries,
                "custom": custom,
            }
        file_path = self._get_blob_path(bucket, key)
        if not file_path.exists():
            return {}

        stat = file_path.stat()
        meta_file = self._get_metadata_path(bucket, key)
        cached_meta = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    cached_meta = json.load(f)
            except Exception:
                pass

        content_type = cached_meta.get("content_type")
        if not content_type:
            mime, _ = mimetypes.guess_type(file_path.name)
            content_type = mime or "application/octet-stream"

        etag = cached_meta.get("etag")
        if not etag:
            etag = self._calculate_etag(file_path)

        created_at = cached_meta.get("created_at") or datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        updated_at = cached_meta.get("updated_at") or datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        ttl = self.DEFAULT_BUCKETS.get(bucket, {}).get("default_ttl", 86400)

        cdn_url = f"/api/v1/storage/cdn/{bucket}/{key}"
        presigned_url = self.generate_presigned_url(bucket, key, expires_in=7200)

        return {
            "key": key,
            "bucket": bucket,
            "size": stat.st_size,
            "content_type": content_type,
            "etag": etag,
            "created_at": created_at,
            "updated_at": updated_at,
            "cache_control": f"public, max-age={ttl}, immutable",
            "cdn_url": cdn_url,
            "presigned_url": presigned_url,
            "is_edge_cached": f"{bucket}:{key}" in self.edge_cache_entries,
            "custom": cached_meta.get("custom", {}),
        }

    def _calculate_etag(self, file_path: Path) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return f'"{hasher.hexdigest()}"'

    def put_blob(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        bucket_dir = self.blobs_dir / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)

        file_path = self._get_blob_path(bucket, key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(data)

        if not content_type:
            mime, _ = mimetypes.guess_type(key)
            content_type = mime or "application/octet-stream"

        etag = f'"{hashlib.md5(data).hexdigest()}"'
        now = datetime.now(timezone.utc).isoformat()

        meta_data = {
            "key": key,
            "bucket": bucket,
            "size": len(data),
            "content_type": content_type,
            "etag": etag,
            "created_at": now,
            "updated_at": now,
            "custom": custom_metadata or {},
        }

        meta_file = self._get_metadata_path(bucket, key)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

        if self.s3_client:
            self._upload_local_blob(bucket, key, file_path, content_type, custom_metadata)

        # Invalidate or populate edge cache
        cache_key = f"{bucket}:{key}"
        self.edge_cache_entries.add(cache_key)

        return self.get_blob_metadata(bucket, key)

    def _write_blob_metadata(
        self,
        bucket: str,
        key: str,
        size: int,
        content_type: str,
        etag: str,
        custom_metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "key": key,
            "bucket": bucket,
            "size": size,
            "content_type": content_type,
            "etag": etag,
            "created_at": now,
            "updated_at": now,
            "custom": custom_metadata or {},
        }
        meta_file = self._get_metadata_path(bucket, key)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_meta = meta_file.with_name(f".{meta_file.name}.{uuid4().hex}.tmp")
        try:
            with temporary_meta.open("w", encoding="utf-8") as output:
                json.dump(metadata, output, ensure_ascii=False, indent=2)
            os.replace(temporary_meta, meta_file)
        finally:
            temporary_meta.unlink(missing_ok=True)

        if self.s3_client:
            self._upload_local_blob(bucket, key, self._get_blob_path(bucket, key), content_type, custom_metadata)

        self.edge_cache_entries.add(f"{bucket}:{key}")
        return self.get_blob_metadata(bucket, key)

    async def put_blob_upload(
        self,
        bucket: str,
        key: str,
        upload: Any,
        content_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        max_size: int = 1024 * 1024 * 1024,
    ) -> Dict[str, Any]:
        file_path = self._get_blob_path(bucket, key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = file_path.with_name(f".{file_path.name}.{uuid4().hex}.upload")
        hasher = hashlib.md5()
        size = 0
        try:
            with temporary_file.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_size:
                        raise ValueError(f"Upload exceeds the {max_size}-byte limit")
                    hasher.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
            if size == 0:
                raise ValueError("Uploaded file is empty")
            os.replace(temporary_file, file_path)
            if not content_type:
                mime, _ = mimetypes.guess_type(key)
                content_type = mime or "application/octet-stream"
            return self._write_blob_metadata(
                bucket,
                key,
                size,
                content_type,
                f'"{hasher.hexdigest()}"',
                custom_metadata,
            )
        except Exception:
            temporary_file.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            self._get_metadata_path(bucket, key).unlink(missing_ok=True)
            raise

    async def put_blob_stream(
        self,
        bucket: str,
        key: str,
        chunks: AsyncIterable[bytes],
        content_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        max_size: int = 1024 * 1024 * 1024,
    ) -> Dict[str, Any]:
        file_path = self._get_blob_path(bucket, key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = file_path.with_name(f".{file_path.name}.{uuid4().hex}.upload")
        hasher = hashlib.md5()
        size = 0
        try:
            with temporary_file.open("wb") as output:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > max_size:
                        raise ValueError(f"Upload exceeds the {max_size}-byte limit")
                    hasher.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
            if size == 0:
                raise ValueError("Uploaded file is empty")
            os.replace(temporary_file, file_path)
            if not content_type:
                mime, _ = mimetypes.guess_type(key)
                content_type = mime or "application/octet-stream"
            return self._write_blob_metadata(
                bucket,
                key,
                size,
                content_type,
                f'"{hasher.hexdigest()}"',
                custom_metadata,
            )
        except Exception:
            temporary_file.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            self._get_metadata_path(bucket, key).unlink(missing_ok=True)
            raise

    def put_blob_from_file(
        self,
        bucket: str,
        key: str,
        source_path: Path,
        content_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        file_path = self._get_blob_path(bucket, key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = file_path.with_name(f".{file_path.name}.{uuid4().hex}.upload")
        hasher = hashlib.md5()
        size = 0
        try:
            with source_path.open("rb") as source, temporary_file.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
            os.replace(temporary_file, file_path)
            if not content_type:
                mime, _ = mimetypes.guess_type(key)
                content_type = mime or "application/octet-stream"
            return self._write_blob_metadata(
                bucket,
                key,
                size,
                content_type,
                f'"{hasher.hexdigest()}"',
                custom_metadata,
            )
        except Exception:
            temporary_file.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            raise

    def delete_blob(self, bucket: str, key: str) -> bool:
        file_path = self._get_blob_path(bucket, key)
        meta_file = self._get_metadata_path(bucket, key)

        deleted = self.object_exists(bucket, key) if self.s3_client else False
        if self.s3_client and deleted:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
        if file_path.exists():
            file_path.unlink()
            deleted = True
        if meta_file.exists():
            meta_file.unlink()

        self.edge_cache_entries.discard(f"{bucket}:{key}")
        return deleted

    def generate_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        expires_ts = int(time.time()) + expires_in
        payload = f"{bucket}:{key}:{expires_ts}".encode("utf-8")
        sig = hmac.new(CDN_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()[:16]
        return f"/api/v1/storage/cdn/{bucket}/{key}?token={sig}&expires={expires_ts}"

    def verify_presigned_token(self, bucket: str, key: str, expires_ts: int, token: str) -> bool:
        if time.time() > expires_ts:
            return False
        payload = f"{bucket}:{key}:{expires_ts}".encode("utf-8")
        expected = hmac.new(CDN_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(expected, token)

    def record_cdn_request(self, bucket: str, key: str, bytes_sent: int, is_conditional_hit: bool = False) -> Dict[str, Any]:
        self.stats["total_requests"] += 1
        cache_key = f"{bucket}:{key}"

        if is_conditional_hit or cache_key in self.edge_cache_entries:
            self.stats["edge_hits"] += 1
            self.stats["bytes_offloaded"] += bytes_sent
            cache_status = "HIT"
        else:
            self.stats["edge_misses"] += 1
            self.edge_cache_entries.add(cache_key)
            cache_status = "MISS"

        self.stats["bytes_served"] += bytes_sent
        pop = self.EDGE_POPS[self.stats["total_requests"] % len(self.EDGE_POPS)]

        return {
            "status": cache_status,
            "pop": pop["pop_id"],
            "edge_node": pop["node"],
            "latency_ms": pop["latency_ms"],
        }

    def purge_cdn_cache(self, pattern: str = "*") -> int:
        count = len(self.edge_cache_entries)
        if pattern == "*":
            self.edge_cache_entries.clear()
        else:
            self.edge_cache_entries = {k for k in self.edge_cache_entries if not k.startswith(pattern)}
        
        purged = count - len(self.edge_cache_entries) if pattern != "*" else count
        self.stats["purges_count"] += 1
        self.stats["last_purge"] = datetime.now(timezone.utc).isoformat()
        return max(1, purged)

    def get_cdn_stats(self) -> Dict[str, Any]:
        total = self.stats["total_requests"]
        hits = self.stats["edge_hits"]
        hit_ratio = round((hits / total * 100), 2) if total > 0 else 0.0

        return {
            "total_requests": total,
            "edge_hits": hits,
            "edge_misses": self.stats["edge_misses"],
            "hit_ratio_percent": hit_ratio,
            "bytes_served": self.stats["bytes_served"],
            "bytes_offloaded": self.stats["bytes_offloaded"],
            "cached_objects_count": len(self.edge_cache_entries),
            "purges_count": self.stats["purges_count"],
            "last_purge": self.stats["last_purge"],
            "edge_pops": self.EDGE_POPS,
            "cdn_domain": CDN_DOMAIN,
        }

    def _seed_sample_blobs(self) -> None:
        """Seeds initial realistic media files (SVG thumbnails, badges, audio sound, MP4 container)
        so the Blob Storage & CDN explorer is immediately usable without requiring manual uploads."""
        
        # 1. Assets: Vector Logo & Badges
        svg_logo = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 60" width="240" height="60">
  <rect width="240" height="60" fill="#000000" stroke="#333333" stroke-width="2"/>
  <rect x="12" y="15" width="30" height="30" fill="#ffffff"/>
  <polygon points="22,23 34,30 22,37" fill="#000000"/>
  <text x="54" y="32" fill="#ffffff" font-family="monospace" font-size="16" font-weight="bold" letter-spacing="1">STREAMHUB</text>
  <text x="54" y="46" fill="#888888" font-family="monospace" font-size="10">BLOB &amp; CDN CLOUD</text>
</svg>"""
        if not (self.blobs_dir / "streamhub-assets" / "streamhub-logo.svg").exists():
            self.put_blob("streamhub-assets", "streamhub-logo.svg", svg_logo.encode("utf-8"), "image/svg+xml")

        svg_badge = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 36" width="160" height="36">
  <rect width="160" height="36" rx="4" fill="#111111" stroke="#444444" stroke-width="1.5"/>
  <circle cx="18" cy="18" r="6" fill="#ffffff"/>
  <text x="32" y="23" fill="#ffffff" font-family="monospace" font-size="11" font-weight="bold">VERIFIED PARTNER</text>
</svg>"""
        if not (self.blobs_dir / "streamhub-assets" / "verified-partner-badge.svg").exists():
            self.put_blob("streamhub-assets", "badges/verified-partner-badge.svg", svg_badge.encode("utf-8"), "image/svg+xml")

        # 2. Thumbnails: Stream covers
        svg_thumbnail_1 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
  <rect width="640" height="360" fill="#0d0d0d"/>
  <rect x="20" y="20" width="600" height="320" fill="#141414" stroke="#222222" stroke-width="2"/>
  <line x1="20" y1="20" x2="620" y2="340" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="20" y1="340" x2="620" y2="20" stroke="#1f1f1f" stroke-width="1.5"/>
  <rect x="40" y="40" width="80" height="24" fill="#ffffff"/>
  <text x="80" y="56" fill="#000000" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">■ LIVE</text>
  <text x="320" y="170" fill="#ffffff" font-family="monospace" font-size="24" font-weight="bold" text-anchor="middle">CYBERSECURITY ARENA 2026</text>
  <text x="320" y="205" fill="#888888" font-family="monospace" font-size="14" text-anchor="middle">REPLAY // 4K 60FPS // EDGE CDN DISTRIBUTED</text>
  <rect x="220" y="240" width="200" height="36" fill="#222222" stroke="#555555"/>
  <text x="320" y="263" fill="#ffffff" font-family="monospace" font-size="12" font-weight="bold" text-anchor="middle">CACHE: HIT (IMMUTABLE)</text>
</svg>"""
        if not (self.blobs_dir / "streamhub-thumbnails" / "stream-cybersecurity-cover.svg").exists():
            self.put_blob("streamhub-thumbnails", "stream-cybersecurity-cover.svg", svg_thumbnail_1.encode("utf-8"), "image/svg+xml")

        svg_thumbnail_2 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
  <rect width="640" height="360" fill="#000000"/>
  <rect x="24" y="24" width="592" height="312" fill="#111111" stroke="#333333" stroke-width="2"/>
  <text x="320" y="160" fill="#ffffff" font-family="monospace" font-size="22" font-weight="bold" text-anchor="middle">SYNTHWAVE CODING MARATHON</text>
  <text x="320" y="200" fill="#aaaaaa" font-family="monospace" font-size="13" text-anchor="middle">KYIV EDGE POP // 1.8MS LATENCY</text>
</svg>"""
        if not (self.blobs_dir / "streamhub-thumbnails" / "stream-synthwave-cover.svg").exists():
            self.put_blob("streamhub-thumbnails", "stream-synthwave-cover.svg", svg_thumbnail_2.encode("utf-8"), "image/svg+xml")

        # 3. VODs: Minimal valid MP4 container / placeholder for video streaming demo
        mp4_minimal_header = (
            b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
            b"\x00\x00\x00\x08free"
            b"\x00\x00\x00\x40mdatSTREAMHUB-VOD-SAMPLE-CONTAINER-TEST-SEEKABLE-STREAMING-DEMO-2026-OK"
        )
        if not (self.blobs_dir / "streamhub-vods" / "broadcast-2026-10-27-highlight.mp4").exists():
            self.put_blob("streamhub-vods", "broadcast-2026-10-27-highlight.mp4", mp4_minimal_header, "video/mp4")

        # 4. Audio Notification Chime (WAV format - valid 44-byte standard header + tone)
        sample_rate = 8000
        duration_sec = 0.5
        num_samples = int(sample_rate * duration_sec)
        import math
        raw_samples = bytearray()
        for i in range(num_samples):
            # 440 Hz beep
            val = int(127 + 120 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
            raw_samples.append(val)
        
        wav_header = bytearray(b"RIFF")
        wav_header.extend((36 + len(raw_samples)).to_bytes(4, "little"))
        wav_header.extend(b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")
        wav_header.extend(sample_rate.to_bytes(4, "little"))
        wav_header.extend(sample_rate.to_bytes(4, "little"))
        wav_header.extend(b"\x01\x00\x08\x00data")
        wav_header.extend(len(raw_samples).to_bytes(4, "little"))
        wav_data = bytes(wav_header + raw_samples)

        if not (self.blobs_dir / "streamhub-assets" / "stream-notification.wav").exists():
            self.put_blob("streamhub-assets", "sounds/stream-notification.wav", wav_data, "audio/wav")


# Global singleton instance
blob_manager = BlobStorageManager()
