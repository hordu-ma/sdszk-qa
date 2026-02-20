import importlib
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注意：部分模块（如 dependencies.engine）在导入阶段读取配置，
# 因此这里必须在测试收集前就设置稳定环境变量。
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/clinic_sim"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["LLM_BASE_URL"] = "http://localhost:8001"
os.environ["LLM_MODEL"] = "qwen2.5-1.5b-instruct"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["LLM_MAX_CONTEXT_LEN"] = "1024"
os.environ["ENV"] = "dev"
os.environ["DEBUG"] = "true"


@pytest.fixture(autouse=True)
def reload_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """确保 Settings 使用稳定的测试环境变量。"""
    # 明确覆盖，避免受本机 shell/.env 漂移影响。
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/clinic_sim",
    )
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minioadmin")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8001")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5-1.5b-instruct")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LLM_MAX_CONTEXT_LEN", "1024")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEBUG", "true")

    import src.apps.api.config as config

    importlib.reload(config)
