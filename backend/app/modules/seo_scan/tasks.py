# app/modules/seo_scan/tasks.py
import os

import redis
from rq import Queue

from .worker import run_seo_scan

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_conn = redis.from_url(REDIS_URL)

seo_queue = Queue("seo", connection=_conn)


def enqueue_seo_scan(scan_id: int):
    """
    Schiebt den SEO-Scan in die 'seo'-Queue.
    """
    return seo_queue.enqueue(
        run_seo_scan,
        scan_id,
        job_timeout=1800,
        result_ttl=86400,
        failure_ttl=86400,
    )
