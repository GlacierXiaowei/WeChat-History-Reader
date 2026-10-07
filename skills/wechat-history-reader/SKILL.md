---
name: wechat-history-reader
description: Use when the user wants to read, search, summarize, configure, diagnose, export, or decode images from local WeChat history with WeChat History Reader 2.1.1.
---

# WeChat History Reader 2.1.1

This version is Skill-only with a local JSON CLI, not an MCP server. Do not
invoke old MCP tools or restore their manifests or server entrypoints.

For `<plugin-root>/skills/wechat-history-reader/SKILL.md`, resolve
`<plugin-root>` from the skill's location, not from the user's current project.
Use that plugin's bundled
`scripts/plugin_bootstrap.cmd` launcher for every operation. The examples
below are relative to the plugin root; in PowerShell use `&` with the quoted
absolute launcher path when calling from another directory or a path with spaces.
The launcher finds the user's Python installation, creates the private runtime
on the first business operation, installs dependencies from the local wheel
bundle when needed, and runs the JSON CLI. Plain `doctor` bypasses runtime setup.
Do not call the system Python directly for business operations.

## Prerequisites and Bootstrap

- The user must install Python 3.10 or newer first. Python itself is not
  bundled and the plugin never attempts to install it. Bundled wheels cover
  Windows x64 CPython 3.10-3.14; do not promise compatibility outside this matrix.
- If bootstrap reports `python_missing` or `python_unsupported`, report the
  exact error and ask the user to install Python 3.10+, then retry.
- Runtime dependencies are installed only from `vendor/wheels` with
  `--no-index`; do not tell the user to install project dependencies from PyPI.
- The first setup can be inspected with:

  ```text
  scripts/plugin_bootstrap.cmd doctor
  ```

  `doctor` is read-only. Use `doctor --repair` only when the user explicitly
  permits dependency repair. Do not bypass a diagnosis-only request by running
  a business command that would bootstrap automatically.
- Existing dependencies and a current install marker skip pip installation.
  `venv_missing`, `dependencies_missing`, and `marker_stale` are diagnostic
  results, not permission to repair. A stale marker can coexist with working
  dependencies; explicit repair may run offline pip to satisfy the pinned
  requirements and update the marker, without forcing a reinstall.
- Report `wheel_unavailable` or `dependency_install_failed` with the returned
  error. Do not fall back to PyPI, download Python, or claim repair succeeded
  before checking the resulting report.

## Diagnosis

Start setup/troubleshooting with plain `doctor`. Inspect both top-level
`status` (runtime) and `wechat.status` (WeChat data); top-level `ready` alone
does not prove WeChat is configured. If `wechat.status` is `unavailable`,
full WeChat diagnostics could not run; do not infer that WeChat is closed.
`configuration_missing` is not evidence that the process is stopped either.

`doctor --repair` repairs only the private Python runtime. It does not configure
an account, discover database paths, scan for keys, or refresh chat data.
For missing paths/keys or an account switch, use `configure-history` with the
user's authorized path/discovery and keep WeChat signed in. A failed switch
must not be described as replacing the previously working account.

## CLI Commands

- `configure-history --db-dir <path>` configures a known database directory.
  Use `--discover` only after explicit permission for one local discovery.
- `doctor` reports runtime health and the existing WeChat path/process/key/
  database diagnosis.
- `refresh-history` forces a local source refresh.
- `find-conversations --query <text>` resolves ambiguous names. Add
  `--chat-kind`, `--member-count`, or `--min-member-count` when useful.
- `read-conversation --chat <value>` reads a known conversation.
  Use `--keyword`, `--start-time`, and `--end-time` to search within it.
- `read-recent` reads recent messages across chats only; never use it to locate
  a known person or group.
- `export-conversation --chat <value>` creates permanent files only after the
  user explicitly requests an export.
- `decode-image --chat <value> --message-id <id>` decodes one image identified
  by a prior records read.

CLI usage and command errors are JSON on stdout, retaining `status` and
`error`, with a non-zero exit code. Bootstrap failures are on stderr (the
missing-Python `.cmd` message can be plain text); inspect both streams and the
exit code. Do not interpret failure as an empty successful read.

Optional `--state-root <path>` is a global option before the subcommand:
`scripts/plugin_bootstrap.cmd --state-root "<path>" doctor`.
It selects WeChat state, not the plugin root or private dependency venv;
use the same state root for cursor continuation.

## Read Protocol

- Reads default to `--mode compact`.
- `--limit` is 1-500; conversation/recent reads default to 100, finding to 20.
- Direct compact rows are `time`, `role`, `text`; group rows are `time`,
  `sender`, `text`; recent rows are `time`, `chat`, `speaker`, `text`.
- Keep the time on every row and render non-text messages as short markers such
  as `[图片]`, `[语音]`, and `[文件]`.
- The first page declares `kind` and `columns`. Continuations contain rows or
  messages, `count`, `has_more`, and `next_cursor`.
- Use `--mode records` for evidence checks, image decoding, or structured
  fields. Request `--include-raw-content` only when the evidence task needs
  raw fields; it is valid only with records mode.

## Snapshots and Cursors

For a long fixed read:

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "..." --create-snapshot
scripts/plugin_bootstrap.cmd read-conversation --snapshot-id "..." --cursor "..."
```

Do not pass `--chat` with `--snapshot-id`, and do not change snapshot filters
or mode. The JSON field `snapshot_id` and the `next_cursor` value are opaque
machine values.
Never expose the absolute snapshot path.

Live cursors include the read scope, filter binding, source signature, and a
persisted read generation. A cursor can continue in a later CLI process while
the source and state root are unchanged. Keep the same chat, mode, raw-content
setting, and filters, and pass `next_cursor` unchanged until `has_more` is false.
Do not run `refresh-history` between pages. It becomes invalid after refresh,
source changes, account configuration, or a different scope/filter set; start
a new read in that case. Snapshot continuation instead uses the saved compact
rows and does not refresh the live source.

## Evidence Boundaries

Preserve unknown identities and distinguish message evidence from inference.
Report the exact chat and time range actually read. A zero-result search does
not prove that an offline event did not happen. Keep WeChat logged in during
first configuration so account-specific keys can be obtained.
