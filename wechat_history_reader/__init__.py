"""Read-only local WeChat history services for the Codex plugin."""

__all__ = ["HistoryService"]


def __getattr__(name: str):
    if name == "HistoryService":
        from .service import HistoryService

        return HistoryService
    raise AttributeError(name)
