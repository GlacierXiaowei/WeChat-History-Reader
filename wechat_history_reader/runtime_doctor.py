from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import plugin_bootstrap as bootstrap


class RuntimeDoctor:
    """Compose read-only runtime health with the existing WeChat diagnosis."""

    def __init__(self, backend: Any = None, state_root: str | Path | None = None):
        self.backend = backend
        self.state_root = state_root

    @staticmethod
    def _marker_state(marker: Path) -> dict[str, Any]:
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def check(self, root: Path | None = None) -> dict[str, Any]:
        package_root = (root or bootstrap.plugin_root()).resolve()
        host = bootstrap._resolve_host_python()
        python_version = ""
        python_supported = False
        if host is not None:
            python_version = bootstrap._python_version(host)
            python_supported = bootstrap._version_tuple(python_version) >= bootstrap.MINIMUM_PYTHON

        environment = bootstrap.venv_root()
        venv_python = bootstrap._venv_python(environment)
        marker_path = bootstrap.install_marker_path()
        marker_state = self._marker_state(marker_path)
        probe = (
            bootstrap._probe_dependencies(venv_python)
            if venv_python.is_file()
            else {"python_version": "", "dependencies": {}}
        )
        dependencies = bootstrap._dependency_report(probe)
        marker_current = bool(
            marker_state
            and bootstrap.install_is_current(
                marker_path,
                package_root / "pyproject.toml",
                bootstrap.PACKAGE_VERSION,
            )
        )

        if host is None:
            status = "python_missing"
            error = bootstrap.MISSING_PYTHON_MESSAGE
        elif not python_supported:
            status = "python_unsupported"
            error = bootstrap.MISSING_PYTHON_MESSAGE
        elif not venv_python.is_file():
            status = "venv_missing"
            error = "The private runtime environment has not been created yet."
        elif not all(item["ok"] for item in dependencies):
            status = "dependencies_missing"
            error = "One or more bundled runtime dependencies are missing or incompatible."
        elif not marker_current:
            status = "marker_stale"
            error = "The runtime marker is missing or stale; run doctor --repair."
        else:
            status = "ready"
            error = None

        wechat: dict[str, Any]
        if self.backend is None:
            wechat = {
                "status": "unavailable",
                "error": "WeChat backend is not configured for this diagnostic.",
            }
        else:
            from .doctor import HistoryDoctor

            wechat = HistoryDoctor(self.backend, self.state_root).check()

        return {
            "status": status,
            "python": {
                "executable": str(host) if host else "",
                "version": python_version,
                "supported": python_supported,
            },
            "venv": {
                "path": str(environment),
                "exists": venv_python.is_file(),
                "python_executable": str(venv_python),
            },
            "marker": {
                "path": str(marker_path),
                "exists": marker_path.is_file(),
                "current": marker_current,
                "state": marker_state,
            },
            "dependencies": dependencies,
            "wechat": wechat,
            "error": error,
        }

    def repair(self, root: Path | None = None) -> dict[str, Any]:
        bootstrap.ensure_runtime(root)
        return self.check(root)
