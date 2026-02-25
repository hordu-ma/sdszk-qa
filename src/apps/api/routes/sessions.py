from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.apps.api.dependencies import CurrentUser, DbSession
from src.apps.api.models import Case, Message, Session
from src.apps.api.schemas.sessions import (
    MessageItem,
    SessionCreate,
    SessionDetail,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SessionResponse:
    """创建新的问答会话。"""
    if data.mode == "custom":
        topic = (data.topic or "").strip()
        case = Case(
            title=topic,
            difficulty="medium",
            department="通用",
            patient_info={"audience": "思政教师"},
            chief_complaint=f"围绕主题“{topic}”进行教学设计与教研问答支持",
            present_illness="用户自定义主题会话",
            past_history={"diseases": [], "allergies": [], "medications": []},
            physical_exam={"visible": {}, "on_request": {}},
            available_tests=[],
            standard_diagnosis={"primary": "聚焦教学目标、教学活动、教学评价给出建议", "differential": []},
            key_points=["教学目标", "教学活动", "教学评价", "学段适配", "课堂落地"],
            recommended_tests=[],
            marriage_childbearing_history="未提供",
            family_history="未提供",
            is_active=True,
            source="custom",
            generation_meta={"created_by": "custom_topic"},
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)
        case_id = case.id
    else:
        if data.case_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="case_id (topic id) is required when mode=fixed",
            )

        result = await db.execute(
            select(Case).where(Case.id == data.case_id, Case.is_active == True)  # noqa: E712
        )
        case = result.scalar_one_or_none()

        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found or is inactive",
            )
        case_id = data.case_id

    session = Session(
        user_id=current_user.id,
        case_id=case_id,
        status="in_progress",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        case_id=session.case_id,
        status=session.status,
        started_at=session.started_at,
    )


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: str | None = Query(None, alias="status", description="状态筛选"),
) -> SessionListResponse:
    """获取用户会话历史。"""
    base_query = select(Session).where(Session.user_id == current_user.id)

    if status_filter:
        base_query = base_query.where(Session.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    query = (
        base_query.options(selectinload(Session.case))
        .order_by(Session.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    session_ids = [s.id for s in sessions]
    if session_ids:
        msg_count_result = await db.execute(
            select(Message.session_id, func.count(Message.id).label("message_count"))
            .where(Message.session_id.in_(session_ids))
            .group_by(Message.session_id)
        )
        msg_counts = {int(row[0]): int(row[1]) for row in msg_count_result}
    else:
        msg_counts = {}

    items = [
        SessionListItem(
            id=session.id,
            case_id=session.case_id,
            case_title=session.case.title,
            case_difficulty=session.case.difficulty,
            status=session.status,
            started_at=session.started_at,
            ended_at=session.ended_at,
            message_count=msg_counts.get(session.id, 0),
        )
        for session in sessions
    ]

    return SessionListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SessionDetail:
    """获取会话详情（包含消息历史）。"""
    result = await db.execute(
        select(Session)
        .options(
            selectinload(Session.case),
            selectinload(Session.messages),
        )
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    sorted_messages = sorted(session.messages, key=lambda m: m.created_at)

    return SessionDetail(
        id=session.id,
        case_id=session.case_id,
        case_title=session.case.title,
        case_difficulty=session.case.difficulty,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        messages=[
            MessageItem(
                id=msg.id,
                role=_normalize_message_role(msg.role),
                content=msg.content,
                tokens=msg.tokens,
                latency_ms=msg.latency_ms,
                created_at=msg.created_at,
            )
            for msg in sorted_messages
        ],
    )


def _normalize_message_role(role: str) -> Literal["user", "assistant", "system"]:
    if role in {"user", "assistant", "system"}:
        return role
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Invalid message role in DB: {role}",
    )
