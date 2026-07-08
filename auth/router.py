from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import bcrypt
from database.session import get_db
from database.models import User, Portfolio
from auth.jwt import create_access_token, create_refresh_token, verify_token
from auth.deps import get_current_user
from utils.logger import get_logger

log    = get_logger("auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    phone:    str = Field(..., min_length=10, max_length=15)
    name:     str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    phone:    str
    password: str

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    user:          dict

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.phone == req.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Phone already registered")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user = User(phone=req.phone, name=req.name, password_hash=hashed)
    db.add(user)
    await db.flush()
    portfolio = Portfolio(user_id=user.id, virtual_inr=100000.0)
    db.add(portfolio)
    await db.commit()
    await db.refresh(user)
    log.info("auth.register", user_id=user.id)
    return _token_response(user)

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == req.phone))
    user   = result.scalar_one_or_none()
    if not user or not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    return _token_response(user)

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "name": current_user.name, "phone": current_user.phone}

@router.post("/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = verify_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return _token_response(user)

def _token_response(user: User) -> dict:
    return {
        "access_token":  create_access_token(user.id, user.phone),
        "refresh_token": create_refresh_token(user.id),
        "token_type":    "bearer",
        "user": {"id": user.id, "name": user.name, "phone": user.phone}
    }
