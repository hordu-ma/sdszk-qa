"""应用配置模块。

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
"""

from pathlib import Path
from typing import Any, cast

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（回到 clinic-sim）
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """应用全局配置。"""

    # 数据库配置
    DATABASE_URL: str = Field(..., min_length=1)

    # MinIO 配置
    MINIO_ENDPOINT: str = Field(..., min_length=1)
    MINIO_ACCESS_KEY: str = Field(..., min_length=1)
    MINIO_SECRET_KEY: str = Field(..., min_length=1)
    MINIO_BUCKET: str = "clinic-sim-dev"
    MINIO_SECURE: bool = False  # 开发环境使用 HTTP

    # LLM 配置
    LLM_BASE_URL: str = Field(..., min_length=1)
    LLM_MODEL: str = Field(..., min_length=1)
    LLM_TIMEOUT: int = 60  # 请求超时时间（秒）
    LLM_MAX_TOKENS: int = 500  # 最大生成 token 数
    LLM_TEMPERATURE: float = 0.7
    # 模型最大上下文长度（需要与 vLLM 启动参数 --max-model-len 一致）
    LLM_MAX_CONTEXT_LEN: int = 1024

    # LLM 病例随机生成配置（独立于对话生成，避免被 LLM_MAX_TOKENS 过小限制）
    # 注意：最终请求会被按 LLM_MAX_CONTEXT_LEN 自动截断，避免 vLLM 因超出上下文而 400。
    LLM_CASE_GEN_MAX_TOKENS: int = 1200
    LLM_CASE_GEN_TEMPERATURE: float = 0.8
    LLM_CASE_GEN_RETRIES: int = 2

    # JWT 配置
    JWT_SECRET: str = Field(..., min_length=1)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 应用环境
    ENV: str = "dev"  # dev / production
    DEBUG: bool = True

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """生产环境安全基线校验。"""
        if self.ENV == "production":
            weak_secrets = {"dev-change-me", "test-secret", "changeme"}
            if self.JWT_SECRET in weak_secrets:
                raise ValueError("JWT_SECRET is too weak for production")
        return self


# 全局配置实例
settings_factory = cast(Any, Settings)
settings = settings_factory()
