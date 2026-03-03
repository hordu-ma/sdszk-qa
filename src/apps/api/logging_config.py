"""日志配置模块

使用 loguru 配置应用日志，支持：
- 控制台彩色输出
- 文件按天轮转
- 结构化日志格式
"""

import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from loguru import logger

from .config import settings

# 上下文变量：存储当前请求的 trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def trace_id_filter(record: Any) -> bool:
    """为日志记录添加 trace_id。"""
    if isinstance(record, dict):
        extra_obj = record.get("extra")
        if isinstance(extra_obj, dict):
            extra_obj["trace_id"] = trace_id_var.get()
    return True


def setup_logging() -> None:
    """配置应用日志。"""
    # 移除默认 handler
    logger.remove()

    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[trace_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 控制台输出
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.ENV == "dev" else "INFO",
        filter=trace_id_filter,
        colorize=True,
    )

    # 文件输出（仅生产环境或明确配置时）
    if settings.ENV != "dev":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            format=(
                log_format.replace("<green>", "")
                .replace("</green>", "")
                .replace("<level>", "")
                .replace("</level>", "")
                .replace("<cyan>", "")
                .replace("</cyan>", "")
            ),
            level="DEBUG",
            filter=trace_id_filter,
            rotation="00:00",
            retention="30 days",
            compression="gz",
            encoding="utf-8",
        )

    logger.info("日志系统初始化完成", env=settings.ENV)


# 导出 logger 供其他模块使用
__all__ = ["logger", "setup_logging", "trace_id_var"]
