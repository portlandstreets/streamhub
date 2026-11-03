import asyncio
import json
import logging
import mimetypes
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aio_pika
from aio_pika import DeliveryMode, Message

from blob_storage import blob_manager
from services import get_stored_recording_path

logger = logging.getLogger("core.queue")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = "streamhub.jobs.transcode"
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "/app/storage"))
VIDEO_BUCKET = "streamhub-vods"
THUMBNAIL_BUCKET = "streamhub-thumbnails"


class AsyncJobQueueManager:
    """Durable RabbitMQ producer and consumer for video background processing."""

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.active_workers = 2
        self.total_enqueued = 0
        self.total_processed = 0
        self.total_failed = 0
        self.broker_name = "RabbitMQ"
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._queue: Optional[aio_pika.abc.AbstractQueue] = None
        self._consumer_tag: Optional[str] = None
        self._worker_slots = asyncio.Semaphore(self.active_workers)

    @property
    def queue_name(self) -> str:
        return QUEUE_NAME

    @property
    def _is_connected(self) -> bool:
        return bool(
            self._connection
            and not self._connection.is_closed
            and self._channel
            and not self._channel.is_closed
        )

    def get_stats(self) -> Dict[str, Any]:
        pending = sum(job.get("status") == "QUEUED" for job in self.jobs.values())
        processing = sum(job.get("status") == "PROCESSING" for job in self.jobs.values())
        completed = sum(job.get("status") == "COMPLETED" for job in self.jobs.values())
        failed = sum(job.get("status") == "FAILED" for job in self.jobs.values())
        return {
            "broker": self.broker_name,
            "queue_name": QUEUE_NAME,
            "active_workers": self.active_workers if self._is_connected else 0,
            "status": "RUNNING" if self._is_connected else "UNAVAILABLE",
            "pending_jobs_depth": pending,
            "processing_jobs": processing,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "total_enqueued": self.total_enqueued,
            "total_processed": self.total_processed,
            "supported_tasks": ["transcode_vod", "extract_thumbnails"],
        }

    async def _connect(self) -> None:
        if self._is_connected:
            return
        self._connection = await aio_pika.connect_robust(
            RABBITMQ_URL,
            timeout=10,
            reconnect_interval=2,
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.active_workers)
        self._queue = await self._channel.declare_queue(QUEUE_NAME, durable=True)
        self._consumer_tag = await self._queue.consume(self._process_message)
        logger.info("Connected to RabbitMQ queue %s", QUEUE_NAME)

    async def start(self) -> None:
        if self._is_connected:
            return
        last_error: Optional[Exception] = None
        for attempt in range(10):
            try:
                await self._connect()
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "RabbitMQ connection attempt %s/10 failed: %s",
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(min(attempt + 1, 3))
        raise RuntimeError("Could not connect to RabbitMQ") from last_error

    async def stop(self) -> None:
        if self._queue and self._consumer_tag:
            await self._queue.cancel(self._consumer_tag)
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._queue = None
        self._consumer_tag = None

    async def enqueue(self, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if job_type not in {"transcode_vod", "extract_thumbnails"}:
            raise ValueError(f"Unsupported background job type '{job_type}'")
        await self._connect()
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job_record: Dict[str, Any] = {
            "id": job_id,
            "type": job_type,
            "payload": payload,
            "status": "QUEUED",
            "progress": 0,
            "current_step": "Published to durable RabbitMQ queue",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "duration_seconds": 0.0,
            "worker_id": None,
            "result": None,
            "error": None,
        }
        try:
            if not self._channel:
                raise RuntimeError("RabbitMQ channel is unavailable")
            await self._channel.default_exchange.publish(
                Message(
                    body=json.dumps(job_record, ensure_ascii=False).encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    message_id=job_id,
                ),
                routing_key=QUEUE_NAME,
                mandatory=True,
            )
        except Exception:
            logger.exception("Could not publish background job to RabbitMQ")
            raise

        self.jobs[job_id] = job_record
        self.total_enqueued += 1
        return job_record

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return sorted(
            self.jobs.values(),
            key=lambda job: job.get("created_at", ""),
            reverse=True,
        )[:limit]

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.get("status") == "QUEUED":
            job["status"] = "CANCELLED"
            job["current_step"] = "Cancelled before processing"
            return True
        return False

    async def _process_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                job = json.loads(message.body)
                job_id = job.get("id")
                if not isinstance(job_id, str):
                    raise ValueError("RabbitMQ job message has no valid ID")
                current = self.jobs.setdefault(job_id, job)
                if current.get("status") == "CANCELLED":
                    return

                async with self._worker_slots:
                    started = time.perf_counter()
                    current["status"] = "PROCESSING"
                    current["started_at"] = datetime.now(timezone.utc).isoformat()
                    current["worker_id"] = f"core-worker-{id(asyncio.current_task())}"
                    current["progress"] = 5
                    current["current_step"] = "RabbitMQ consumer acknowledged the job"
                    await self._process_job(current)
                    current["duration_seconds"] = round(time.perf_counter() - started, 2)
                    current["status"] = "COMPLETED"
                    current["progress"] = 100
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
                    current["current_step"] = "Video processing completed"
                    self.total_processed += 1
            except Exception as exc:
                logger.exception("RabbitMQ background job processing failed")
                if isinstance(locals().get("job"), dict):
                    job_id = job.get("id")
                    current = self.jobs.get(job_id) if isinstance(job_id, str) else None
                    if current is not None:
                        current["status"] = "FAILED"
                        current["error"] = str(exc)
                        current["current_step"] = "Video processing failed"
                        current["completed_at"] = datetime.now(timezone.utc).isoformat()
                self.total_failed += 1

    async def _process_job(self, job: Dict[str, Any]) -> None:
        job_type = job["type"]
        payload = job.get("payload", {})
        if job_type == "transcode_vod":
            result = await self._transcode_video(job, payload)
        elif job_type == "extract_thumbnails":
            result = await self._extract_thumbnail(job, payload)
        else:
            raise ValueError(f"Unsupported background job type '{job_type}'")
        job["result"] = result

    async def _run_ffmpeg(self, *arguments: str) -> None:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *arguments,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=6 * 60 * 60)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("FFmpeg video processing exceeded the six-hour limit")
        if process.returncode:
            message = (stderr or b"").decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"FFmpeg failed: {message.strip()}")

    async def _transcode_video(
        self, job: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        source = get_stored_recording_path(str(payload.get("file_path", "")))
        work_dir = STORAGE_DIR / "processing" / job["id"]
        await asyncio.to_thread(work_dir.mkdir, parents=True, exist_ok=True)
        playlist = work_dir / "index.m3u8"
        segment_pattern = work_dir / "segment_%05d.ts"
        job["progress"] = 15
        job["current_step"] = "Transcoding video and packaging HLS renditions"
        try:
            await self._run_ffmpeg(
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-f",
                "hls",
                "-hls_time",
                "6",
                "-hls_playlist_type",
                "vod",
                "-hls_segment_filename",
                str(segment_pattern),
                str(playlist),
            )
            job["progress"] = 85
            job["current_step"] = "Publishing HLS playlist and segments to blob storage"
            recording_id = payload.get("recording_id", job["id"])
            blob_prefix = f"transcoded/{recording_id}/{job['id']}"
            uploaded: Dict[str, str] = {}
            output_files = sorted(
                work_dir.iterdir(),
                key=lambda path: path.suffix == ".m3u8",
            )
            for output_file in output_files:
                mime_type = (
                    "application/vnd.apple.mpegurl"
                    if output_file.suffix == ".m3u8"
                    else mimetypes.guess_type(output_file.name)[0] or "video/mp2t"
                )
                metadata = await asyncio.to_thread(
                    blob_manager.put_blob_from_file,
                    VIDEO_BUCKET,
                    f"{blob_prefix}/{output_file.name}",
                    output_file,
                    mime_type,
                    {"recording_id": recording_id},
                )
                uploaded[output_file.name] = metadata["cdn_url"]
            return {
                "playlist": uploaded.get("index.m3u8"),
                "renditions": ["HLS VOD"],
                "segment_count": sum(name.endswith(".ts") for name in uploaded),
            }
        finally:
            await asyncio.to_thread(shutil.rmtree, work_dir, True)

    async def _extract_thumbnail(
        self, job: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        source = get_stored_recording_path(str(payload.get("file_path", "")))
        work_dir = STORAGE_DIR / "processing" / job["id"]
        await asyncio.to_thread(work_dir.mkdir, parents=True, exist_ok=True)
        output_file = work_dir / "poster.jpg"
        job["progress"] = 25
        job["current_step"] = "Extracting a video frame with FFmpeg"
        try:
            await self._run_ffmpeg(
                "-ss",
                "1",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                str(output_file),
            )
            recording_id = payload.get("recording_id", job["id"])
            metadata = await asyncio.to_thread(
                blob_manager.put_blob_from_file,
                THUMBNAIL_BUCKET,
                f"recordings/{recording_id}/{job['id']}.jpg",
                output_file,
                "image/jpeg",
                {"recording_id": recording_id},
            )
            return {"poster_url": metadata["cdn_url"]}
        finally:
            await asyncio.to_thread(shutil.rmtree, work_dir, True)


async_job_queue = AsyncJobQueueManager()
