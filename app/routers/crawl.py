import redis
from rq import Queue
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..security import get_current_user
from ..config import get_settings
from ..tasks.crawl_job import process_crawl_job

router = APIRouter(prefix="/crawl", tags=["crawl"])
settings = get_settings()
queue = None
if settings.use_queue:
    redis_conn = redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=redis_conn)


@router.post("", response_model=schemas.CrawlJobOut)
def crawl_url(
    payload: schemas.CrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    job = models.CrawlJob(url=payload.url, status=models.CrawlStatus.pending, owner_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        if queue:
            queue.enqueue(process_crawl_job, str(job.id), str(current_user.id), payload.url)
        else:
            background_tasks.add_task(process_crawl_job, str(job.id), str(current_user.id), payload.url)
        return job
    except Exception as exc:  # noqa: BLE001
        job.status = models.CrawlStatus.failed
        job.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to enqueue crawl job")


@router.get("", response_model=list[schemas.CrawlJobOut])
def list_crawl_jobs(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    jobs = (
        db.query(models.CrawlJob)
        .filter(models.CrawlJob.owner_id == current_user.id)
        .order_by(models.CrawlJob.created_at.desc())
        .all()
    )
    return jobs


@router.get("/{job_id}", response_model=schemas.CrawlJobOut)
def get_crawl_job(job_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    job = db.query(models.CrawlJob).filter(models.CrawlJob.id == job_id, models.CrawlJob.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
