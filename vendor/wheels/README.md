# Offline runtime wheels

This directory is part of the 2.1.1 plugin package. It contains the pinned
`pycryptodome` and `zstandard` Windows x64 wheels used by the first-use
bootstrap. The plugin never downloads project dependencies from PyPI at
runtime.

Python itself is intentionally **not** bundled. Users must install CPython
3.10 or newer before using the plugin. Release builds must contain compatible
wheels for CPython 3.10, 3.11, 3.12, 3.13, and 3.14.

The current bundle pins `pycryptodome==3.24.0` (Windows x64 abi3) and
`zstandard==0.25.0` (one wheel per supported CPython minor version).
Runtime pip uses `--no-index --find-links <plugin-root>/vendor/wheels` and the
bundled `requirements-runtime.txt`; no network fallback is allowed.

Plain `doctor` only checks the environment. Explicit `doctor --repair` or a
business operation runs bootstrap; current dependencies and install marker
skip installation. Missing/stale markers may require offline pip and a marker
update even when imports already work.

`scripts/build_wheels.ps1` is a maintainer-only bundle preparation script and
downloads wheels at build time. It is not a user setup/repair command and
must not be invoked as a runtime installation fallback.
