from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete, select, text

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import (
    Case,
    Message,
    Session,
    User,
)


async def _fake_stream_chat(*args: object, **kwargs: object) -> AsyncGenerator[str, None]:
    del args, kwargs
    yield "你好"


async def _ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(User.metadata.create_all)


async def _create_user_and_case() -> tuple[int, int, str, str]:
    password = "password123"
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
    username = f"integration_user_{uuid4().hex[:8]}"

    case = Case(
        title="思政教学集成测试主题",
        difficulty="easy",
        department="高中",
        context_info={"teacher_role": "思政教师", "grade": "高一", "class_size": 45},
        core_question="如何设计思政课中的家国情怀教育活动",
        scenario_text="希望设计一堂 45 分钟的主题教学活动",
        supplementary_info={"existing_issues": [], "constraints": [], "available_resources": []},
        reference_answer={"primary": "目标明确、活动闭环、评价可执行"},
        key_points=["教学目标", "教学活动"],
        is_active=True,
        source="fixed",
        generation_meta=None,
    )

    user = User(
        username=username,
        hashed_password=hashed_password,
        full_name="集成测试用户",
        role="student",
        is_active=True,
    )

    async with AsyncSessionLocal() as db:
        db.add_all([user, case])
        await db.commit()
        await db.refresh(user)
        await db.refresh(case)

    return user.id, case.id, username, password


async def _cleanup(user_id: int, case_id: int) -> None:
    async with AsyncSessionLocal() as db:
        # 仅清理当前测试创建的数据，避免全表删除导致锁等待。
        session_ids_result = await db.execute(
            select(Session.id).where(Session.user_id == user_id, Session.case_id == case_id)
        )
        session_ids = [row[0] for row in session_ids_result]

        if session_ids:
            await db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
            await db.execute(delete(Session).where(Session.id.in_(session_ids)))

        await db.execute(delete(Case).where(Case.id == case_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_tables()
    user_id, case_id, username, password = await _create_user_and_case()

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.apps.api.routes.chat.model_client.stream_chat",
        _fake_stream_chat,
    )

    try:
        transport = httpx.ASGITransport(app=app)
        async with real_async_client(transport=transport, base_url="http://test") as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": username, "password": password},
            )
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            session_resp = await client.post(
                "/api/sessions/",
                json={"mode": "fixed", "case_id": case_id},
                headers=headers,
            )
            assert session_resp.status_code == 201
            session_id = session_resp.json()["id"]

            chat_resp = await client.post(
                "/api/chat/",
                json={"session_id": session_id, "message": "您好"},
                headers=headers,
            )
            assert chat_resp.status_code == 200
            body = (await chat_resp.aread()).decode("utf-8")
            assert "data:" in body

            list_resp = await client.get("/api/sessions/", headers=headers)
            assert list_resp.status_code == 200
    finally:
        await _cleanup(user_id, case_id)
