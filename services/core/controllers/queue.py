import logging
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from database import get_db
from dependencies import get_current_user
from models import Recording, Stream, User
from job_queue import async_job_queue
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/queue", tags=["Async Message Queue (B8)"])
logger = logging.getLogger("core.queue.api")


class EnqueueJobRequest(BaseModel):
    type: Literal["transcode_vod", "extract_thumbnails"] = Field(
        default="transcode_vod",
        description="Background video task to run through RabbitMQ and FFmpeg.",
    )
    stream_id: Optional[int] = None
    file_path: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


@router.get("/stats")
async def get_queue_stats():
    """
    B8 Requirement: Returns message queue health, active background workers count,
    queue depth (pending jobs), and completed job counts.
    """
    return async_job_queue.get_stats()


@router.get("/jobs")
async def list_queue_jobs(limit: int = Query(default=30, ge=1, le=100)):
    """Lists asynchronous jobs from the queue with real-time progress and statuses."""
    items = async_job_queue.list_jobs(limit=limit)
    return {
        "total": len(items),
        "items": items,
        "queue_stats": async_job_queue.get_stats(),
    }


@router.get("/jobs/{job_id}")
async def get_queue_job_details(job_id: str):
    """Inspects a specific asynchronous job by its job_id."""
    job = async_job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_background_job(
    request: EnqueueJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Producer Endpoint: Dispatches an asynchronous job to the message queue.
    Immediately returns HTTP 202 ACCEPTED with the unique job_id.
    Workers asynchronously consume, execute, and ACK the message.
    """
    if request.stream_id is None:
        raise HTTPException(status_code=422, detail="stream_id is required")
    stream = await db.get(Stream, request.stream_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    if stream.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the channel owner can process its videos")

    recording_id = (request.options or {}).get("recording_id")
    recording = None
    if recording_id is not None:
        if isinstance(recording_id, bool) or not isinstance(recording_id, int):
            raise HTTPException(status_code=422, detail="recording_id must be an integer")
        recording = await db.get(Recording, recording_id)
        if recording is None or recording.stream_id != stream.id:
            raise HTTPException(status_code=404, detail="Recording not found in this channel")
    elif request.file_path:
        result = await db.execute(
            select(Recording).where(
                Recording.stream_id == stream.id,
                Recording.file_path == request.file_path,
            )
        )
        recording = result.scalars().first()
    if recording is None:
        raise HTTPException(status_code=404, detail="A saved recording is required for processing")

    payload = {
        "stream_id": stream.id,
        "recording_id": recording.id,
        "file_path": recording.file_path,
        "duration_seconds": recording.duration_seconds or 0,
        "owner": current_user.username,
    }
    try:
        job_record = await async_job_queue.enqueue(
            job_type=request.type,
            payload=payload,
        )
    except Exception as exc:
        logger.exception("Could not enqueue video job")
        raise HTTPException(
            status_code=503,
            detail="Background processing queue is unavailable",
        ) from exc
    return {
        "message": f"Job enqueued into {async_job_queue.queue_name} successfully",
        "job_id": job_record["id"],
        "status": job_record["status"],
        "job": job_record,
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_queued_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancels a pending job before it starts processing."""
    job = async_job_queue.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("payload", {}).get("owner") != current_user.username:
        raise HTTPException(status_code=403, detail="Only the job owner can cancel it")
    success = async_job_queue.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (either not found or already processing/completed)",
        )
    return {"message": f"Job {job_id} cancelled", "status": "CANCELLED"}
