"""FastAPI 应用入口。

提供核心 API 路由和中间件配置。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from .config import settings
from .exceptions import setup_exception_handlers
from .logging_config import logger, setup_logging
from .middleware import (
    AuthContextMiddleware,
    RequestLoggingMiddleware,
    TraceIdMiddleware,
)
from .rate_limit import limiter, rate_limit_exceeded_handler


async def _rate_limit_exception_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RateLimitExceeded):
        raise exc
    return await rate_limit_exceeded_handler(request, exc)


# 初始化日志系统
setup_logging()

# 创建 FastAPI 应用
app = FastAPI(
    title="LuYun SiZheng API",
    version="0.1.0",
    description="鲁韵思政问答系统 API",
    docs_url="/docs" if settings.ENV == "dev" else None,  # 生产环境禁用文档
    redoc_url="/redoc" if settings.ENV == "dev" else None,  # redoc 提升文档可读性
)

# 配置限流器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exception_handler)

# 注册全局异常处理器
setup_exception_handlers(app)

# 添加中间件（注意顺序：后添加的先执行）
# 1. 请求日志中间件
app.add_middleware(RequestLoggingMiddleware)
# 2. 认证上下文中间件（为限流提供 user_id）
app.add_middleware(AuthContextMiddleware)
# 3. Trace ID 中间件（最先执行，确保 trace_id 可用）
app.add_middleware(TraceIdMiddleware)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("FastAPI 应用初始化完成")


# 健康检查端点
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """健康检查端点。

    Returns:
        包含状态信息的字典
    """
    return {"status": "ok", "env": settings.ENV}


# 根路径
@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """API 根路径。

    Returns:
        欢迎信息
    """
    return {
        "message": "LuYun SiZheng API",
        "version": "0.1.0",
        "docs": "/docs" if settings.ENV == "dev" else "disabled",
    }


# 注册路由
from .routes import auth, cases, chat, sessions  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(cases.router, prefix="/api/topics", tags=["topics"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
