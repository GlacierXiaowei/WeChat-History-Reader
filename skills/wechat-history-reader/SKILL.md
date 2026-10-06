---
name: wechat-history-reader
description: Read, configure, diagnose, search, and export local WeChat history through the bundled offline CLI.
---

# WeChat History Reader 2.1

Use the bundled `scripts/plugin_bootstrap.cmd` launcher for every operation.
The launcher finds the user's Python installation, creates the private runtime
on first real use, installs missing dependencies from the plugin's local wheel
bundle, and then runs the JSON CLI. Do not call the system Python directly for
business operations.

## Prerequisites and Bootstrap

- The user must install Python 3.10 or newer first. Python itself is not
  bundled and the plugin never attempts to install it.
- If bootstrap reports `python_missing` or `python_unsupported`, report the
  exact error and ask the user to install Python 3.10+, then retry.
- Runtime dependencies are installed only from `vendor/wheels` with
  `--no-index`; do not tell the user to install project dependencies from PyPI.
- The first setup can be inspected with:

  ```text
  scripts/plugin_bootstrap.cmd doctor
  ```

  `doctor` is read-only. Use `doctor --repair` only when the user explicitly
  permits dependency repair.

## CLI Commands

- `configure-history --db-dir <path>` configures a known database directory.
  Use `--discover` only after explicit permission for one local discovery.
- `doctor` reports runtime health and the existing WeChat path/process/key/
  database diagnosis.
- `refresh-history` forces a local source refresh.
- `find-conversations --query <text>` resolves ambiguous names. Add
  `--chat-kind`, `--member-count`, or `--min-member-count` when useful.
- `read-conversation --chat <value>` reads a known conversation.
- `read-recent` reads recent messages across chats only; never use it to locate
  a known person or group.
- `export-conversation --chat <value>` creates permanent files only after the
  user explicitly requests an export.
- `decode-image --chat <value> --message-id <id>` decodes one image identified
  by a prior records read.

Every command writes exactly one JSON object to stdout. Runtime and usage
errors are written to stderr by the launcher; CLI command errors retain the
existing `status` and `error` fields and use a non-zero exit code.

## Read Protocol

- Reads default to `--mode compact`.
- Direct compact rows are `time`, `role`, `text`; group rows are `time`,
  `sender`, `text`; recent rows are `time`, `chat`, `speaker`, `text`.
- Keep the time on every row and render non-text messages as short markers such
  as `[图片]`, `[语音]`, and `[文件]`.
- The first page declares `kind` and `columns`. Continuations contain rows or
  messages, `count`, `has_more`, and `next_cursor`.
- Use `--mode records` for evidence checks, image decoding, or structured
  fields. `--include-raw-content` is valid only with records mode.

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
the source is unchanged. It becomes invalid after `refresh-history`, source
replacement, or a different scope/filter set; start a new read in that case.

## Evidence Boundaries

Preserve unknown identities and distinguish message evidence from inference.
Report the exact chat and time range actually read. A zero-result search does
not prove that an offline event did not happen. Keep WeChat logged in during
first configuration so account-specific keys can be obtained.
