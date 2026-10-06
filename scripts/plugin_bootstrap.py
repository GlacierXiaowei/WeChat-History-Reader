from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PACKAGE_VERSION = "2.1.1"
MINIMUM_PYTHON = (3, 10)
REQUIRED_DEPENDENCIES = {
    "pycryptodome": ("3.23.0", "Crypto"),
    "zstandard": ("0.22.0", "zstandard"),
}
MISSING_PYTHON_MESSAGE = (
    "WeChat History Reader requires Python 3.10 or newer. "
    "Install Python 3.10+ and make sure the Windows Python launcher or python command is available."
)


@dataclass
class RuntimeReport:
    status: str
    python_executable: str = ""
    python_version: str = ""
    venv_path: str = ""
    marker_path: str = ""
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    installed: bool = False
    error: str | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "python_executable": self.python_executable,
            "python_version": self.python_version,
            "venv_path": self.venv_path,
            "marker_path": self.marker_path,
            "dependencies": self.dependencies,
            "installed": self.installed,
            "error": self.error,
        }


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_root(root: Path | None = None) -> Path:
    override = os.environ.get("WECHAT_HISTORY_READER_RUNTIME_ROOT", "").strip()
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(local_app_data) / "WeChatHistoryReader" / "runtime"


def venv_root(root: Path | None = None) -> Path:
    return runtime_root(root) / "venv"


def install_marker_path(root: Path | None = None) -> Path:
    return runtime_root(root) / "install-state.json"


def _venv_python(venv_root_path: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_name = "python.exe" if os.name == "nt" else "python"
    return venv_root_path / scripts_dir / python_name


def build_cli_command(
    venv_root_path: Path, arguments: list[str] | None = None
) -> list[str]:
    return [
        str(_venv_python(venv_root_path)),
        "-m",
        "wechat_history_reader.cli",
        *(arguments or []),
    ]


def build_host_cli_command(
    python_executable: Path, arguments: list[str] | None = None
) -> list[str]:
    return [
        str(python_executable),
        "-m",
        "wechat_history_reader.cli",
        *(arguments or []),
    ]


def build_install_command(venv_root_path: Path, root: Path) -> list[str]:
    wheels = root / "vendor" / "wheels"
    requirements = root / "requirements-runtime.txt"
    return [
        str(_venv_python(venv_root_path)),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--quiet",
        "--no-index",
        "--find-links",
        str(wheels),
        "-r",
        str(requirements),
    ]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_hash(project_file: Path) -> str:
    return _hash_file(project_file)


def _source_hash(root: Path) -> str:
    """Fingerprint runtime inputs independently of the plugin cache path."""
    files: set[Path] = set()
    for name in (
        "pyproject.toml",
        "plugin.json",
        ".codex-plugin/plugin.json",
        "requirements-runtime.txt",
    ):
        path = root / name
        if path.is_file():
            files.add(path)
    source_suffixes = {".py", ".pyi", ".js", ".json", ".pyd", ".dll"}
    for directory, suffixes in (
        (root / "wechat_history_reader", source_suffixes),
        (root / "scripts", source_suffixes | {".cmd", ".bat", ".ps1", ".sh"}),
    ):
        if not directory.is_dir():
            continue
        files.update(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in suffixes
            and "__pycache__" not in path.relative_to(directory).parts
        )
    digest = hashlib.sha256(b"wechat-history-reader-runtime-v2.1\0")
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_hash_file(path)))
    return digest.hexdigest()


def _wheel_bundle_hash(root: Path) -> str:
    directory = root / "vendor" / "wheels"
    digest = hashlib.sha256(b"wechat-history-reader-wheel-bundle-v1\0")
    if not directory.is_dir():
        return digest.hexdigest()
    for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_hash_file(path)))
    return digest.hexdigest()


def _install_state(
    project_file: Path,
    package_version: str,
    *,
    host_python_version: str = "",
    platform_tag: str = "",
    installed_dependencies: dict[str, str] | None = None,
) -> dict[str, Any]:
    root = project_file.parent
    return {
        "package_version": package_version,
        "pyproject_sha256": _project_hash(project_file),
        "source_sha256": _source_hash(root),
        "wheel_bundle_sha256": _wheel_bundle_hash(root),
        "host_python_version": host_python_version,
        "platform_tag": platform_tag or platform.platform(),
        "installed_dependencies": installed_dependencies or {},
    }


