import os
import redis
from rq import Worker, Queue, Connection

from app.config import get_settings
from app.tasks.crawl_job import process_crawl_job


def start_worker():
    settings = get_settings()
    redis_url = settings.redis_url
    redis_conn = redis.from_url(redis_url)

    with Connection(redis_conn):
        queue = Queue(settings.rq_queue_name)
        worker = Worker([queue])
        worker.work()


if __name__ == "__main__":
    start_worker()
