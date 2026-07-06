"""In-memory job manager for asynchronous blog generation.

Large blog batches (25-60 posts) take well over the request/proxy timeouts, so
generation is run as a background job instead of inline in the request. Callers
enqueue a job, get a job_id back immediately, and poll for status.

The store is in-process (a single uvicorn worker). This is acceptable because
the generation now runs off the event loop (see routes.py), so the /health probe
stays responsive and Railway no longer restarts the container mid-job. If the
container does restart, in-flight jobs are lost and the caller's poll will 404 —
the caller treats that as "retry".
"""
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional


# Terminal states: "completed", "failed". Active: "queued", "generating", "sending".
class JobManager:
    def __init__(self, max_jobs: int = 500):
        self._jobs: dict = {}
        self._order: list = []
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(self, *, business_name: str, num_blogs: int) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "business_name": business_name,
                "num_blogs": num_blogs,
                "blogs_generated": 0,
                "blogs_sent_to_duda": 0,
                "success": False,
                "message": "Queued",
                "errors": [],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
            }
            self._order.append(job_id)
            self._evict_if_needed()
        return job_id

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(fields)

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _evict_if_needed(self) -> None:
        # Called under lock. Drop oldest completed/failed jobs past the cap.
        while len(self._order) > self._max_jobs:
            oldest = self._order.pop(0)
            self._jobs.pop(oldest, None)


job_manager = JobManager()