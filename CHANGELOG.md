# Changelog

## 2.1.1 - 2026-10-06

- Removed the obsolete MCP manifests, server entrypoint, and legacy MCP tool
  wrapper from the formal source tree.
- Kept only the CLI/runtime product path and cleaned generated development
  artifacts from the working directory.
- Made plain `doctor` strictly read-only; dependency repair requires
  `doctor --repair`.

## 2.1.0 - 2026-10-06

- Replaced the public MCP launcher with a Skill-driven local JSON CLI.
- Added first-use offline bootstrap with a private virtual environment and
  bundled Windows x64 dependency wheels.
- Added read-only `doctor` and explicit `doctor --repair`.
- Preserved compact/records reads, snapshots, exports, image decoding, and
  cross-process cursor pagination.
- The 2.0 MCP interface remains available only from the 2.0 release line.
