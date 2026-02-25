"""审计日志模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .users import User


class AuditLog(Base):
    """审计日志表。

    记录所有用户操作，用于审计和追溯。
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, comment="日志ID")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="用户ID",
    )

    # 操作信息
    action: Mapped[str] = mapped_column(
        String(50), comment="操作类型（如：login、chat、create_session）"
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="资源类型（如：session、case）"
    )
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="资源ID")

    # 详细信息
    details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="操作详情（JSON 格式）"
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="IP 地址")
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="User Agent")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        server_default="now()", comment="创建时间", index=True
    )

    # 关系
    user: Mapped["User | None"] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action})>"
