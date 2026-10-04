# Get Wechat History 2.0

Get Wechat History is a read-only MCP plugin for reading local Windows WeChat
history. Version 2.0 is designed for AI retrieval: responses are compact
structured rows, not human-facing transcripts.

## Core Rules

- If the user names a known person, group, or `chat_id`, call
  `read_conversation` directly.
- Call `find_conversations` only for an ambiguous name, duplicate matches, or
  an explicit request to find a conversation.
- `read_recent_across_chats` means recent messages across chats. It is never a
  contact lookup tool.
- The default read mode is `compact`. It removes per-message metadata that is
  not needed for AI analysis.
- Use `mode="records"` only for evidence checks, image decoding, or raw payload
  inspection.
- Use `create_snapshot=true` when a very long conversation should be fixed and
  read page by page without rescanning the database.

## Compact Protocol

The first page declares `kind` and `columns`. Later pages return only the
projected rows, count, `has_more`, and `next_cursor`.

- Direct chat: `time`, `role` (`me` or `other`), `text`.
- Group chat: `time`, `sender`, `text`.
- Cross-chat recent: `time`, `chat`, `speaker`, `text`.
- Every row keeps its time.
- Non-text messages become short markers such as `[图片]`, `[语音]`, and
  `[文件]`.
- Compact responses do not include `message_id`, `sender_id`, `type_id`, raw
  XML, cache diagnostics, or database details.

`records` responses retain the evidence fields
`message_id`, `timestamp`, `sender_name`, `type`, and `text`. Set
`include_raw_content=true` only together with `mode="records"`.

## Long Conversation Snapshots

Create a fixed machine snapshot with:

```text
read_conversation(chat="联系人或群名", create_snapshot=true)
```

The first response includes `snapshot_id`. Continue with:

```text
read_conversation(snapshot_id="...", cursor="...")
```

`chat` and `snapshot_id` are mutually exclusive. A snapshot cannot change its
chat, time range, keyword, or mode. Snapshot files are compact JSONL rows in a
separate `snapshots` directory. Successful snapshots are not deleted
automatically; users can clean them up manually. Temporary files are removed
when snapshot creation fails.

Live pagination uses opaque cursors containing the read scope and source
generation. A cursor becomes invalid after a refresh or when used with another
query, so pages cannot silently overlap or skip after the source changes.

## Requirements

- Windows desktop WeChat, logged in during first configuration.
- Python 3.10 or newer.
- Windows WeChat 4.1.13 modern key recovery, with the legacy scanner retained
  as a fallback.

## Installation

Place the complete repository in:

`%USERPROFILE%\.codex\plugins\get-wechat-history`

The plugin root must contain `.codex-plugin`, `.mcp.json`, `skills`,
`get_wechat_history`, and `scripts`. Enable it from Codex plugin management;
the launcher creates or reuses its private runtime environment.

## Configuration And Diagnostics

- `configure_history(db_dir="", discover=false)`: configure or switch the
  local WeChat database directory. Use `discover=true` only with explicit
  permission for one local discovery.
- `check_history()`: inspect the saved path, WeChat process, keys, and database
  access without changing configuration.
- `refresh_history()`: force one local refresh. A successful response contains
  only `status` and `refreshed_at`.

Keep WeChat logged in during the first configuration so account-specific keys
can be obtained. Switching accounts or data directories requires configuring
the new directory.

## MCP Tools

- `configure_history(...)`
- `check_history()`
- `refresh_history()`
- `find_conversations(query, limit=20, chat_kind="any", ...)`
- `read_conversation(chat=..., snapshot_id=..., limit=100, cursor=..., mode="compact", ...)`
- `read_recent_across_chats(limit=100, cursor=..., mode="compact", ...)`
- `export_conversation(chat=..., ...)`
- `decode_conversation_image(chat=..., message_id=..., ...)`

Exports are permanent user-requested artifacts under `exports`. Snapshot files
are machine-read caches under `snapshots`; they are intentionally separate.

## Runtime Data

Runtime configuration, keys, decrypted databases, decoded images, exports, and
snapshots are stored under `%LOCALAPPDATA%\GetWechatHistory`. The plugin does
not upload local history.
