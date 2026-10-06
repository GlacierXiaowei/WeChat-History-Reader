# 读懂微信

[English README](README.en.md)

读懂微信（WeChat History Reader）是一个本地 Skill，让 AI Agent 读取、
搜索、分页、导出和解码本机微信聊天记录。聊天内容不会上传，也不会修改
微信原始数据库。

## 2.1.1 的运行方式

2.1.1 公开插件只包含 Skill 和本地 JSON CLI，不加载 MCP。所有业务命令都
通过 `scripts/plugin_bootstrap.cmd` 启动：

```text
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd find-conversations --query "联系人"
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --limit 100
```

首次真正使用时，bootstrap 会：

1. 查找用户已经安装的 Python 3.10+；
2. 在 `%LOCALAPPDATA%\WeChatHistoryReader\runtime\venv` 创建私有 venv；
3. 只从插件内置 `vendor/wheels` 离线安装 `pycryptodome` 和 `zstandard`；
4. 写入安装标记，后续在源码、版本、wheel 或依赖未变化时跳过重复安装。

Python 解释器不会随插件打包，也不会由插件自动安装。缺少 Python 时只会
报告明确的安装提示。首次依赖安装禁止访问 PyPI。

## 安装前提

- Windows。
- 用户自行安装 Python 3.10 或更高版本。
- 发布包内置 Windows x64 CPython 3.10、3.11、3.12、3.13、3.14 可用的
  依赖 wheel。
- 首次配置或切换账号时保持微信桌面端登录，以便获取账号对应的密钥。

## 配置与诊断

```text
scripts/plugin_bootstrap.cmd configure-history --db-dir "D:\path\to\db_storage"
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd doctor --repair
scripts/plugin_bootstrap.cmd refresh-history
```

`doctor` 默认只读，检查 Python、私有 venv、依赖、安装标记以及微信路径、
进程、密钥和数据库状态。只有用户明确要求修复时才使用
`doctor --repair`；普通使用不会手动从 PyPI 安装项目依赖。

如果允许进行一次本地发现，可以使用：

```text
scripts/plugin_bootstrap.cmd configure-history --discover
```

## 读取协议

- `read-conversation --chat <值>` 读取已知联系人、群聊或 `chat_id`。
- 名称有歧义时先使用 `find-conversations --query <文本>`。
- `read-recent` 只用于跨聊天读取近期消息，不能用来查找已知聊天。
- 默认 `--mode compact`：单聊列为 `time, role, text`，群聊列为
  `time, sender, text`，跨聊天近期消息列为 `time, chat, speaker, text`。
- 证据核对、原始字段和图片解码使用 `--mode records`；
  `--include-raw-content` 只能配合 records。

长对话可创建机器快照并分页：

```text
scripts/plugin_bootstrap.cmd read-conversation --chat "联系人" --create-snapshot
scripts/plugin_bootstrap.cmd read-conversation --snapshot-id "<snapshot_id>" --cursor "<next_cursor>"
```

`snapshot_id` 和 `next_cursor` 都是不透明值。快照续读不能再传 `--chat`，
也不能修改过滤条件或模式。绝不向用户展示快照绝对路径。实时 cursor 可以
跨 CLI 进程继续使用；刷新数据、数据源变化或读取范围变化后会失效。

## 其他命令

```text
scripts/plugin_bootstrap.cmd export-conversation --chat "联系人"
scripts/plugin_bootstrap.cmd decode-image --chat "联系人" --message-id "<message_id>"
```

导出只在用户明确要求时执行，文件保存在运行时 `exports` 目录。配置、密钥、
解密缓存、快照和解码图片默认保存在 `%LOCALAPPDATA%\WeChatHistoryReader`。

## 版本边界

2.1.1 不包含 MCP。2.0 MCP 接口不属于当前正式目录，也不会复制到 2.1.1
包中。
