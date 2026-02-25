"""认证相关路由。

提供用户登录、JWT 验证等功能。
"""

from datetime import timedelta
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.dependencies import get_current_user, get_db
from src.apps.api.logging_config import logger
from src.apps.api.models import User
from src.apps.api.schemas.auth import LoginCredentials, Token, UserResponse
from src.apps.api.services.audit import write_audit_log
from src.apps.api.utils.jwt import create_access_token

router = APIRouter()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码。

    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码

    Returns:
        是否匹配
    """
    # bcrypt 限制密码最大 72 字节
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """验证用户凭证。

    Args:
        db: 数据库会话
        username: 用户名
        password: 密码

    Returns:
        用户对象，如果验证失败返回 None
    """
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user


@router.post("/login", response_model=Token, summary="用户登录")
async def login(
    request: Request,
    credentials: LoginCredentials,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """用户登录，返回 JWT token。

    Args:
        credentials: 登录凭证
        db: 数据库会话

    Returns:
        JWT token

    Raises:
        HTTPException: 认证失败
    """
    user = await authenticate_user(db, credentials.username, credentials.password)

    if not user:
        await write_audit_log(
            db=db,
            request=request,
            action="login_failed",
            details={"username": credentials.username},
        )
        await db.commit()
        logger.warning("登录失败", username=credentials.username, reason="用户名或密码错误")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成 JWT token
    access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )

    await write_audit_log(
        db=db,
        request=request,
        action="login_success",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"username": user.username},
    )
    await db.commit()

    logger.info("用户登录成功", user_id=user.id, username=user.username)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """获取当前登录用户信息。

    Args:
        current_user: 当前用户（从 JWT token 解析）

    Returns:
        用户信息
    """
    return UserResponse.model_validate(current_user)
