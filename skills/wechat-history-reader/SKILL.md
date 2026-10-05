---
name: wechat-history-reader
description: Read, configure, diagnose, search, and export local WeChat history through the 2.0 MCP tools.
---

# WeChat History Reader 2.0

Use only the plugin MCP tools. Do not use shell commands, folder scans, or
another tool as a substitute for local WeChat history.

## Setup

- Use `configure_history` for first configuration or switching the WeChat
  database directory. Pass a known `db_dir`; use `discover=true` only after
  explicit permission for one local discovery.
- Use `check_history` for environment questions or failed reads. It checks the
  saved path, WeChat process, keys, and database access without changing keys.
- Use `refresh_history` only when a fresh source check is needed. A successful
  refresh response contains only `status` and `refreshed_at`.
- Keep desktop WeChat logged in during first configuration so account-specific
  keys can be obtained. A different account or data directory needs a new
  configuration.

## Choosing A Read Tool

- Known person, group, or `chat_id`: call `read_conversation` directly.
- Ambiguous, duplicated, or explicitly requested lookup: call
  `find_conversations` once, then use the selected `chat_id` with
  `read_conversation`.
- Never repeatedly search name fragments.
- Never call `read_recent_across_chats` to locate a known conversation.
- `read_recent_across_chats` is only for recent messages across multiple chats.

## Read Protocol

- `read_conversation` defaults to `mode="compact"`.
- Direct compact rows are `time`, `role`, `text`, where `role` is `me` or
  `other`.
- Group compact rows are `time`, `sender`, `text`.
- Cross-chat recent compact rows are `time`, `chat`, `speaker`, `text`.
- Keep the time on every row.
- Render non-text messages as short markers such as `[图片]`, `[语音]`, and
  `[文件]`.
- The first page declares `kind` and `columns`. Continuations return only rows
  or messages, count, `has_more`, and `next_cursor`.
- Do not ask for or generate a human-readable transcript. Compact rows are
  specifically for AI context reduction.

Use `mode="records"` only for evidence checks, image decoding, or raw field
inspection. Its standard fields are `message_id`, `timestamp`, `sender_name`,
`type`, and `text`. `include_raw_content=true` is valid only in records mode.

## Long Reads

For a very long fixed conversation, call:

```text
read_conversation(chat="...", create_snapshot=true)
```

Then continue only with:

```text
read_conversation(snapshot_id="...", cursor="...")
```

Do not pass `chat` together with `snapshot_id`. Do not change the snapshot's
filters, mode, or target. A snapshot is a compact machine file, not a
human-facing transcript, and its absolute path must never be exposed.

Live cursors are tied to their read scope and source generation. Do not reuse a
cursor after `refresh_history`, for another chat, or for another filter set.
`has_more=false` means the current read range is complete.

## Evidence Boundaries

Preserve unknown identities. Do not infer that a zero result proves an offline
event did not happen. Report the exact chat and time range that were actually
read, and distinguish message evidence from inference.
