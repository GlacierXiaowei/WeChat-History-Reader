# 读懂微信
# WeChat History Reader
[English](README.en.md)

读懂微信（WeChat History Reader）让 AI Agent 能够轻易读取、搜索和总结微信本地聊天记录，使得模型能够充分理解你的工作和生活。

> 聊天记录太多，不想一条条翻？让 AI 帮你找、帮你看、帮你总结。

---

### 📥 一键获取微信聊天记录

只需拥有 Python 环境，就能让 AI Agent 快速读取聊天记录。

### 🧠 面向 AI 优化的结构化读取

提供紧凑、清楚的文本字段，让 AI 浏览、查找和总结更高效。

### 🔎 自由搜索记录

支持按微信名、微信 ID、微信备注以及聊天记录进行查找，即使是模糊搜索也能快速找到目标。

### 🔒 安全可靠

该插件有skill构成，插件本省完全不具备上传数据能力，相关处理均在本地完成；插件基于本地的缓存副本文件，不会修改微信的任何原始数据。

### 💬 随时随地理解你的独特需求

- 帮我总结我和某人的最近讨论。
- 找出群里关于某件事的最终决定。
- 整理过去一个月聊天中提到的待办事项。
- 找出某个时间段内和某个主题有关的消息。

---

### 安装

从 GitHub Releases 下载最新版本的安装压缩包，然后在 ChatGPT 桌面端打开
“插件”，选择“添加插件”，导入下载的压缩包之后，再次在插件列表的“个人/Personal”类别搜索该插件并点击“+”来启用该插件

### 首次使用

由于平台限制，在与AI对话中，推荐使用英文名【WeChat History Reader】调用该插件（译为：微信聊天记录读取器），尤其是当AI无法意识到你想要调用该插件时。
同时，我们在设计上，原则上涉及到“读取微信聊天记录”相关关键词均可以触发该插件。
第一次安装该插件时候，需要先进行初始化：保持微信登录状态的情况下，让AI使用“请使用WeChat History Reader插件并进行初始化”。

### 运行环境要求

- 适配 Windows11 (x64) 平台。
- 电脑必须具备 Python 3.10 或更高版本。
- 需要 Windows 微信桌面端，且首次配置时请保持微信已打开并处于正常已登录状态。
  >如果不理解相关要求，可以直接全文复制给AI，让其为之配置。

---

## 适用于开发者的相关信息

### 开发环境与依赖

不限定编辑器或 IDE；涉及微信数据库读取、初始化和图片解码的联调，建议在 Windows 11 (x64) 上进行。首次初始化或切换账号时，请保持微信桌面端登录。

项目要求 Python 3.10 或更高版本。发行包附带的离线依赖适用于 Windows x64、CPython 3.10 至 3.14，由本地启动器安装到插件的私有 Python 环境中。

| 依赖 | 源码版本范围 | 发行包固定版本 | 用途 |
|---|---|---|---|
| `pycryptodome` | `>=3.23,<4` | `3.24.0` | 微信数据库与图片的加解密 |
| `zstandard` | `>=0.22,<1` | `0.25.0` | 消息内容解压 |

构建依赖为 `setuptools>=68`、`wheel>=0.40`。SQLite、JSON 等处理使用 Python 标准库，不需要额外部署数据库服务或 MCP 服务器。依赖范围见 [pyproject.toml](pyproject.toml)，发行包版本见 [requirements-runtime.txt](requirements-runtime.txt)。

### 实现结构

技能指令由 [SKILL.md](skills/wechat-history-reader/SKILL.md) 提供，业务通过本地脚本执行：

```text
技能指令 → 本地启动器 → JSON CLI → 业务服务 → 本地微信数据库
```

- `scripts/`：启动器、离线依赖准备和插件打包脚本。
- `wechat_history_reader/cli.py`：命令入口与参数定义。
- `wechat_history_reader/service.py`：会话定位、读取、快照和导出等业务逻辑。
- `wechat_history_reader/local_backend.py`：本地数据读取接口。
- `wechat_history_reader/runtime_state.py`：账号配置与本地状态管理。

### 工具与 API

目前提供 8 个本地 CLI 工具，不是 HTTP API。参数定义见 [cli.py](wechat_history_reader/cli.py)，业务行为见 [service.py](wechat_history_reader/service.py)。

