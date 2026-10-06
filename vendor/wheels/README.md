# Offline runtime wheels

This directory is part of the 2.1.0 plugin package. It contains the pinned
`pycryptodome` and `zstandard` Windows x64 wheels used by the first-use
bootstrap. The plugin never downloads project dependencies from PyPI at
runtime.

Python itself is intentionally **not** bundled. Users must install CPython
3.10 or newer before using the plugin. Release builds must contain compatible
wheels for CPython 3.10, 3.11, 3.12, 3.13, and 3.14.
