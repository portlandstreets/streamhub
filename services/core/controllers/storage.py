import re
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from blob_storage import blob_manager

router = APIRouter(prefix="/api/v1/storage", tags=["Blob Storage & CDN"])


class PurgeCacheRequest(BaseModel):
    pattern: str = "*"


@router.get("/buckets")
async def get_buckets():
    """List all configured Blob Storage buckets with usage statistics."""
    buckets = blob_manager.list_buckets()
    return {"buckets": buckets, "total": len(buckets)}


@router.get("/blobs")
async def list_blobs(
    bucket: str = Query(default="streamhub-vods", description="Bucket identifier"),
    prefix: str = Query(default="", description="Key prefix filter"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List all blobs in the selected bucket with CDN and Presigned URLs."""
    if bucket not in blob_manager.DEFAULT_BUCKETS and bucket != "all":
        # allow listing if directory exists
        bucket_dir = blob_manager.blobs_dir / bucket
        if not bucket_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bucket '{bucket}' not found",
            )

    return blob_manager.list_blobs(bucket=bucket, prefix=prefix, limit=limit, skip=skip)


@router.post("/upload")
async def upload_blob(
    file: UploadFile = File(...),
    bucket: str = Form(default="streamhub-vods"),
    key: Optional[str] = Form(default=None),
):
    """Direct multipart upload of media (video, audio, image) to Blob Storage."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename missing")

    if bucket not in blob_manager.DEFAULT_BUCKETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown storage bucket")
    target_key = (
        key.strip().lstrip("/")
        if key and key.strip()
        else Path(file.filename.replace("\\", "/")).name
    )
    try:
        blob_meta = await blob_manager.put_blob_upload(
            bucket=bucket,
            key=target_key,
            upload=file,
            content_type=file.content_type,
        )
    except ValueError as exc:
        error_status = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if "limit" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=str(exc)) from exc
    finally:
        await file.close()

    return {
        "message": "File uploaded to blob storage successfully",
        "blob": blob_meta,
    }


@router.delete("/blobs/{bucket}/{key:path}")
async def delete_blob(bucket: str, key: str):
    """Delete an object from Blob Storage and invalidate edge cache."""
    deleted = blob_manager.delete_blob(bucket, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blob '{key}' not found in bucket '{bucket}'",
        )
    return {"message": f"Blob '{key}' successfully deleted from '{bucket}'"}


@router.get("/presigned-url")
async def get_presigned_url(
    bucket: str = Query(..., description="Target bucket"),
    key: str = Query(..., description="Blob key"),
    expires_in: int = Query(default=3600, ge=60, le=86400, description="Expiration in seconds"),
):
    """Generate a time-limited HMAC-signed URL for direct secure CDN access."""
    if not blob_manager.object_exists(bucket, key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blob '{key}' does not exist in bucket '{bucket}'",
        )

    signed_url = blob_manager.generate_presigned_url(bucket, key, expires_in=expires_in)
    return {
        "bucket": bucket,
        "key": key,
        "expires_in": expires_in,
        "presigned_url": signed_url,
    }


@router.get("/cdn-stats")
async def get_cdn_stats():
    """Retrieve CDN Edge delivery statistics, hit ratios, and active edge nodes."""
    return blob_manager.get_cdn_stats()


@router.post("/cdn/purge")
async def purge_cdn_cache(payload: PurgeCacheRequest):
    """Purge edge cache for all or matching keys."""
    purged = blob_manager.purge_cdn_cache(pattern=payload.pattern)
    return {
        "message": f"Edge cache purged for pattern '{payload.pattern}'",
        "purged_entries": purged,
    }


