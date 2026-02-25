"""会话模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .cases import Case
    from .messages import Message
    from .scores import Score
    from .test_requests import TestRequest
    from .users import User


class Session(Base, TimestampMixin):
    """会话表。

    记录用户与主题的问答会话。
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, comment="会话ID")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="用户ID"
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, comment="主题ID"
    )

    # 会话状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="in_progress",
        comment="状态：in_progress/ended",
    )

    # 历史兼容字段（纯问答模式当前不使用）
    submitted_diagnosis: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="历史字段（未使用）"
    )

    # 时间记录
    started_at: Mapped[datetime] = mapped_column(server_default="now()", comment="开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True, comment="结束时间")

    # 关系
    user: Mapped["User"] = relationship(back_populates="sessions")
    case: Mapped["Case"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    test_requests: Mapped[list["TestRequest"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    score: Mapped["Score | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, user_id={self.user_id}, "
            f"case_id={self.case_id}, status={self.status})>"
        )
