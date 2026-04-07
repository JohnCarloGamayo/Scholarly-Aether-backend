from datetime import datetime, timedelta
import random

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import schemas, models
from ..config import get_settings
from ..db import get_db
from ..security import get_password_hash, verify_password, create_access_token, get_current_user
from ..services.emailer import send_reset_code_email

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=schemas.UserOut)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = models.User(email=payload.email, hashed_password=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    token = create_access_token(user.id)
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", response_model=schemas.MessageResponse)
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()

    # Always return a generic success message to avoid email enumeration.
    generic_message = schemas.MessageResponse(message="If the email exists, a reset code was sent.")
    if not user:
        return generic_message

    # Invalidate existing active codes for this user.
    db.query(models.PasswordResetCode).filter(
        models.PasswordResetCode.user_id == user.id,
        models.PasswordResetCode.used.is_(False),
    ).update({models.PasswordResetCode.used: True}, synchronize_session=False)

    code = f"{random.randint(0, 999999):06d}"
    reset_code = models.PasswordResetCode(
        user_id=user.id,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.password_reset_code_expiry_minutes),
        used=False,
    )
    db.add(reset_code)
    db.commit()

    try:
        send_reset_code_email(user.email, code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to send reset email: {exc}")

    return generic_message


@router.post("/verify-reset-code", response_model=schemas.MessageResponse)
def verify_reset_code(payload: schemas.VerifyResetCodeRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or code")

    reset_code = db.query(models.PasswordResetCode).filter(
        models.PasswordResetCode.user_id == user.id,
        models.PasswordResetCode.code == payload.code,
        models.PasswordResetCode.used.is_(False),
        models.PasswordResetCode.expires_at > datetime.utcnow(),
    ).order_by(models.PasswordResetCode.created_at.desc()).first()

    if not reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    return schemas.MessageResponse(message="Code verified")


@router.post("/reset-password", response_model=schemas.MessageResponse)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or code")

    reset_code = db.query(models.PasswordResetCode).filter(
        models.PasswordResetCode.user_id == user.id,
        models.PasswordResetCode.code == payload.code,
        models.PasswordResetCode.used.is_(False),
        models.PasswordResetCode.expires_at > datetime.utcnow(),
    ).order_by(models.PasswordResetCode.created_at.desc()).first()

    if not reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user.hashed_password = get_password_hash(payload.new_password)
    reset_code.used = True
    db.commit()

    return schemas.MessageResponse(message="Password updated successfully")
