# WeChat History Reader

WeChat History Reader is a local Skill for reading, searching, paging,
exporting, and decoding a user's WeChat history. Chat content stays on the
machine and the original WeChat databases are never modified.

## How 2.1.1 Runs

The public 2.1.1 package contains a Skill and a local JSON CLI. It does not
load MCP. Every business operation goes through the bundled launcher.
Examples below run from the plugin root. Agents must locate the current
plugin installation, not another project's directory or old MCP tools.
From another PowerShell directory, invoke the quoted absolute launcher path
with `&`:

```text
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd find-conversations --query "Alice"
scripts/plugin_bootstrap.cmd read-conversation --chat "Alice" --limit 100
```

On the first business command (configuration, finding, or reading), bootstrap
finds user-installed Python 3.10+, creates a
private environment under
`%LOCALAPPDATA%\WeChatHistoryReader\runtime\venv`, installs
`pycryptodome` and `zstandard` only from the bundled offline wheels, and writes
an idempotent install marker. Python itself is not bundled or installed by the
plugin. Missing Python produces an actionable message, and first-use
dependency installation never contacts PyPI. Plain `doctor` skips environment
creation and installation.

## Requirements

- Windows x64.
- User-installed Python with the `py` launcher or `python` command available.
- Release packages include compatible Windows x64 wheels for CPython 3.10,
  3.11, 3.12, 3.13, and 3.14.
- Use CPython 3.10-3.14 for the bundled wheel matrix. Other platforms,
  architectures, or versions are not guaranteed; failed installation never
  falls back to a network index.
- Keep the desktop WeChat client logged in during initial configuration so
  account-specific keys can be obtained.

## Configure and Diagnose

```text
scripts/plugin_bootstrap.cmd configure-history --db-dir "D:\path\to\db_storage"
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd doctor --repair
scripts/plugin_bootstrap.cmd refresh-history
```

`doctor` is read-only and reports Python, the private venv, dependencies,
install marker, and the existing WeChat path/process/key/database health.
Missing environments/dependencies or stale markers are reported without
installation. Existing dependencies are checked for version and importability.

`doctor --repair` repairs only the private Python runtime, not accounts, keys,
or chat data. Current dependencies and marker skip installation. `marker_stale`
can occur even with working dependencies; repair may run offline pip and update
the marker without forcing reinstallation. Missing wheels or installation
failures are reported, never replaced by PyPI installation.

Inspect top-level `status` (runtime) and `wechat.status` (WeChat data)
separately. Runtime `ready` does not mean WeChat is configured; WeChat
`unavailable` means full diagnosis could not run, not that the process is
stopped. Use authorized `configure-history` for path/key issues.

Use `configure-history --discover` only after explicit permission for one local
discovery.

Optional global `--state-root` goes before the subcommand:

```text
scripts/plugin_bootstrap.cmd --state-root "D:\wechat-reader-state" doctor
```

It selects WeChat configuration, keys, caches, and snapshots, not the plugin
root or private dependency venv. Cursor continuation needs the same state root.

## Read Protocol

- Use `read-conversation --chat <value>` for a known person, group, or `chat_id`.
- Use `find-conversations --query <text>` only when the target is ambiguous.
- Use `read-recent` only for recent messages across chats, never to locate a
  known conversation.
- Default `--mode compact` keeps direct rows as `time, role, text`, group rows
  as `time, sender, text`, and recent rows as `time, chat, speaker, text`.
- `--limit` is 1-500; reads default to 100, finding to 20.
- Use `--mode records` for evidence checks, structured fields, raw content, or
  image decoding. `--include-raw-content` is records-only.

Search using read filters, not a legacy MCP search interface:

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "Alice" --keyword "keyword" --start-time "2026-10-01" --end-time "2026-10-08"
scripts/plugin_bootstrap.cmd read-conversation --chat "Alice" --mode records --limit 20
```

For a long fixed read:

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "Alice" --create-snapshot
scripts/plugin_bootstrap.cmd read-conversation --snapshot-id "<snapshot_id>" --cursor "<next_cursor>"
```

`snapshot_id` and `next_cursor` are opaque values. Snapshot continuation must
not include `--chat` or change filters/mode, and the absolute snapshot path must
never be shown. Live cursors remain valid across CLI processes while the source
is unchanged; refreshes, source changes, and different read scopes invalidate
them.
Keep the same chat, mode, raw-content setting, and filters; pass `next_cursor`
unchanged. Do not run `refresh-history` between pages. Account configuration
also invalidates live cursors. Snapshot continuation reads saved compact rows
without refreshing the live source.

## Other Commands

```text
scripts/plugin_bootstrap.cmd export-conversation --chat "Alice"
scripts/plugin_bootstrap.cmd decode-image --chat "Alice" --message-id "<message_id>"
```

Exports are created only on explicit request. Runtime configuration, keys,
decrypted caches, snapshots, exports, and decoded images live under
`%LOCALAPPDATA%\WeChatHistoryReader`.
Exports support `--output-dir`, `--start-time`, and `--end-time`.
Image `message_id` must come from a records read, not a guessed identifier.

CLI results and usage/command errors are one JSON object on stdout. Errors
retain `status` and `error` and use non-zero exit codes. Bootstrap failures go
to stderr; the missing-Python launcher message can be plain text. Inspect both
output and exit code, and never treat an error as a successful empty read.

## Version Boundary

2.1.1 contains no MCP interface. The old MCP manifests and server entrypoint
are intentionally absent from the formal source tree.
