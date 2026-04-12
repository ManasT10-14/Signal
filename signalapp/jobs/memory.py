"""
In-memory queue — a drop-in ARQ replacement for local development.

Use QUEUE_MODE=memory in .env to activate this instead of Redis.

Jobs are stored in an in-memory deque and executed synchronously
or via asyncio.create_task in a background thread pool.

WARNING: Jobs are lost on restart. DO NOT use in production.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class MemoryJob:
    job_id: str
    function_name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class MemoryQueue:
    """
    In-memory job queue that mimics ARQ's interface.

    Usage:
        queue = MemoryQueue()

        # Enqueue a job
        await queue.enqueue_job("run_pipeline_job", call_id="abc")

        # Or use the decorator
        @queue.job
        async def my_job(ctx, arg1):
            return arg1 * 2
    """

    def __init__(self, max_workers: int = 4):
        self._jobs: dict[str, MemoryJob] = {}
        self._pending: deque[str] = deque()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._registry: dict[str, Callable] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        # Serialize pipeline jobs to prevent SQLite concurrent write issues.
        # Jobs queue up and run one-at-a-time. This is safe because each
        # pipeline job is internally async (LLM calls use await), so the
        # event loop stays responsive while a job is running.
        self._pipeline_lock = asyncio.Lock()

    def job(self, func: Callable[..., Awaitable]) -> Callable:
        """Decorator to register a job function."""
        self._registry[func.__name__] = func
        return func

    async def enqueue_job(
        self,
        function_name: str,
        *args,
        _job_id: str | None = None,
        **kwargs,
    ) -> str:
        """
        Enqueue a job for async execution.
        Returns the job_id.
        """
        job_id = _job_id or f"job_{uuid.uuid4().hex[:12]}"

        job = MemoryJob(
            job_id=job_id,
            function_name=function_name,
            args=args,
            kwargs=kwargs,
        )
        self._jobs[job_id] = job
        self._pending.append(job_id)

        logger.info(f"[memory_queue] Enqueued job {job_id}: {function_name}")

        # Kick off execution
        asyncio.create_task(self._process_job(job_id))

        return job_id

    async def _process_job(self, job_id: str) -> None:
        """
        Process a single job.

        Uses _pipeline_lock to serialize jobs, preventing SQLite concurrent
        write errors. Jobs still enqueue instantly — they just execute
        one-at-a-time. Each job is internally async so the event loop
        stays responsive while waiting for LLM calls.
        """
        async with self._pipeline_lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            job.status = JobStatus.RUNNING
            logger.info(f"[memory_queue] {job_id}: acquired lock, starting execution")

            func = self._registry.get(job.function_name)
            if func is None:
                job.status = JobStatus.FAILED
                job.error = f"Unknown function: {job.function_name}"
                logger.error(f"[memory_queue] {job_id}: {job.error}")
                return

            try:
                # Prepare a fake ARQ ctx dict
                ctx = {"job_id": job_id, "redis": None}

                if inspect.iscoroutinefunction(func):
                    result = await func(ctx, *job.args, **job.kwargs)
                else:
                    result = func(ctx, *job.args, **job.kwargs)

                job.result = result
                job.status = JobStatus.COMPLETE
                job.completed_at = datetime.utcnow()
                logger.info(f"[memory_queue] {job_id}: completed, releasing lock")
                # Remove from pending deque
                try:
                    self._pending.remove(job_id)
                except ValueError:
                    pass

            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                logger.exception(f"[memory_queue] {job_id}: failed: {e}")
                # Remove from pending deque on failure too
                try:
                    self._pending.remove(job_id)
                except ValueError:
                    pass

    async def get_job_result(self, job_id: str) -> MemoryJob | None:
        """Get the result of a job (for testing / polling)."""
        return self._jobs.get(job_id)

    async def run_until_complete(self, timeout: float = 60.0) -> None:
        """Run all pending jobs to completion. Useful for testing."""
        deadline = asyncio.get_event_loop().time() + timeout
        while self._pending:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError("Queue processing timed out")
            await asyncio.sleep(0.05)


# Global instance — used across the app
_memory_queue: MemoryQueue | None = None


def get_memory_queue() -> MemoryQueue:
    global _memory_queue
    if _memory_queue is None:
        _memory_queue = MemoryQueue()
    return _memory_queue


# ── Decorator for registering jobs ─────────────────────────────────────────────


def register_job(func: Callable[..., Awaitable]) -> Callable:
    """Register a function as a memory queue job."""
    queue = get_memory_queue()
    return queue.job(func)
