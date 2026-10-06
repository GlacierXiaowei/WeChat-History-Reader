from __future__ import annotations

from pathlib import Path

from .exporter import HistoryExporter
from .local_backend import LocalHistoryBackend, RuntimePaths
from .service import HistoryService


def create_service(state_root: str | Path | None = None) -> HistoryService:
    paths = RuntimePaths(state_root)
    backend = LocalHistoryBackend(paths)
    exporter = HistoryExporter(paths.exports)
    return HistoryService(backend, exporter, state_root=paths.root)
