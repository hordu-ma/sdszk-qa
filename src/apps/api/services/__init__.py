"""服务层模块。"""

from typing import Any

__all__ = ["ScoringService"]


def __getattr__(name: str) -> Any:
    if name == "ScoringService":
        from src.apps.api.services.scoring import ScoringService

        return ScoringService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
