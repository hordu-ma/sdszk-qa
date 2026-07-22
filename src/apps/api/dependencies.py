"""依赖注入模块。

提供全局依赖，如数据库会话、JWT 验证等。
"""

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models import User

# HTTP Bearer 认证
security = HTTPBearer()

# 创建异步数据库引擎
# 将 psycopg 驱动替换为 asyncpg
async_db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")
engine = create_async_engine(
    async_db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖。

    Yields:
        AsyncSession: 异步数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """获取当前认证用户。

    Args:
        credentials: JWT token
        db: 数据库会话

    Returns:
        当前用户对象

    Raises:
        HTTPException: 401 如果 token 无效或过期
    """
    token = credentials.credentials

    try:
        # 解码 JWT
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str | None = payload.get("sub")

        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
            )

        # 转换为整数
        user_id = int(user_id_str)

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e

    # 从数据库加载用户
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return user


async def get_pilot_user(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """要求当前用户可使用试点工作台（平台 admin 放行，其余须属白名单组织）。"""
    from src.apps.api.exceptions import BusinessError
    from src.apps.api.services.rbac import require_pilot_membership

    try:
        await require_pilot_membership(db, current_user)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return current_user


# 依赖注入类型别名
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PilotUser = Annotated[User, Depends(get_pilot_user)]
