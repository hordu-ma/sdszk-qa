"""聊天相关路由。

提供 SSE 流式对话功能。
核心实现：思政教师提问，LLM 提供教学支持回答。
"""

import json
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.apps.api.config import settings
from src.apps.api.dependencies import CurrentUser, DbSession
from src.apps.api.logging_config import logger
from src.apps.api.models import Message, Session
from src.apps.api.rate_limit import limiter
from src.apps.api.schemas.chat import ChatRequest
from src.apps.api.services.audit import write_audit_log
from src.apps.api.services.chat_orchestration import (
    build_messages,
    estimate_prompt_tokens,
    estimate_tokens,
)
from src.apps.api.services.model_gateway import ModelGatewayError, model_client

router = APIRouter()

@router.post("/")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    data: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """SSE 流式对话接口。

    用户发送问题，LLM 流式返回教学支持回答。
    限流：每用户每分钟最多 20 次请求。

    Args:
        request: FastAPI Request 对象（限流需要）
        data: 聊天请求（session_id, message）
        db: 数据库会话
        current_user: 当前用户

    Returns:
        StreamingResponse: SSE 流式响应

    Raises:
        HTTPException: 403 如果用户无权访问会话
        HTTPException: 404 如果会话不存在
        HTTPException: 400 如果会话已结束
    """
    # 1. 查询会话（包含主题和历史消息）
    result = await db.execute(
        select(Session)
        .options(
            selectinload(Session.case),
            selectinload(Session.messages),
        )
        .where(Session.id == data.session_id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # 2. 权限检查
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # 3. 检查会话状态
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is {session.status}, cannot continue chat",
        )

    case = session.case

    async def persist_chat_result(
        user_content: str,
        assistant_content: str | None,
        *,
        latency_ms: int | None,
        error: str | None = None,
    ) -> None:
        """保存聊天消息与审计日志（失败不影响响应）。"""
        from src.apps.api.dependencies import AsyncSessionLocal

        async with AsyncSessionLocal() as save_db:
            try:
                save_db.add(
                    Message(
                        session_id=data.session_id,
                        role="user",
                        content=user_content,
                        tokens=estimate_tokens(user_content),
                    )
                )
                if assistant_content:
                    save_db.add(
                        Message(
                            session_id=data.session_id,
                            role="assistant",
                            content=assistant_content,
                            tokens=estimate_tokens(assistant_content),
                            latency_ms=latency_ms,
                        )
                    )
                await write_audit_log(
                    db=save_db,
                    request=request,
                    action="chat_failed" if error else "chat_completed",
                    user_id=current_user.id,
                    resource_type="session",
                    resource_id=str(data.session_id),
                    details={
                        "error": error,
                        "latency_ms": latency_ms,
                    },
                )
                await save_db.commit()
            except Exception as e:
                await save_db.rollback()
                logger.error("保存对话或审计失败", session_id=data.session_id, error=str(e))

    # 4. 构建消息
    history = sorted(session.messages, key=lambda m: m.created_at)
    messages = build_messages(case, history, data.message)
    prompt_tokens = estimate_prompt_tokens(messages)
    available_tokens = settings.LLM_MAX_CONTEXT_LEN - prompt_tokens
    if available_tokens < 16:
        logger.warning(
            "上下文过长，无法继续生成",
            session_id=data.session_id,
            prompt_tokens=prompt_tokens,
            max_context=settings.LLM_MAX_CONTEXT_LEN,
        )

        async def over_limit_generator() -> AsyncGenerator[str, None]:
            await persist_chat_result(
                user_content=data.message,
                assistant_content=None,
                latency_ms=None,
                error="context_too_long",
            )
            yield "data: " + json.dumps({"error": "上下文过长，请结束会话或减少消息"}) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            over_limit_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    max_tokens = min(settings.LLM_MAX_TOKENS, available_tokens)

    # 5. 创建 SSE 生成器
    async def event_generator() -> AsyncGenerator[str, None]:
        full_response = ""
        start_time = time.time()

        try:
            async for content in model_client.stream_chat(
                messages,
                user_id=current_user.id,
                max_tokens=max_tokens,
            ):
                full_response += content
                chunk_data = {"content": content, "done": False}
                yield f"data: {json.dumps(chunk_data)}\n\n"
        except ModelGatewayError as e:
            error_msg = str(e)
            await persist_chat_result(
                user_content=data.message,
                assistant_content=None,
                latency_ms=None,
                error=error_msg,
            )
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return

        # 6. 流式结束，发送完成信号
        latency_ms = int((time.time() - start_time) * 1000)
        yield f"data: {json.dumps({'content': '', 'done': True, 'latency_ms': latency_ms})}\n\n"

        # 7. 落库：保存用户消息和助手回复（尽量不丢用户输入）
        await persist_chat_result(
            user_content=data.message,
            assistant_content=full_response if full_response else None,
            latency_ms=latency_ms,
        )
        logger.debug(
            "对话消息已保存",
            session_id=data.session_id,
            latency_ms=latency_ms,
        )

        # 发送最终的 [DONE] 信号
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
