"""主题相关路由。

提供主题列表、详情查询等功能。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.dependencies import get_current_user, get_db
from src.apps.api.models import Case, User
from src.apps.api.schemas.cases import CaseDetail, CaseDetailFull, CaseListItem

router = APIRouter()


@router.get("/", response_model=list[CaseListItem], summary="获取主题列表")
async def list_cases(
    db: Annotated[AsyncSession, Depends(get_db)],
    difficulty: Annotated[str | None, Query(description="难度筛选")] = None,
    department: Annotated[str | None, Query(description="学段/方向筛选")] = None,
    skip: Annotated[int, Query(ge=0, description="跳过记录数")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="返回记录数")] = 20,
) -> list[CaseListItem]:
    """获取主题列表（不含内部参考答案）。

    Args:
        db: 数据库会话
        difficulty: 难度筛选（可选）
        department: 学段/方向筛选（可选）
        skip: 跳过记录数
        limit: 返回记录数

    Returns:
        主题列表
    """
    # 默认仅展示库内固定主题；随机主题通过“随机入口”创建，并通过会话复用/回溯。
    query = select(Case).where(
        Case.is_active == True,  # noqa: E712
        Case.source == "fixed",
    )

    if difficulty:
        query = query.where(Case.difficulty == difficulty)

    if department:
        query = query.where(Case.department == department)

    # 分页
    query = query.offset(skip).limit(limit).order_by(Case.created_at.desc())

    result = await db.execute(query)
    cases = result.scalars().all()

    return [CaseListItem.model_validate(case) for case in cases]


@router.get("/{case_id}", summary="获取主题详情")
async def get_case(
    case_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CaseDetail | CaseDetailFull:
    """获取主题详情。

    普通用户返回基础信息（不含内部参考答案）。
    教师/管理员返回完整信息。

    Args:
        case_id: 主题ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        主题详情

    Raises:
        HTTPException: 404 主题不存在
    """
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="主题不存在",
        )

    if current_user.role in ("teacher", "admin"):
        return CaseDetailFull.model_validate(case)
    return CaseDetail.model_validate(case)
