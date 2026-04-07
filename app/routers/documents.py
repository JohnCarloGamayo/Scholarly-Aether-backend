from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import os
from pathlib import Path

from .. import models, schemas
from ..db import get_db
from ..security import get_current_user
from ..config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    docs = (
        db.query(models.Document)
        .join(models.CrawlJob, models.Document.crawl_job_id == models.CrawlJob.id)
        .filter(models.CrawlJob.owner_id == current_user.id)
        .order_by(models.Document.created_at.desc())
        .all()
    )
    return docs


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a document and its associated crawl job (cascade)"""
    # Find document and verify ownership
    document = (
        db.query(models.Document)
        .join(models.CrawlJob, models.Document.crawl_job_id == models.CrawlJob.id)
        .filter(
            models.Document.id == document_id,
            models.CrawlJob.owner_id == current_user.id
        )
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete PDF file from storage
    if document.pdf_path:
        try:
            # Extract filename from path (e.g., "/pdfs/summary_xxx.pdf" -> "summary_xxx.pdf")
            filename = document.pdf_path.split("/")[-1]
            pdf_file_path = Path(settings.pdf_output_dir) / filename
            
            if pdf_file_path.exists():
                os.unlink(pdf_file_path)
                print(f"Deleted PDF file: {pdf_file_path}")
        except Exception as e:
            print(f"Error deleting PDF file: {e}")
            # Continue with database deletion even if file deletion fails
    
    # Delete crawl job (will cascade to document due to relationship)
    crawl_job = document.crawl_job
    db.delete(crawl_job)
    db.commit()
    
    return None


@router.post("/{document_id}/share", response_model=schemas.SharedDocumentOut)
def share_document_to_group(
    document_id: str,
    share_request: schemas.ShareDocumentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Share a document to a specific group"""
    # Verify document exists and user owns it
    document = (
        db.query(models.Document)
        .join(models.CrawlJob, models.Document.crawl_job_id == models.CrawlJob.id)
        .filter(
            models.Document.id == document_id,
            models.CrawlJob.owner_id == current_user.id
        )
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Verify group exists and user is a member
    membership = (
        db.query(models.Membership)
        .filter(
            models.Membership.group_id == share_request.group_id,
            models.Membership.user_id == current_user.id,
            models.Membership.status == models.MembershipStatus.accepted
        )
        .first()
    )
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Check if already shared
    existing_share = (
        db.query(models.SharedDocument)
        .filter(
            models.SharedDocument.document_id == document_id,
            models.SharedDocument.group_id == share_request.group_id
        )
        .first()
    )
    
    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document already shared to this group"
        )
    
    # Create shared document
    shared_doc = models.SharedDocument(
        document_id=document.id,
        group_id=share_request.group_id,
        shared_by_id=current_user.id
    )
    
    db.add(shared_doc)
    db.commit()
    db.refresh(shared_doc)
    
    return shared_doc


@router.get("/shared/{group_id}", response_model=list[schemas.SharedDocumentDetail])
def list_shared_documents(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all documents shared to a specific group"""
    print(f"[DEBUG] Fetching shared documents for group_id: {group_id}, user: {current_user.email}")
    
    # Verify user is a member of the group
    membership = (
        db.query(models.Membership)
        .filter(
            models.Membership.group_id == group_id,
            models.Membership.user_id == current_user.id,
            models.Membership.status == models.MembershipStatus.accepted
        )
        .first()
    )
    
    if not membership:
        print(f"[DEBUG] User {current_user.email} is not a member of group {group_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    print(f"[DEBUG] User is a member, fetching shared documents...")
    
    # Get all shared documents for this group with sharer info
    shared_rows = (
        db.query(models.SharedDocument, models.Document, models.User)
        .join(models.Document, models.Document.id == models.SharedDocument.document_id)
        .join(models.User, models.User.id == models.SharedDocument.shared_by_id)
        .filter(models.SharedDocument.group_id == group_id)
        .order_by(models.SharedDocument.shared_at.desc())
        .all()
    )
    
    results: list[schemas.SharedDocumentDetail] = []
    for shared_doc, doc, user in shared_rows:
        results.append(
            schemas.SharedDocumentDetail(
                id=doc.id,
                title=doc.title,
                source_url=doc.source_url,
                pdf_path=doc.pdf_path,
                created_at=doc.created_at,
                shared_at=shared_doc.shared_at,
                shared_by_email=user.email,
            )
        )
    
    print(f"[DEBUG] Found {len(results)} shared documents")
    for item in results:
        print(f"[DEBUG] - Document: {item.id}, Title: {item.title}, Shared by: {item.shared_by_email}")
    
    return results
