# 读懂微信

[英文版](README.en.md)

> 聊天记录太多，不想一条条翻？让 AI 帮你找、帮你看、帮你总结。

读懂微信（WeChat History Reader）是一个开源本地插件，让 AI Agent 直接读取、搜索和总结微信聊天记录，帮助 Agent 更好地理解你的工作和生活。

## 特色

### 一键获取微信聊天记录

只需拥有 Python 环境，就能让 AI Agent 快速读取聊天记录。

### 面向 AI 优化的结构化读取

提供紧凑、清楚的文本字段，让 AI 浏览、查找和总结更高效。

### 自由搜索记录

支持按微信名、微信 ID、微信备注进行查找，模糊搜索也能快速找到目标。

### 安全可靠，聊天内容不上网

不上传聊天内容，不修改微信原始聊天记录；读取和处理都在本机完成。

## 随时随地理解你的独特需求

- 帮我总结我和某人的最近讨论。
- 找出群里关于某件事的最终决定。
- 整理过去一个月聊天中提到的待办事项。
- 找出某个时间段内和某个主题有关的消息。

### 安装

从 GitHub Releases 下载最新版本的安装压缩包，然后在 ChatGPT 桌面端打开
“插件”，选择“添加插件”，导入下载的压缩包之后，再次在插件列表的“个人/Personal”类别搜索该插件并点击“+”来启用该插件

### 首次使用

由于平台限制，在与AI对话中，推荐使用英文名【WeChat History Reader】调用该插件（译为：微信聊天记录读取器），尤其是当AI无法意识到你想要调用该插件时。
同时，我们在设计上，原则上涉及到“读取微信聊天记录”相关字眼均可以触发该插件。
在第一次安装该插件之后，需要保持微信登录状态的情况下，让AI使用“请使用WeChat History Reader插件并进行初始化”。

### 运行环境要求

- 目前只支持 Windows 平台。
- 需要 Python 3.10 或更高版本。
- 目前适配微信 4.1.13。
- 需要 Windows 微信桌面端，首次配置时请保持登录状态。
- 如不理解相关要求，可以直接全文复制给AI，让其为之配置。

---
## 我们的技术优势

读懂微信 2.0 版本专为 AI 读取设计

### 核心规则

- 如果用户说出了明确的联系人、群聊或 `chat_id`，直接调用
  `read_conversation`。
- 只有在名称有歧义、存在多个匹配项，或用户明确要求查找聊天时，才调用
  `find_conversations`。
- `read_recent_across_chats` 用于读取多个聊天中的近期消息，不能用来查找
  已知的联系人或群聊。
- 默认读取模式为 `compact`，会移除 AI 分析不需要的单条消息元数据。
- 只有在核对证据、解码图片或检查原始字段时，才使用
  `mode="records"`。
- 当聊天内容很长，需要固定读取范围并逐页读取时，使用
  `create_snapshot=true`。

### 紧凑读取协议

第一页会声明 `kind` 和 `columns`。后续页面只返回投影后的行、数量、
`has_more` 和 `next_cursor`。

- 单聊：`time`、`role`（`me` 或 `other`）、`text`。
- 群聊：`time`、`sender`、`text`。
- 跨聊天读取近期消息：`time`、`chat`、`speaker`、`text`。
- 每一行都会保留时间。
- 非文本消息会转换为简短标记，例如 `[图片]`、`[语音]` 和 `[文件]`。
- `compact` 响应不会包含 `message_id`、`sender_id`、`type_id`、原始 XML、
  缓存诊断信息或数据库细节。

`records` 响应会保留用于证据核对的字段：`message_id`、`timestamp`、
`sender_name`、`type` 和 `text`。只有在 `mode="records"` 时，才能设置
`include_raw_content=true`。

### 长对话快照

使用下面的方式创建固定的机器快照：

```text
read_conversation(chat="联系人或群名", create_snapshot=true)
```

第一次响应会返回 `snapshot_id`，后续使用下面的方式继续读取：

```text
read_conversation(snapshot_id="...", cursor="...")
```

`chat` 和 `snapshot_id` 不能同时使用。快照创建后，不能修改聊天对象、
时间范围、关键词或读取模式。快照文件是单独存放在 `snapshots` 目录中的
紧凑 JSONL 数据。成功创建的快照不会自动删除，用户可以手动清理；创建失败
时会删除临时文件。

实时分页使用包含读取范围和数据源版本的不可读 cursor。刷新数据后，或将
cursor 用于其他查询时，cursor 会失效，从而避免分页结果无声地重叠或跳过。

### 配置与诊断

- `configure_history(db_dir="", discover=false)`：配置或切换本地微信数据库
  目录。只有在获得明确许可时，才能使用 `discover=true` 执行一次本地发现。
- `check_history()`：检查已保存的路径、微信进程、密钥和数据库访问状态，
  不会修改配置。
- `refresh_history()`：强制刷新一次本地数据。成功响应只包含 `status` 和
  `refreshed_at`。

首次配置时，请保持微信登录，以便获取与账号对应的密钥。切换账号或数据
目录时，需要重新配置新的目录。

### MCP 工具

- `configure_history(...)`
- `check_history()`
- `refresh_history()`
- `find_conversations(query, limit=20, chat_kind="any", ...)`
- `read_conversation(chat=..., snapshot_id=..., limit=100, cursor=..., mode="compact", ...)`
- `read_recent_across_chats(limit=100, cursor=..., mode="compact", ...)`
- `export_conversation(chat=..., ...)`
- `decode_conversation_image(chat=..., message_id=..., ...)`

导出文件是用户明确要求后生成的永久文件，存放在 `exports` 目录中。快照
文件是机器读取缓存，存放在独立的 `snapshots` 目录中。

### 运行时数据

运行时配置、密钥、解密后的数据库、解码后的图片、导出文件和快照都存放在
`%LOCALAPPDATA%\WeChatHistoryReader`。读懂微信不会上传本地聊天记录。
