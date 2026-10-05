# WeChat History Reader

[Chinese version](README.md)

> Too many chat messages to read one by one? Let AI find them, read them, and
> summarize them for you.

WeChat History Reader is an open-source local plugin that lets AI agents
directly read, search, and summarize WeChat chat history, helping them better
understand your work and daily life.

## Features

### One-click access to WeChat chat history

You only need a Python environment to let an AI agent quickly read your chat
history.

### Structured reading optimized for AI

It provides compact, clear text fields so AI can browse, search, and summarize
more efficiently.

### Flexible search

Search by WeChat name, WeChat ID, or remark name. Fuzzy search is supported.

### Reliable and local, with no chat content sent online

Chat content is not uploaded, and the original WeChat chat records are not
modified. Reading and processing happen on the local machine.

## Understand your needs wherever you are

- Summarize my recent discussion with someone.
- Find the final decision about a topic in a group chat.
- Organize action items mentioned in chats during the past month.
- Find messages related to a topic within a specific time range.

### Requirements

- Windows only.
- Python 3.10 or newer.
- Currently adapted for WeChat 4.1.13.
- Windows desktop WeChat is required; keep it logged in during first
  configuration.

### Installation

Download the latest release package from GitHub Releases. Then open
“Plugins” in the ChatGPT desktop app, choose “Add plugin”, and import the
downloaded ZIP archive.

### First Use

Due to platform limitations, we recommend invoking the plugin by its English
name, `WeChat History Reader`, in your conversation with AI. This is especially
helpful when the AI does not recognize that you want to use this plugin.
In principle, phrases related to “reading WeChat chat history” can also trigger
the plugin.

After installing the plugin for the first time, keep WeChat logged in and ask
the AI: “Please use the WeChat History Reader plugin and initialize it.”

### Runtime Requirements

- Windows only.
- Python 3.10 or newer.
- Currently adapted for WeChat 4.1.13.
- Windows desktop WeChat is required; keep it logged in during first
  configuration.
- If these requirements are unclear, copy this section to the AI and ask it to
  configure the plugin.

---
## Technical Advantages

Version 2.0 of WeChat History Reader is designed for AI retrieval: it returns
compact structured data instead of full human-facing chat transcripts.

### Core Rules

- If the user names a known person, group, or `chat_id`, call
  `read_conversation` directly.
- Call `find_conversations` only for an ambiguous name, duplicate matches, or
  an explicit request to find a conversation.
- `read_recent_across_chats` is for recent messages across multiple chats. It
  must not be used to locate a known contact or group.
- The default read mode is `compact`. It removes per-message metadata that is
  not needed for AI analysis.
- Use `mode="records"` only for evidence checks, image decoding, or raw field
  inspection.
- Use `create_snapshot=true` when a very long conversation should be fixed and
  read page by page without rescanning the database.

### Compact Read Protocol

The first page declares `kind` and `columns`. Later pages return only the
projected rows, count, `has_more`, and `next_cursor`.

- Direct chat: `time`, `role` (`me` or `other`), `text`.
- Group chat: `time`, `sender`, `text`.
- Recent messages across chats: `time`, `chat`, `speaker`, `text`.
- Every row keeps its time.
- Non-text messages become short markers such as `[图片]`, `[语音]`, and
  `[文件]`.
- Compact responses do not include `message_id`, `sender_id`, `type_id`, raw
  XML, cache diagnostics, or database details.

`records` responses retain the evidence fields
`message_id`, `timestamp`, `sender_name`, `type`, and `text`. Set
`include_raw_content=true` only together with `mode="records"`.

### Long Conversation Snapshots

Create a fixed machine snapshot with:

```text
read_conversation(chat="contact or group name", create_snapshot=true)
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

### Configuration and Diagnostics

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

### MCP Tools

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

### Runtime Data

Runtime configuration, keys, decrypted databases, decoded images, exports, and
snapshots are stored under `%LOCALAPPDATA%\WeChatHistoryReader`. WeChat History
Reader does not upload local chat history.
