# 读懂微信

[English README](README.en.md)

读懂微信（WeChat History Reader）是一个本地 Skill，让 AI Agent 读取、
搜索、分页、导出和解码本机微信聊天记录。聊天内容不会上传，也不会修改
微信原始数据库。

## 2.1.1 的运行方式

2.1.1 公开插件只包含 Skill 和本地 JSON CLI，不加载 MCP。所有业务命令都
通过 `scripts/plugin_bootstrap.cmd` 启动。以下示例在插件根目录执行；
Agent 应定位当前插件的实际安装目录，不使用其他项目目录或旧版 MCP 工具。
在其他目录的 PowerShell 中，用 `& "插件绝对路径\scripts\plugin_bootstrap.cmd"`
调用启动器：

```text
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd find-conversations --query "联系人"
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --limit 100
```

首次执行业务命令（例如配置、查找或读取）时，bootstrap 会：

1. 查找用户已经安装的 Python 3.10+；
2. 在 `%LOCALAPPDATA%\WeChatHistoryReader\runtime\venv` 创建私有 venv；
3. 只从插件内置 `vendor/wheels` 离线安装 `pycryptodome` 和 `zstandard`；
4. 写入安装标记，后续在源码、版本、wheel 或依赖未变化时跳过重复安装。

Python 解释器不会随插件打包，也不会由插件自动安装。缺少 Python 时只会
报告明确的安装提示。依赖安装始终禁止访问 PyPI。普通 `doctor` 不触发
上述创建和安装流程。

## 安装前提

- Windows x64。
- 用户自行安装 Python，并确保 `py` 或 `python` 命令可用。
- 发布包内置 Windows x64 CPython 3.10、3.11、3.12、3.13、3.14 可用的
  依赖 wheel。
- 建议使用上述 CPython 3.10-3.14 版本；其他平台、架构或版本不保证有
  兼容 wheel，安装失败时不会退回联网安装。
- 首次配置或切换账号时保持微信桌面端登录，以便获取账号对应的密钥。

## 配置与诊断

```text
scripts/plugin_bootstrap.cmd configure-history --db-dir "D:\path\to\db_storage"
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd doctor --repair
scripts/plugin_bootstrap.cmd refresh-history
```

`doctor` 默认只读，检查 Python、私有 venv、依赖、安装标记以及微信路径、
进程、密钥和数据库状态。即使 venv、依赖缺失或标记过期，也只报告，
不会安装；已安装依赖时自动检查版本和能否导入。

`doctor --repair` 只修复私有 Python 环境，不配置账号、不扫描密钥、不刷新
聊天数据。依赖和 marker 均有效时跳过安装；`marker_stale` 不代表依赖
一定损坏，修复可能执行离线 pip 并更新 marker，但不会强制重装。
缺少可用 wheel 或安装失败时保留明确错误，不从 PyPI 补装。

诊断结果的顶层 `status` 表示运行环境，`wechat.status` 表示微信数据状态，
两者需要分别检查。顶层 `ready` 不代表微信已配置；`wechat.status` 为
`unavailable` 表示微信诊断暂不能执行，不等于微信未运行。路径或密钥问题
应通过获授权的 `configure-history` 处理，而不是 `doctor --repair`。

如果允许进行一次本地发现，可以使用：

```text
scripts/plugin_bootstrap.cmd configure-history --discover
```

可选全局参数 `--state-root` 必须写在子命令前，例如：

```text
scripts/plugin_bootstrap.cmd --state-root "D:\wechat-reader-state" doctor
```

它仅选择微信配置、密钥、缓存和快照等状态目录，不改变插件位置或依赖 venv。
分页续读必须使用同一个状态目录。

## 读取协议

- `read-conversation --chat <值>` 读取已知联系人、群聊或 `chat_id`。
- 名称有歧义时先使用 `find-conversations --query <文本>`。
- `read-recent` 只用于跨聊天读取近期消息，不能用来查找已知聊天。
- 默认 `--mode compact`：单聊列为 `time, role, text`，群聊列为
  `time, sender, text`，跨聊天近期消息列为 `time, chat, speaker, text`。
- `--limit` 范围为 1-500；读取默认 100，查找会话默认 20。
- 证据核对、原始字段和图片解码使用 `--mode records`；
  `--include-raw-content` 只能配合 records。

关键词和时间范围搜索直接使用读取命令，不需要旧版 MCP 搜索接口：

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --keyword "关键词" --start-time "2026-10-01" --end-time "2026-10-08"
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --mode records --limit 20
```

长对话可创建机器快照并分页：

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --create-snapshot
scripts/plugin_bootstrap.cmd read-conversation --snapshot-id "<snapshot_id>" --cursor "<next_cursor>"
```

`snapshot_id` 和 `next_cursor` 都是不透明值。快照续读不能再传 `--chat`，
也不能修改过滤条件或模式。绝不向用户展示快照绝对路径。实时 cursor 可以
跨 CLI 进程继续使用；刷新数据、数据源变化或读取范围变化后会失效。
续页使用相同聊天、模式、原始字段开关和过滤条件，原样传入 `next_cursor`，
不要在两页之间执行 `refresh-history`。配置或切换账号也会使实时 cursor
失效。机器快照续页读取已保存的 compact 行，不重新刷新实时数据。

## 其他命令

```text
scripts/plugin_bootstrap.cmd export-conversation --chat "联系人"
scripts/plugin_bootstrap.cmd decode-image --chat "联系人" --message-id "<message_id>"
```

导出只在用户明确要求时执行，文件保存在运行时 `exports` 目录。配置、密钥、
解密缓存、快照和解码图片默认保存在 `%LOCALAPPDATA%\WeChatHistoryReader`。
导出可使用 `--output-dir` 指定目录，并支持 `--start-time`、`--end-time`。
图片的 `message_id` 必须来自 records 读取结果，不应猜测。

CLI 成功和命令/参数错误均在 stdout 输出一个 JSON 对象；错误保留 `status`
和 `error`，并返回非零退出码。bootstrap 失败写 stderr，缺少 Python 的
启动器提示可能是纯文本。Agent 应检查输出和退出码，不把错误当成零条消息。

## 版本边界

2.1.1 不包含 MCP。2.0 MCP 接口不属于当前正式目录，也不会复制到 2.1.1
包中。
