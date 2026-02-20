from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete, select

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import (
    Case,
    Message,
    Score,
    Session,
    User,
)
from src.apps.api.models import (
    TestRequest as SessionTestRequest,
)


class _FakeStreamResponse:
    def __init__(self) -> None:
        self.status_code = 200

    async def __aenter__(self) -> _FakeStreamResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False

    async def aiter_lines(self) -> AsyncGenerator[str, None]:
        yield 'data: {"choices":[{"delta":{"content":"你好"}}]}'
        yield "data: [DONE]"

    async def aread(self) -> bytes:
        return b""


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001, ANN002
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False

    def stream(self, method: str, url: str, json: dict) -> _FakeStreamResponse:
        return _FakeStreamResponse()


async def _ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(User.metadata.create_all)


async def _create_user_and_case() -> tuple[int, int, str, str]:
    password = "password123"
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
    username = f"integration_user_{uuid4().hex[:8]}"

    case = Case(
        title="集成测试病例",
        difficulty="easy",
        department="内科",
        patient_info={"age": 30, "gender": "male", "occupation": "测试"},
        chief_complaint="咽痛 2 天",
        present_illness="两天前受凉后咽痛发热",
        past_history={"diseases": [], "allergies": [], "medications": []},
        physical_exam={"visible": {}, "on_request": {}},
        available_tests=[
            {"type": "blood_routine", "name": "血常规", "result": {"wbc": "7.2"}},
            {"type": "ct", "name": "胸部CT", "result": {"impression": "右下肺炎性浸润"}},
        ],
        standard_diagnosis={"primary": "急性上呼吸道感染", "differential": []},
        key_points=["咽痛", "发热"],
        recommended_tests=["blood_routine"],
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
            await db.execute(
                delete(SessionTestRequest).where(SessionTestRequest.session_id.in_(session_ids))
            )
            await db.execute(delete(Score).where(Score.session_id.in_(session_ids)))
            await db.execute(delete(Session).where(Session.id.in_(session_ids)))

        await db.execute(delete(Case).where(Case.id == case_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_e2e_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_tables()
    user_id, case_id, username, password = await _create_user_and_case()

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr("src.apps.api.routes.chat.httpx.AsyncClient", _FakeAsyncClient)

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

            # Order a test via chat and assert system result event is returned.
            order_resp = await client.post(
                "/api/chat/",
                json={"session_id": session_id, "message": "先做个CT"},
                headers=headers,
            )
            assert order_resp.status_code == 200
            order_body = (await order_resp.aread()).decode("utf-8")
            assert '"role": "system"' in order_body
            assert "[检查结果]" in order_body

            # Ensure TestRequest is created.
            async with AsyncSessionLocal() as db:
                tr = (
                    await db.execute(
                        select(SessionTestRequest).where(
                            SessionTestRequest.session_id == session_id,
                            SessionTestRequest.test_type == "ct",
                        )
                    )
                ).scalar_one_or_none()
                assert tr is not None
                assert tr.test_name

            tests_resp = await client.get(
                f"/api/cases/{case_id}/available-tests",
                headers=headers,
            )
            assert tests_resp.status_code == 200

            apply_resp = await client.post(
                f"/api/sessions/{session_id}/tests",
                json={"test_type": "blood_routine"},
                headers=headers,
            )
            assert apply_resp.status_code == 201

            submit_resp = await client.post(
                f"/api/sessions/{session_id}/submit",
                json={"diagnosis": "急性上呼吸道感染"},
                headers=headers,
            )
            assert submit_resp.status_code == 200
            assert submit_resp.json()["score"]["total_score"] >= 0

            score_resp = await client.get(
                f"/api/sessions/{session_id}/score",
                headers=headers,
            )
            assert score_resp.status_code == 200

            list_resp = await client.get("/api/sessions/", headers=headers)
            assert list_resp.status_code == 200
    finally:
        await _cleanup(user_id, case_id)
