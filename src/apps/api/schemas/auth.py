"""认证相关的 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginCredentials(BaseModel):
    """登录凭证。"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class Token(BaseModel):
    """JWT token 响应。"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    full_name: str = Field(..., description="姓名")
    role: str = Field(..., description="角色")
    is_active: bool = Field(..., description="是否激活")
    external_user_id: str | None = Field(None, description="外部系统用户ID")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)
