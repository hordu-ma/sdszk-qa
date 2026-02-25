"""主题相关的 Pydantic schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CaseListItem(BaseModel):
    """主题列表项（不含敏感信息）。"""

    id: int = Field(..., description="主题ID")
    title: str = Field(..., description="主题标题")
    difficulty: str = Field(..., description="难度：easy/medium/hard")
    department: str = Field(..., description="学段/方向")
    is_active: bool = Field(..., description="是否启用")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class CaseDetail(BaseModel):
    """主题详情（基础视图，不含参考答案）。"""

    id: int = Field(..., description="主题ID")
    title: str = Field(..., description="主题标题")
    difficulty: str = Field(..., description="难度")
    department: str = Field(..., description="学段/方向")
    context_info: dict[str, Any] = Field(..., description="背景信息")
    core_question: str = Field(..., description="核心问题/诉求")
    scenario_text: str = Field(..., description="场景说明")
    supplementary_info: dict[str, Any] = Field(..., description="补充信息")

    model_config = ConfigDict(from_attributes=True)


class CaseDetailFull(CaseDetail):
    """主题完整详情（教师端，含参考答案）。"""

    reference_answer: dict[str, Any] = Field(..., description="参考答案")
    key_points: list[str] = Field(..., description="关键教学点")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
