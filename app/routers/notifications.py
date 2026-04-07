from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notifications = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )
    return notifications


@router.patch("/{notification_id}/read")
def mark_as_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    return {"status": "ok"}


@router.post("/{notification_id}/respond")
def respond_to_invitation(
    notification_id: str,
    payload: schemas.InvitationResponse,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id,
            models.Notification.type == models.NotificationType.group_invitation,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if not notification.membership_id:
        raise HTTPException(status_code=400, detail="Invalid notification")
    
    membership = db.query(models.Membership).filter(
        models.Membership.id == notification.membership_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    if membership.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to respond to this invitation")

    if membership.status in [models.MembershipStatus.accepted, models.MembershipStatus.rejected]:
        raise HTTPException(status_code=400, detail="Invitation already handled")
    
    if payload.accept:
        membership.status = models.MembershipStatus.accepted
    else:
        membership.status = models.MembershipStatus.rejected
    
    notification.is_read = True
    db.commit()
    
    return {"status": "accepted" if payload.accept else "rejected"}
