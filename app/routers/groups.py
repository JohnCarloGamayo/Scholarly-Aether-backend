from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .. import models, schemas
from ..db import get_db
from ..security import get_current_user, get_user_from_token

router = APIRouter(prefix="/groups", tags=["groups"])
class TypingBroker:
    def __init__(self):
        self.group_subscribers: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, group_id: str, payload: dict):
        queues = self.group_subscribers.get(group_id, [])
        for q in queues:
            await q.put(payload)

    def subscribe(self, group_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.group_subscribers.setdefault(group_id, []).append(q)
        return q

    def unsubscribe(self, group_id: str, q: asyncio.Queue):
        if group_id in self.group_subscribers:
            self.group_subscribers[group_id] = [item for item in self.group_subscribers[group_id] if item is not q]
            if not self.group_subscribers[group_id]:
                del self.group_subscribers[group_id]


typing_broker = TypingBroker()


def ensure_membership(db: Session, group_id, user_id):
    membership = (
        db.query(models.Membership)
        .filter(and_(models.Membership.group_id == group_id, models.Membership.user_id == user_id))
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return membership


@router.post("", response_model=schemas.GroupOut)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    group = models.Group(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(group)
    db.flush()
    owner_membership = models.Membership(
        user_id=current_user.id,
        group_id=group.id,
        role=models.GroupRole.owner,
        status=models.MembershipStatus.accepted
    )
    db.add(owner_membership)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=list[schemas.GroupOut])
def list_groups(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    groups = (
        db.query(models.Group)
        .join(models.Membership, models.Membership.group_id == models.Group.id)
        .filter(
            models.Membership.user_id == current_user.id,
            models.Membership.status == models.MembershipStatus.accepted
        )
        .order_by(models.Group.created_at.desc())
        .all()
    )
    return groups


@router.post("/{group_id}/tasks", response_model=schemas.TaskOut)
def create_task(
    group_id: str,
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    task = models.Task(
        group_id=group_id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{group_id}/tasks", response_model=list[schemas.TaskOut])
def list_tasks(group_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    ensure_membership(db, group_id, current_user.id)
    tasks = (
        db.query(models.Task)
        .filter(models.Task.group_id == group_id)
        .order_by(models.Task.created_at.desc())
        .all()
    )
    return tasks


@router.patch("/{group_id}/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    group_id: str,
    task_id: str,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    task = (
        db.query(models.Task)
        .filter(models.Task.id == task_id, models.Task.group_id == group_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = payload.status
    if payload.description is not None:
        task.description = payload.description
    db.commit()
    db.refresh(task)
    return task


@router.get("/{group_id}/members", response_model=list[schemas.MemberOut])
def list_members(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    
    members = (
        db.query(models.User, models.Membership.role)
        .join(models.Membership, models.Membership.user_id == models.User.id)
        .filter(models.Membership.group_id == group_id)
        .all()
    )
    
    return [
        schemas.MemberOut(
            id=user.id,
            email=user.email,
            role=role.value
        )
        for user, role in members
    ]


@router.post("/{group_id}/members", response_model=schemas.MemberOut)
def add_member(
    group_id: str,
    payload: schemas.MemberAdd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    
    # Get group info
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Search by email or user ID
    user = None
    try:
        # Try to parse as UUID first
        from uuid import UUID
        user_uuid = UUID(payload.user_identifier)
        user = db.query(models.User).filter(models.User.id == user_uuid).first()
    except ValueError:
        # If not a valid UUID, search by email
        user = db.query(models.User).filter(models.User.email == payload.user_identifier).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already a member
    existing = (
        db.query(models.Membership)
        .filter(and_(models.Membership.group_id == group_id, models.Membership.user_id == user.id))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")
    
    # Add member with pending status
    membership = models.Membership(
        user_id=user.id,
        group_id=group_id,
        role=models.GroupRole.member,
        status=models.MembershipStatus.pending
    )
    db.add(membership)
    db.flush()
    
    # Create notification for the invited user
    notification = models.Notification(
        user_id=user.id,
        type=models.NotificationType.group_invitation,
        title="Group Invitation",
        message=f"You have been invited to join the group '{group.name}'",
        group_id=group.id,
        membership_id=membership.id
    )
    db.add(notification)
    db.commit()
    
    return schemas.MemberOut(
        id=user.id,
        email=user.email,
        role=models.GroupRole.member.value
    )


@router.patch("/{group_id}", response_model=schemas.GroupOut)
def update_group(
    group_id: str,
    payload: schemas.GroupUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = ensure_membership(db, group_id, current_user.id)
    if membership.role != models.GroupRole.owner:
        raise HTTPException(status_code=403, detail="Only group owners can update the group")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    db.commit()
    db.refresh(group)
    return group



@router.get("/{group_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    
    messages = (
        db.query(models.GroupMessage, models.User.email)
        .join(models.User, models.GroupMessage.user_id == models.User.id)
        .filter(models.GroupMessage.group_id == group_id)
        .order_by(models.GroupMessage.created_at.asc())
        .all()
    )
    
    return [
        schemas.MessageOut(
            id=msg.id,
            user_email=email,
            message=msg.message,
            created_at=msg.created_at
        )
        for msg, email in messages
    ]


@router.post("/{group_id}/messages", response_model=schemas.MessageOut)
def send_message(
    group_id: str,
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    
    message = models.GroupMessage(
        group_id=group_id,
        user_id=current_user.id,
        message=payload.message
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return schemas.MessageOut(
        id=message.id,
        user_email=current_user.email,
        message=message.message,
        created_at=message.created_at
    )


@router.delete("/{group_id}/messages/{message_id}", status_code=204)
def delete_message(
    group_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    message = (
        db.query(models.GroupMessage)
        .filter(models.GroupMessage.id == message_id, models.GroupMessage.group_id == group_id)
        .first()
    )

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")

    db.delete(message)
    db.commit()
    return


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = ensure_membership(db, group_id, current_user.id)
    if membership.role != models.GroupRole.owner:
        raise HTTPException(status_code=403, detail="Only group owners can delete the group")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.query(models.GroupMessage).filter(models.GroupMessage.group_id == group_id).delete(synchronize_session=False)
    db.query(models.Task).filter(models.Task.group_id == group_id).delete(synchronize_session=False)
    db.query(models.Notification).filter(models.Notification.group_id == group_id).delete(synchronize_session=False)
    db.query(models.Membership).filter(models.Membership.group_id == group_id).delete(synchronize_session=False)
    db.delete(group)
    db.commit()
    return


@router.post("/{group_id}/leave", response_model=schemas.MessageOut)
def leave_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = ensure_membership(db, group_id, current_user.id)

    # Record a lightweight system message so remaining members see the departure.
    system_text = json.dumps({"text": f"{current_user.email} left the group", "system": True})
    system_message = models.GroupMessage(group_id=group_id, user_id=current_user.id, message=system_text)
    db.add(system_message)

    db.query(models.Membership).filter(models.Membership.id == membership.id).delete(synchronize_session=False)
    db.commit()
    db.refresh(system_message)

    return schemas.MessageOut(
        id=system_message.id,
        user_email=current_user.email,
        message=system_message.message,
        created_at=system_message.created_at,
    )


@router.post("/{group_id}/typing")
async def send_typing(
    group_id: str,
    payload: schemas.TypingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_membership(db, group_id, current_user.id)
    await typing_broker.publish(group_id, {"user_email": current_user.email, "is_typing": payload.is_typing})
    return {"status": "ok"}


@router.get("/{group_id}/typing/stream")
async def stream_typing(
    request: Request,
    group_id: str,
    token: str,
    db: Session = Depends(get_db),
):
    user = get_user_from_token(token, db)
    ensure_membership(db, group_id, user.id)

    async def event_generator():
        queue = typing_broker.subscribe(group_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield "data: {}\n\n"
                    continue
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            typing_broker.unsubscribe(group_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