| 命令 | 用途 | 主要参数 |
|---|---|---|
| `doctor` | 检查运行环境与配置 | 默认只读；`--repair` 仅修复私有运行环境，不重新提取密钥。 |
| `configure-history` | 初始化或切换账号 | 使用 `--db-dir` 指定数据库目录，或用 `--discover` 自动查找；需要明确授权，并保持微信登录。 |
| `refresh-history` | 强制刷新本地聊天数据 | 无专用参数。 |
| `find-conversations` | 查找会话 | 必填 `--query`；`--limit` 默认 20；`--chat-kind` 默认 `any`，也可选 `direct`、`group`；支持群人数线索。 |
| `read-conversation` | 读取指定会话或快照 | 使用 `--chat` 或 `--snapshot-id`，二者不能同时提供；支持通用读取参数、群人数线索及 `--create-snapshot`。 |
| `read-recent` | 跨会话读取近期消息 | 支持通用读取参数。 |
| `export-conversation` | 导出会话 | 必填 `--chat`；可指定 `--start-time`、`--end-time`、`--output-dir`、刷新选项和群人数线索。 |
| `decode-image` | 解码聊天中的图片 | 必填 `--chat`、`--message-id`，消息标识从 `records` 读取结果取得；可指定 `--output-dir` 和群人数线索。 |

#### 通用读取参数

以下参数适用于 `read-conversation` 和 `read-recent`：

| 参数 | 说明 |
|---|---|
| `--limit` | 每页数量，范围为 1 至 500，默认 100。 |
| `--cursor` | 分页续读值，使用上次返回的 `next_cursor`，不要自行修改。 |
| `--keyword` | 按消息内容关键词筛选。 |
| `--start-time`、`--end-time` | 起止时间，支持日期、日期时间或 ISO 8601；结束时间只提供日期时，覆盖当天结束。 |
| `--mode` | 默认 `compact`，返回紧凑字段；也可选 `records`，返回结构化消息记录。 |
| `--include-raw-content` | 包含原始载荷字段，仅能与 `records` 模式一起使用。 |

#### 其他参数与分页

- `--chat` 用于指定会话，建议使用 `find-conversations` 返回的会话标识。
- `--member-count`、`--min-member-count` 是群人数线索，用于候选排序，不是严格过滤；适用于查找、单会话读取、导出和图片解码。
- `--refresh` / `--no-refresh` 控制导出或创建快照前是否刷新，默认刷新；不控制普通实时读取。
- `--create-snapshot` 仅用于首次读取，不能同时传入游标；快照只支持 `compact` 模式。之后用 `--snapshot-id` 续读，不能重新指定会话或修改筛选条件。
- 全局参数 `--state-root` 放在子命令之前，用于更改数据状态目录，不改变插件安装位置或私有 Python 环境。默认数据目录为 `%LOCALAPPDATA%\WeChatHistoryReader`。
- 实时分页续读需要保持会话、模式和筛选条件一致；刷新、切换账号或数据源变化后，应重新开始读取。

#### 调用与返回

在插件根目录下调用本地启动器，例如：

```powershell
.\scripts\plugin_bootstrap.cmd find-conversations --query "项目群" --chat-kind group
```

业务 CLI 向标准输出返回一个 JSON 对象。读取结果通过 `count`、`has_more`、`next_cursor` 描述当前页；`compact` 模式使用 `rows` 和字段说明 `columns`，`records` 模式使用 `messages`。紧凑模式的字段说明可能仅在首屏返回，续读时需要保留。

退出码为 `0` 时表示成功，`1` 表示业务或运行失败，`2` 表示参数错误。启动器失败时，错误信息可能输出到标准错误；调用方应同时检查退出码和错误输出。

### 如何贡献

欢迎通过 GitHub Issues 报告问题、讨论功能，通过 Pull Request 提交改进。

- 问题报告请附微信版本、Python 版本、复现步骤、预期结果与脱敏错误信息。
- 代码改动请说明影响范围和验证方式；涉及解析、解密或分页行为时，请提供可复现的测试样例。
- 请使用合成或脱敏数据，不要提交真实聊天记录、微信数据库、密钥、导出文件或个人配置。