@router.get("/cdn/{bucket}/{key:path}")
async def deliver_cdn_blob(
    bucket: str,
    key: str,
    request: Request,
    if_none_match: Optional[str] = Header(None),
    range_header: Optional[str] = Header(None, alias="Range"),
    token: Optional[str] = Query(None),
    expires: Optional[int] = Query(None),
):
    """CDN Edge Delivery Endpoint.
    Delivers static media (video, audio, images) with standard CDN edge headers:
    - Cache-Control: public, max-age=..., immutable
    - ETag support & 304 Not Modified
    - HTTP 206 Partial Content for video/audio seeking (Range: bytes=start-end)
    - X-CDN-Cache: HIT / MISS
    - X-CDN-Edge-Node & X-CDN-Pop
    - Optional HMAC presigned token verification
    """
    if not blob_manager.object_exists(bucket, key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CDN 404: Blob '{key}' not found on edge or origin for bucket '{bucket}'",
        )

    # Validate presigned signature if token provided
    if token and expires:
        if not blob_manager.verify_presigned_token(bucket, key, expires, token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CDN 403: Presigned URL has expired or signature is invalid",
            )

    meta = blob_manager.get_blob_metadata(bucket, key)
    etag = meta.get("etag", '""')
    content_type = meta.get("content_type", "application/octet-stream")
    ttl = blob_manager.DEFAULT_BUCKETS.get(bucket, {}).get("default_ttl", 31536000)
    file_size = meta.get("size", 0)
    file_path = blob_manager.ensure_local_blob(bucket, key)

    # 1. Conditional 304 Not Modified check
    if if_none_match and (if_none_match == etag or if_none_match == etag.strip('"')):
        cdn_info = blob_manager.record_cdn_request(bucket, key, bytes_sent=0, is_conditional_hit=True)
        headers = {
            "ETag": etag,
            "Cache-Control": f"public, max-age={ttl}, immutable",
            "X-CDN-Cache": "HIT",
            "X-CDN-Edge-Node": cdn_info["edge_node"],
            "X-CDN-Pop": cdn_info["pop"],
            "X-CDN-Status": "304 Not Modified (Revalidated)",
            "Accept-Ranges": "bytes",
        }
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    # 2. HTTP 206 Partial Content (Range request) for video scrubbing & seeking
    if range_header:
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
            if start < file_size and end < file_size and start <= end:
                content_length = end - start + 1
                cdn_info = blob_manager.record_cdn_request(bucket, key, bytes_sent=content_length)

                def range_stream():
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(65536, remaining)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk

                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(content_length),
                    "Content-Type": content_type,
                    "ETag": etag,
                    "Cache-Control": f"public, max-age={ttl}, immutable",
                    "X-CDN-Cache": cdn_info["status"],
                    "X-CDN-Edge-Node": cdn_info["edge_node"],
                    "X-CDN-Pop": cdn_info["pop"],
                    "X-CDN-Latency": f"{cdn_info['latency_ms']}ms",
                }
                return StreamingResponse(
                    range_stream(),
                    status_code=status.HTTP_206_PARTIAL_CONTENT,
                    headers=headers,
                )

    # 3. Standard 200 Edge Delivery
    cdn_info = blob_manager.record_cdn_request(bucket, key, bytes_sent=file_size)
    headers = {
        "ETag": etag,
        "Cache-Control": f"public, max-age={ttl}, immutable",
        "X-CDN-Cache": cdn_info["status"],
        "X-CDN-Edge-Node": cdn_info["edge_node"],
        "X-CDN-Pop": cdn_info["pop"],
        "X-CDN-Latency": f"{cdn_info['latency_ms']}ms",
        "Accept-Ranges": "bytes",
    }
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        headers=headers,
    )


@router.head("/cdn/{bucket}/{key:path}")
async def head_cdn_blob(bucket: str, key: str):
    """HEAD request for CDN metadata inspection."""
    if not blob_manager.object_exists(bucket, key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blob not found")

    meta = blob_manager.get_blob_metadata(bucket, key)
    ttl = blob_manager.DEFAULT_BUCKETS.get(bucket, {}).get("default_ttl", 31536000)

    headers = {
        "ETag": meta.get("etag", '""'),
        "Content-Type": meta.get("content_type", "application/octet-stream"),
        "Content-Length": str(meta.get("size", 0)),
        "Cache-Control": f"public, max-age={ttl}, immutable",
        "Accept-Ranges": "bytes",
        "X-CDN-Edge-Node": "edge-fra-01.streamhub.cdn",
        "X-CDN-Pop": "FRA-1",
    }
    return Response(status_code=status.HTTP_200_OK, headers=headers)
