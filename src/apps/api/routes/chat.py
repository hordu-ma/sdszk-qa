"""聊天相关路由。

提供 SSE 流式对话功能。
核心实现：思政教师提问，LLM 提供教学支持回答。
"""

import json
import time
from collections.abc import AsyncGenerator

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.apps.api.config import settings
from src.apps.api.dependencies import CurrentUser, DbSession
from src.apps.api.logging_config import logger
from src.apps.api.models import Case, Message, Session
from src.apps.api.rate_limit import limiter
from src.apps.api.schemas.chat import ChatRequest

router = APIRouter()

# 系统提示词模板（固定角色约束）
SYSTEM_PROMPT = """你是“鲁韵思政”教学支持助手。

【角色与任务】
- 服务对象：山东省大中小学思政教师
- 核心任务：围绕思政课教学设计、教学实施、教学研究提供问答支持

【回答原则】
1. 先给结构化结论，再补充可执行要点
2. 表达准确、克制，不编造政策出处或文件原文
3. 若用户问题信息不足，先说明需要补充的关键信息
4. 输出优先可落地：可给出教学目标、活动设计、评价建议
5. 不输出医疗建议、法律定性结论等越界内容
"""


def build_developer_prompt(case: Case) -> str:
    """构建开发者提示词（包含主题上下文）。

    Args:
        case: 主题对象

    Returns:
        开发者提示词字符串
    """
    physical_exam = case.physical_exam or {}
    visible_signs = physical_exam.get("visible", {})
    on_request_signs = physical_exam.get("on_request", {})

    visible_str = (
        "\n".join(f"  - {k}: {v}" for k, v in visible_signs.items())
        if visible_signs
        else "  - 无"
    )

    on_request_str = (
        "\n".join(f"  - {k}: {v}" for k, v in on_request_signs.items())
        if on_request_signs
        else "  - 无"
    )

    past_history = case.past_history or {}
    diseases = past_history.get("diseases", [])
    allergies = past_history.get("allergies", [])
    medications = past_history.get("medications", [])

    marriage_history = getattr(case, "marriage_childbearing_history", None) or "未提供"
    fam_history = getattr(case, "family_history", None) or "未提供"

    case_num = getattr(case, "case_number", None)
    case_number_line = f"\n主题序号：{case_num}" if case_num else ""

    std_diag = case.standard_diagnosis or {}
    primary_diag = std_diag.get("primary", "未知")
    return f"""当前教学主题上下文：
- 标题：{case.title}
- 难度：{case.difficulty}
- 学段/方向：{case.department}{case_number_line}

参考背景：
- 核心描述：{case.chief_complaint}
- 详细说明：{case.present_illness}
- 补充信息：
  - 疾病史：{", ".join(diseases) if diseases else "无"}
  - 过敏史：{", ".join(allergies) if allergies else "无"}
  - 用药史：{", ".join(medications) if medications else "无"}
- 补充背景字段：{marriage_history}；{fam_history}

结构化数据（如有）：
- visible: {visible_str}
- on_request: {on_request_str}

内部参考答案（仅用于回答质量约束，不要原样暴露）：
- primary: {primary_diag}
"""


def build_messages(
    case: Case,
    history: list[Message],
    user_message: str,
) -> list[dict]:
    """构建发送给 LLM 的消息列表。

    Args:
        case: 主题对象
        history: 历史消息列表
        user_message: 用户当前消息

    Returns:
        OpenAI 格式的消息列表
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_developer_prompt(case)},
    ]

    # 添加历史消息（最近 20 条）
    recent_history = history[-20:] if len(history) > 20 else history
    for msg in recent_history:
        messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    # 添加当前用户消息
    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    return messages


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量。

    简单估算：中文约 1.5 字符/token，英文约 4 字符/token
    混合文本取中间值

    Args:
        text: 输入文本

    Returns:
        估算的 token 数
    """
    # 简单方法：字符数 / 2
    return max(1, len(text) // 2)


def estimate_prompt_tokens(messages: list[dict]) -> int:
    """保守估算 prompt token 数。

    Args:
        messages: OpenAI 格式消息列表

    Returns:
        估算的 token 数（偏保守）
    """
    return sum(max(1, len(str(m.get("content", "")))) for m in messages)


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
        user_tokens = estimate_tokens(data.message)

        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{settings.LLM_BASE_URL}/v1/chat/completions",
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": messages,
                        "stream": True,
                        "temperature": settings.LLM_TEMPERATURE,
                        "max_tokens": max_tokens,
                    },
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        err_msg = f"LLM error: {error_text.decode()}"
                        yield f"data: {json.dumps({'error': err_msg})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:]

                            if data_str.strip() == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data_str)
                                content = (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if content:
                                    full_response += content
                                    chunk_data = {"content": content, "done": False}
                                    yield f"data: {json.dumps(chunk_data)}\n\n"
                            except json.JSONDecodeError:
                                continue

        except httpx.TimeoutException:
            yield f"data: {json.dumps({'error': 'LLM request timeout'})}\n\n"
            return
        except httpx.RequestError as e:
            yield f"data: {json.dumps({'error': f'LLM connection error: {str(e)}'})}\n\n"
            return

        # 6. 流式结束，发送完成信号
        latency_ms = int((time.time() - start_time) * 1000)
        yield f"data: {json.dumps({'content': '', 'done': True, 'latency_ms': latency_ms})}\n\n"

        # 7. 落库：保存用户消息和助手回复（尽量不丢用户输入）
        from src.apps.api.dependencies import AsyncSessionLocal

        async with AsyncSessionLocal() as save_db:
            try:
                save_db.add(
                    Message(
                        session_id=data.session_id,
                        role="user",
                        content=data.message,
                        tokens=user_tokens,
                    )
                )

                if full_response:
                    save_db.add(
                        Message(
                            session_id=data.session_id,
                            role="assistant",
                            content=full_response,
                            tokens=estimate_tokens(full_response),
                            latency_ms=latency_ms,
                        )
                    )

                await save_db.commit()
                logger.debug(
                    "对话消息已保存",
                    session_id=data.session_id,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                await save_db.rollback()
                logger.error(
                    "保存对话消息失败",
                    session_id=data.session_id,
                    error=str(e),
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
