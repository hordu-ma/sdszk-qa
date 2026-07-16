"""应用配置模块。

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
"""

from pathlib import Path
from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """应用全局配置。"""

    # 数据库配置
    DATABASE_URL: str = Field(..., min_length=1)

    # MinIO 配置
    MINIO_ENDPOINT: str = Field(..., min_length=1)
    MINIO_ACCESS_KEY: str = Field(..., min_length=1)
    MINIO_SECRET_KEY: str = Field(..., min_length=1)
    MINIO_BUCKET: str = "luyun-sizheng-dev"
    MINIO_SECURE: bool = False  # 开发环境使用 HTTP

    # LLM 配置
    LLM_BASE_URL: str = Field(..., min_length=1)
    LLM_MODEL: str = Field(..., min_length=1)
    LLM_PROVIDER: str = "vllm"
    LLM_LOGICAL_MODEL: str = "teaching-chat"
    LLM_TIMEOUT: int = 60  # 请求超时时间（秒）
    LLM_MAX_TOKENS: int = 500  # 最大生成 token 数
    LLM_TEMPERATURE: float = 0.7
    # 模型最大上下文长度（需要与 vLLM 启动参数 --max-model-len 一致）
    LLM_MAX_CONTEXT_LEN: int = 1024

    # 固定版本 vLLM 与模型资产登记。默认值是工程验证资产，不代表专业选型。
    VLLM_RUNTIME_VERSION: str = "0.18.0"
    VLLM_RUNTIME_IMAGE: str = (
        "vllm/vllm-openai:v0.18.0@"
        "sha256:c32358ebfc115d56ade2acfdbcd00df5b115417dbd6006547c88f07e2b39de06"
    )
    VLLM_GENERATION_MODEL: str = "Qwen/Qwen2.5-0.5B-Instruct"
    VLLM_GENERATION_REVISION: str = "7ae557604adf67be50417f59c2c2f167def9a775"
    VLLM_GENERATION_SERVED_NAME: str = "teaching-chat-engineering"

    # 语义 RAG Provider。关闭时保留 pg_trgm + 字符向量降级链。
    SEMANTIC_RAG_ENABLED: bool = False
    EMBEDDING_BASE_URL: str = "http://127.0.0.1:28002"
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_REVISION: str = "7999e1d3359715c523056ef9478215996d62a620"
    EMBEDDING_SERVED_NAME: str = "teaching-embedding"
    EMBEDDING_DIMENSIONS: int = 512
    EMBEDDING_MAX_TOKENS: int = 512
    EMBEDDING_TIMEOUT: int = 60
    RERANKER_BASE_URL: str = "http://127.0.0.1:28003"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_REVISION: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    RERANKER_SERVED_NAME: str = "teaching-reranker"
    RERANKER_TIMEOUT: int = 60
    RERANKER_CANDIDATE_LIMIT: int = 20

    # 阶段 1A 资料处理
    KNOWLEDGE_CHUNK_SIZE: int = 800
    KNOWLEDGE_CHUNK_OVERLAP: int = 100
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    # retrieve_basis 词法检索（pg_trgm word_similarity）最低相关度；
    # 低于该值视为资料不足。经中文样例标定：短语命中约 0.4–0.67，
    # 自然问句约 0.25，无关内容为 0。
    RETRIEVE_MIN_RELEVANCE: float = 0.15
    RETRIEVE_CANDIDATE_LIMIT: int = 200
    RETRIEVE_LEXICAL_WEIGHT: float = 0.7
    RETRIEVE_VECTOR_WEIGHT: float = 0.3

    # 发布清单中的应用版本；由部署环境注入，不从 Git 猜测。
    APP_RELEASE: str = "dev"

    # JWT 配置
    JWT_SECRET: str = Field(..., min_length=1)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 应用环境
    ENV: str = "dev"  # dev / production
    DEBUG: bool = True

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """生产环境安全基线校验。"""
        if self.EMBEDDING_DIMENSIONS != 512:
            raise ValueError("EMBEDDING_DIMENSIONS must match the database vector(512) schema")
        if self.ENV == "production":
            weak_secrets = {"dev-change-me", "test-secret", "changeme"}
            if self.JWT_SECRET in weak_secrets:
                raise ValueError("JWT_SECRET is too weak for production")
        return self


# 全局配置实例
# pydantic-settings 从环境变量/.env 填充 Field(...)，pyright 误报缺少必填参数
settings: Settings = Settings()  # pyright: ignore[reportCallIssue]
