from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as aioredis

from app.database import get_db
from app.redis_client import get_redis
from app.models import User
from app.schemas import (
    UserRegisterRequest, UserLoginRequest, TokenRefreshRequest,
    UserResponse, TokenResponse, MessageResponse,
)
from app.security import (
    hash_password, verify_password, create_token_pair, decode_token,
)
from app.dependencies import get_current_user
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db = Depends(get_db)):
    # Check duplicate email
    user_exists = await db.users.find_one({"email": payload.email})
    if user_exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check duplicate username
    username_exists = await db.users.find_one({"username": payload.username})
    if username_exists:
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="developer",
    )
    await db.users.insert_one(user.to_dict())
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    db = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user_doc = await db.users.find_one({"email": payload.email})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = User(**user_doc)
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    tokens = create_token_pair(str(user.id), user.email, user.role)

    # Store refresh token in Redis with expiry
    await redis.setex(
        f"refresh:{str(user.id)}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        tokens["refresh_token"],
    )

    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: TokenRefreshRequest,
    db = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = token_payload.get("sub")
    stored = await redis.get(f"refresh:{user_id}")
    if stored != payload.refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    user = User(**user_doc)
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    tokens = create_token_pair(str(user.id), user.email, user.role)
    await redis.setex(
        f"refresh:{user_id}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        tokens["refresh_token"],
    )
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    await redis.delete(f"refresh:{str(current_user.id)}")
    return {"message": "Successfully logged out", "success": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    cursor = db.users.find({"is_active": True})
    users_doc = await cursor.to_list(length=100)
    return [User(**u) for u in users_doc]