def install_is_current(marker: Path, project_file: Path, package_version: str) -> bool:
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(state, dict) or not state.get("source_sha256"):
        return False
    expected = _install_state(project_file, package_version)
    required_keys = (
        "package_version",
        "pyproject_sha256",
        "source_sha256",
        "wheel_bundle_sha256",
    )
    return all(state.get(key) == expected.get(key) for key in required_keys)


def _write_install_marker(marker: Path, state: dict[str, Any]) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(marker.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(marker)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in str(value).split("."):
        number = ""
        for character in part:
            if character.isdigit():
                number += character
            else:
                break
        if not number:
            break
        parts.append(int(number))
    return tuple(parts)


def _resolve_host_python() -> Path | None:
    candidates = [Path(sys.executable)]
    if os.name == "nt":
        candidates.extend([Path("py"), Path("python")])
    else:
        candidates.append(Path("python3"))
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate == Path(sys.executable):
            if sys.version_info >= MINIMUM_PYTHON:
                return candidate
            continue
        try:
            completed = subprocess.run(
                [
                    str(candidate),
                    "-c",
                    "import sys; print('.'.join(map(str, sys.version_info[:3])))",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        version = completed.stdout.strip()
        if completed.returncode == 0 and _version_tuple(version) >= MINIMUM_PYTHON:
            return candidate
    return None


def _python_version(python_executable: Path) -> str:
    if python_executable == Path(sys.executable):
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            "import sys; print('.'.join(map(str, sys.version_info[:3])))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def _create_venv(host_python: Path, environment: Path) -> None:
    del host_python
    if environment.exists() and _venv_python(environment).is_file():
        return
    venv.EnvBuilder(
        with_pip=True,
        clear=environment.exists(),
        symlinks=False,
    ).create(environment)


_PROBE_SCRIPT = r"""
import importlib.metadata as metadata
import json
import sys
result = {"python_version": ".".join(map(str, sys.version_info[:3])), "dependencies": {}}
for name in ("pycryptodome", "zstandard"):
    try:
        result["dependencies"][name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        pass
for module in ("Crypto", "zstandard"):
    try:
        __import__(module)
    except Exception:
        result.setdefault("import_errors", []).append(module)
print(json.dumps(result))
"""


def _probe_dependencies(python_executable: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(python_executable), "-c", _PROBE_SCRIPT],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {
            "python_version": "",
            "dependencies": {},
            "probe_error": str(exc),
        }
    if completed.returncode != 0:
        return {
            "python_version": "",
            "dependencies": {},
            "probe_error": completed.stderr.strip(),
        }
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "python_version": "",
            "dependencies": {},
            "probe_error": "dependency probe returned invalid JSON",
        }
    return value if isinstance(value, dict) else {"python_version": "", "dependencies": {}}


def _dependency_report(probe: dict[str, Any]) -> list[dict[str, Any]]:
    installed = probe.get("dependencies", {})
    import_errors = set(probe.get("import_errors", []))
    result = []
    for name, (required, module) in REQUIRED_DEPENDENCIES.items():
        actual = str(installed.get(name, "") or "")
        ok = (
            bool(actual)
            and _version_tuple(actual) >= _version_tuple(required)
            and module not in import_errors
        )
        result.append(
            {
                "name": name,
                "required": f">={required}",
                "installed": actual,
                "ok": ok,
            }
        )
    return result


def _dependencies_ok(probe: dict[str, Any]) -> bool:
    return all(item["ok"] for item in _dependency_report(probe))


def ensure_runtime(root: Path | None = None) -> RuntimeReport:
    root = Path(root or plugin_root()).resolve()
    marker = install_marker_path()
    environment = venv_root()
    host = _resolve_host_python()
    if host is None:
        return RuntimeReport(
            status="python_missing",
            venv_path=str(environment),
            marker_path=str(marker),
            error=MISSING_PYTHON_MESSAGE,
        )

    host_version = _python_version(host)
    if _version_tuple(host_version) < MINIMUM_PYTHON:
        return RuntimeReport(
            status="python_unsupported",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            error=MISSING_PYTHON_MESSAGE,
        )

    runtime_root().mkdir(parents=True, exist_ok=True)
    try:
        _create_venv(host, environment)
    except Exception as exc:
        return RuntimeReport(
            status="dependency_install_failed",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            error=f"Could not create the private Python environment: {exc}",
        )
    venv_python = _venv_python(environment)
    probe = _probe_dependencies(venv_python)
    dependency_details = _dependency_report(probe)
    current = install_is_current(marker, root / "pyproject.toml", PACKAGE_VERSION)
    if current and _dependencies_ok(probe):
        return RuntimeReport(
            status="ready",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            dependencies=dependency_details,
            installed=False,
        )

    wheels = root / "vendor" / "wheels"
    if not wheels.is_dir() or not any(wheels.glob("*.whl")):
        return RuntimeReport(
            status="wheel_unavailable",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            dependencies=dependency_details,
            error=(
                f"No compatible dependency wheels were found in {wheels}. "
                "Build or reinstall the plugin package before retrying."
            ),
        )

    command = build_install_command(environment, root)
    completed = subprocess.run(
        command,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output = (completed.stdout or "").strip()
        return RuntimeReport(
            status="dependency_install_failed",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            dependencies=dependency_details,
            error=(
                f"Offline dependency installation failed with exit code "
                f"{completed.returncode}. {output}"
            ).strip(),
        )

    verified = _probe_dependencies(venv_python)
    dependency_details = _dependency_report(verified)
    if not _dependencies_ok(verified):
        return RuntimeReport(
            status="dependency_install_failed",
            python_executable=str(host),
            python_version=host_version,
            venv_path=str(environment),
            marker_path=str(marker),
            dependencies=dependency_details,
            installed=True,
            error=(
                "Offline dependency installation completed but required imports "
                "or versions are still unavailable."
            ),
        )
    state = _install_state(
        root / "pyproject.toml",
        PACKAGE_VERSION,
        host_python_version=host_version,
        installed_dependencies=verified.get("dependencies", {}),
    )
    _write_install_marker(marker, state)
    return RuntimeReport(
        status="ready",
        python_executable=str(host),
        python_version=host_version,
        venv_path=str(environment),
        marker_path=str(marker),
        dependencies=dependency_details,
        installed=True,
    )


def ensure_environment(root: Path | None = None) -> Path:
    """Compatibility wrapper for old launchers; raises on actionable failures."""
    report = ensure_runtime(root)
    if report.status != "ready":
        raise RuntimeError(report.error or report.status)
    return Path(report.venv_path)


def run_cli(arguments: list[str] | None = None, root: Path | None = None) -> int:
    arguments = list(arguments or [])
    read_only_doctor = "doctor" in arguments and "--repair" not in arguments
    if read_only_doctor:
        environment = venv_root()
        venv_python = _venv_python(environment)
        target = venv_python if venv_python.is_file() else _resolve_host_python()
        if target is None:
            report = RuntimeReport(
                status="python_missing",
                venv_path=str(environment),
                marker_path=str(install_marker_path()),
                error=MISSING_PYTHON_MESSAGE,
            )
            print(json.dumps(report.as_dict(), ensure_ascii=False), file=sys.stderr)
            return 1
        command = (
            build_cli_command(environment, arguments)
            if target == venv_python
            else build_host_cli_command(target, arguments)
        )
        completed = subprocess.run(
            command,
            cwd=str((root or plugin_root()).resolve()),
            check=False,
        )
        return completed.returncode

    report = ensure_runtime(root)
    if report.status != "ready":
        print(json.dumps(report.as_dict(), ensure_ascii=False), file=sys.stderr)
        return 1
    command = build_cli_command(Path(report.venv_path), arguments)
    completed = subprocess.run(
        command, cwd=str((root or plugin_root()).resolve()), check=False
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if arguments and arguments[0] == "run":
        arguments = arguments[2:] if arguments[1:2] == ["--"] else arguments[1:]
    return run_cli(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
