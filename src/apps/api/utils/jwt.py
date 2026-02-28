"""JWT 令牌工具。"""

from datetime import UTC, datetime, timedelta
from typing import TypeAlias

import jwt

from src.apps.api.config import settings

# JWT payload 值的合法类型
JWTValue: TypeAlias = str | int | float | datetime


def create_access_token(
    data: dict[str, JWTValue],
    expires_delta: timedelta | None = None,
) -> str:
    """创建 JWT access token。

    Args:
        data: 要编码的数据（通常包含 sub: user_id）
        expires_delta: 过期时间间隔

    Returns:
        JWT token 字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.JWT_EXPIRE_MINUTES,
        )

    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt
