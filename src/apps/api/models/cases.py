"""主题模型（沿用历史表名 cases）。"""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .sessions import Session


class Case(Base, TimestampMixin):
    """主题表。

    存储思政教学主题/场景数据，供问答会话使用。
    """

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, comment="主题ID")
    title: Mapped[str] = mapped_column(String(200), comment="主题标题")
    difficulty: Mapped[str] = mapped_column(String(20), comment="难度：easy/medium/hard")
    department: Mapped[str] = mapped_column(String(50), comment="学段/方向")

    # 主题内容字段
    context_info: Mapped[dict] = mapped_column(JSON, comment="背景信息（教师角色、年级等）")
    core_question: Mapped[str] = mapped_column(Text, comment="核心问题/诉求")
    scenario_text: Mapped[str] = mapped_column(Text, comment="场景说明")
    supplementary_info: Mapped[dict] = mapped_column(JSON, comment="补充信息")

    # 内部参考答案（仅教师端可见）
    reference_answer: Mapped[dict] = mapped_column(JSON, comment="参考答案")
    key_points: Mapped[list] = mapped_column(JSON, comment="关键教学点列表")

    # 主题来源
    source: Mapped[str] = mapped_column(
        String(20),
        default="fixed",
        comment="主题来源：fixed（内置）/custom（用户自定义）",
    )
    generation_meta: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="生成元信息",
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")

    # 关系
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, title={self.title}, difficulty={self.difficulty})>"
