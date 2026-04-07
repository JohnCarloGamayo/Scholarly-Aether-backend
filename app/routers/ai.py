from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..security import get_current_user
from ..services.llm import LLMClient

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=schemas.ChatResponse)
async def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Fetch context documents scoped to the user
    query = (
        db.query(models.Document)
        .join(models.CrawlJob, models.Document.crawl_job_id == models.CrawlJob.id)
        .filter(models.CrawlJob.owner_id == current_user.id)
        .order_by(models.Document.created_at.desc())
    )

    if payload.document_ids:
        query = query.filter(models.Document.id.in_(payload.document_ids))

    docs = query.limit(5).all()
    if not docs:
        raise HTTPException(status_code=400, detail="No documents available for context")

    context_parts = [f"Title: {d.title}\nURL: {d.source_url}\nSummary: {d.summary}" for d in docs]
    context = "\n\n".join(context_parts)

    llm = LLMClient()
    answer = await llm.answer(payload.question, context)
    return schemas.ChatResponse(answer=answer)
