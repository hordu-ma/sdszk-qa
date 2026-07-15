"""用户模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .audit_logs import AuditLog
    from .sessions import Session
    from .workbench import TeachingProject


class User(Base, TimestampMixin):
    """用户表。

    存储系统用户信息，包括学生、教师、管理员。
    支持与外部系统用户同步。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="用户名")
    hashed_password: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    full_name: Mapped[str] = mapped_column(String(100), comment="姓名")
    role: Mapped[str] = mapped_column(String(20), comment="角色：student/teacher/admin")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否激活")
    external_user_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True, comment="外部系统用户ID"
    )

    # 关系
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    teaching_projects: Mapped[list["TeachingProject"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
