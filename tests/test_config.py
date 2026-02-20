from src.apps.api.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/clinic_sim",
        MINIO_ENDPOINT="localhost:9000",
        MINIO_ACCESS_KEY="minioadmin",
        MINIO_SECRET_KEY="minioadmin",
        LLM_BASE_URL="http://localhost:8001",
        LLM_MODEL="qwen2.5-1.5b-instruct",
        JWT_SECRET="test-secret",
    )

    assert settings.CORS_ORIGINS == ["http://localhost:5173"]
    assert settings.LLM_TIMEOUT == 60
    assert settings.LLM_MAX_TOKENS == 500
    assert settings.LLM_MAX_CONTEXT_LEN == 1024
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.MINIO_SECURE is False
