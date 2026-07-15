"""逻辑模型客户端和 OpenAI 兼容 Provider Adapter。"""

import json
import time
from collections.abc import AsyncGenerator

import httpx

from src.apps.api.config import settings
from src.apps.api.logging_config import logger
from src.apps.api.models import ModelCallAudit


class ModelGatewayError(Exception):
    """统一模型调用错误。"""

    def __init__(self, message: str, code: str) -> None:
        self.code = code
        super().__init__(message)


class ModelClient:
    """业务只感知逻辑模型名的最小 ModelClient。"""

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: int | None,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """流式调用当前登记的 OpenAI 兼容 Provider。"""
        started = time.monotonic()
        status = "completed"
        error_code: str | None = None
        completion_chars = 0
        try:
            is_ollama = settings.LLM_PROVIDER.lower() == "ollama"
            if is_ollama:
                url = f"{settings.LLM_BASE_URL.rstrip('/')}/api/chat"
                payload = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "think": False,
                    "options": {
                        "temperature": settings.LLM_TEMPERATURE,
                        "num_predict": max_tokens,
                    },
                }
            else:
                url = f"{settings.LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
                payload = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_tokens": max_tokens,
                }
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode(errors="replace")[:500]
                        raise ModelGatewayError(
                            f"模型服务返回 {response.status_code}: {body}",
                            "provider_error",
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data_str = (
                            line.strip()
                            if is_ollama
                            else line.removeprefix("data: ").strip()
                        )
                        if not is_ollama and not line.startswith("data: "):
                            continue
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if is_ollama:
                            content = chunk.get("message", {}).get("content", "")
                            done = bool(chunk.get("done"))
                        else:
                            content = (
                                chunk.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            done = False
                        if content:
                            completion_chars += len(content)
                            yield content
                        if done:
                            break
        except httpx.TimeoutException as exc:
            status = "failed"
            error_code = "timeout"
            raise ModelGatewayError("模型请求超时", error_code) from exc
        except httpx.RequestError as exc:
            status = "failed"
            error_code = "connection_error"
            raise ModelGatewayError(f"模型连接失败: {exc}", error_code) from exc
        except ModelGatewayError as exc:
            status = "failed"
            error_code = exc.code
            raise
        finally:
            await self._write_audit(
                user_id=user_id,
                status=status,
                latency_ms=int((time.monotonic() - started) * 1000),
                prompt_tokens=sum(len(item.get("content", "")) for item in messages),
                completion_tokens=max(0, completion_chars // 2),
                error_code=error_code,
            )

    async def _write_audit(
        self,
        *,
        user_id: int | None,
        status: str,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        error_code: str | None,
    ) -> None:
        from src.apps.api.dependencies import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                db.add(
                    ModelCallAudit(
                        user_id=user_id,
                        logical_model=settings.LLM_LOGICAL_MODEL,
                        provider=settings.LLM_PROVIDER,
                        provider_model_id=settings.LLM_MODEL,
                        operation="chat.completions",
                        status=status,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        error_code=error_code,
                        details={"base_url": settings.LLM_BASE_URL},
                    )
                )
                await db.commit()
        except Exception as exc:
            logger.warning("模型调用审计写入失败", error=str(exc))


model_client = ModelClient()
