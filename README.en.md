# WeChat History Reader

WeChat History Reader is a local Skill for reading, searching, paging,
exporting, and decoding a user's WeChat history. Chat content stays on the
machine and the original WeChat databases are never modified.

## How 2.1.1 Runs

The public 2.1.1 package contains a Skill and a local JSON CLI. It does not
load MCP. Every business operation goes through the bundled launcher:

```text
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd find-conversations --query "Alice"
scripts/plugin_bootstrap.cmd read-conversation --chat "Alice" --limit 100
```

On first real use, bootstrap finds user-installed Python 3.10+, creates a
private environment under
`%LOCALAPPDATA%\WeChatHistoryReader\runtime\venv`, installs
`pycryptodome` and `zstandard` only from the bundled offline wheels, and writes
an idempotent install marker. Python itself is not bundled or installed by the
plugin. Missing Python produces an actionable message, and first-use
dependency installation never contacts PyPI.

## Requirements

- Windows.
- User-installed Python 3.10 or newer.
- Release packages include compatible Windows x64 wheels for CPython 3.10,
  3.11, 3.12, 3.13, and 3.14.
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
`doctor --repair` is the explicit repair path. Normal use must not install
project dependencies from PyPI.

Use `configure-history --discover` only after explicit permission for one local
discovery.

## Read Protocol

- Use `read-conversation --chat <value>` for a known person, group, or `chat_id`.
- Use `find-conversations --query <text>` only when the target is ambiguous.
- Use `read-recent` only for recent messages across chats, never to locate a
  known conversation.
- Default `--mode compact` keeps direct rows as `time, role, text`, group rows
  as `time, sender, text`, and recent rows as `time, chat, speaker, text`.
- Use `--mode records` for evidence checks, structured fields, raw content, or
  image decoding. `--include-raw-content` is records-only.

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

## Other Commands

```text
scripts/plugin_bootstrap.cmd export-conversation --chat "Alice"
scripts/plugin_bootstrap.cmd decode-image --chat "Alice" --message-id "<message_id>"
```

Exports are created only on explicit request. Runtime configuration, keys,
decrypted caches, snapshots, exports, and decoded images live under
`%LOCALAPPDATA%\WeChatHistoryReader`.

## Version Boundary

2.1.1 contains no MCP interface. The old MCP manifests and server entrypoint
are intentionally absent from the formal source tree.
