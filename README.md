# Anki OpenAI Secure Tunnel

独立的 Anki 配套插件：在 Anki 的「工具 → OpenAI 隧道连接」中，配置、启动、检查、停止 **OpenAI 官方 tunnel-client**，让 ChatGPT 通过 Secure MCP Tunnel 调用本机 AnkiMCP。

这是社区配套项目，不是 OpenAI 官方插件。它不重新实现 MCP，不捆绑或修改 AnkiMCP，不包含 OpenAI 二进制或用户配置。

```text
ChatGPT → OpenAI MCP / Secure Tunnel → 官方 tunnel-client → 本机 AnkiMCP → Anki
```

## 与已有 fork 的关系

- Anki MCP Server Addon 上游：[ankimcp/anki-mcp-server-addon](https://github.com/ankimcp/anki-mcp-server-addon)
- 作者的 fork：[zoeyzhang233666/anki-mcp-server-addon](https://github.com/zoeyzhang233666/anki-mcp-server-addon)
- 本仓库是一个单独的启动/状态界面，以上游或该 fork 的 HTTP MCP 为依赖，两者均可使用。
- `anki-mcp-server` 是另一个仓库；本项目所连接的是运行在 Anki 内部的 **server-addon**。

## Windows 和 macOS

| 层级 | macOS | Windows |
|---|---|---|
| 官方 tunnel-client 发布包 | Apple Silicon / Intel | x64 / ARM64 |
| 本插件 | 使用 Qt QProcess、动态路径，无外部 Python 依赖 | 同一份源码与安装包，选择 `.exe` |
| 旧 Mac 专用版本 | 曾在真实 ChatGPT 完成只读验收 | 不适用 |
| 本仓库新版 | 自动测试与人工验收范围见下 | 自动测试与人工验收范围见下 |

新版是可移植的重写，**不把旧版在 Mac 的成功当作新版实机验收**。CI 在 Windows/macOS 执行配置、校验、脱敏和打包测试；这不是两台系统上真实 Anki + ChatGPT 的端到端测试。目前 Windows 上的真实 Anki/ChatGPT 验收仍待完成。

## 安装与使用

1. 安装桌面 Anki 和 AnkiMCP Server Addon。启用 HTTP，默认地址为 `http://127.0.0.1:3141/`。保持 Anki 打开。
2. 安装 OpenAI 官方 [tunnel-client](https://github.com/openai/tunnel-client)。macOS 优先官方支持的 Homebrew 路径 `brew install openai/tools/tunnel-client`；Windows 从[官方 Releases](https://github.com/openai/tunnel-client/releases/latest)选择对应 `tunnel-client-…-windows-amd64.zip` 或 `windows-arm64.zip`，解压完整目录。不要绕过系统安全警告。
3. 从本仓库 Releases 下载 `.ankiaddon`。在 Anki「工具 → 插件 → 从文件安装」选择它，按 Anki 提示重启。也可用 `python tools/build.py` 自行打包。
4. 「工具 → OpenAI 隧道连接 → 设置」填写官方程序路径、已有 Tunnel ID、可选 Organization ID、本机 MCP 地址。macOS Homebrew 常见路径 `/opt/homebrew/bin/tunnel-client` 或 `/usr/local/bin/tunnel-client`；Windows 用文件选择器选实际解压目录内的 `tunnel-client.exe`。路径可以含空格。
5. 点「启动连接」，在隐藏输入框填写**现有 Runtime API Key**。插件先运行 `doctor --explain`，通过后启动 `run`。密钥仅用于本次进程环境，**不保存到文件、Anki 设置或系统凭据库**；停止后再次启动需要重新输入。程序不创建密钥、隧道或付费服务。
6. 「查看状态」确认轮询；「打开管理界面」打开该进程动态分配的回环 `/ui`。
7. 在 ChatGPT 普通聊天中使用已有 Anki Local 插件，执行 `list_decks(include_stats=false)`，与本机牌组对照。Ready / Connected 不构成端到端验收。

本插件启动的客户端由 Anki 拥有，关闭 Anki 时停止；不会登录自启。使用时无需额外终端或单独安装 Python。`user_files` 只存运行配置和健康地址；Anki 自身的插件配置存非秘密设置。勿将个人运行目录提交到 GitHub。

### 已有旧插件的电脑

这台电脑原来的“ChatGPT 本地连接”是 Mac 专用启动器。新版没有自动替换它或停止它。**切换前先在旧插件停止已有连接**；禁用旧插件，再安装使用新版，避免同时启动同一 Tunnel ID 的多个客户端。新版只管理自己启动的进程，不能停止旧插件或别的电脑上的进程。manifest 声明与旧插件冲突。

### 换一台电脑

GitHub 保存程序，不能自动迁移 Anki 数据、账户授权或操作系统二进制。在新电脑安装对应系统的依赖，使用 AnkiWeb 或自己已有的备份迁移牌组；同步是用户单独的操作，本插件不执行同步。

切换使用电脑时，**先停止旧电脑对同一 Tunnel ID 的客户端**，新电脑再填原有 Tunnel ID 和有权使用它的 Runtime Key。若想多台电脑同时连接各自独立的 Anki 集合，应分别规划隧道及 ChatGPT 插件绑定，避免请求被另一台电脑接收；本项目不会自动创建它们。

同一账号还需正确的 Platform 组织、ChatGPT workspace 关联和 Tunnels Read / Use 权限；代码安装本身不授予权限。可先复用原有 Anki Local 自定义插件，无需为了迁移删除重建它。

## 安全与排错

- MCP 与管理界面仅使用回环地址，无公网入站端口。
- 不上传 Anki 数据、密钥、个人 ID、诊断日志或隧道配置；发布包仅包含 4 个允许的源码/默认配置文件。
- 默认 HTTP MCP 不使用额外认证。如果本机 AnkiMCP 配置了 API Key，本版未提供额外认证头配置，请先不要切换；本项目不要求关闭已有认证。
- API Key 只用于 OpenAI 官方控制面。安装官方二进制并自行核对来源；不要选择不可信的可执行文件。
- 输出按完整行脱敏后仅保留内存尾部，不开启 raw HTTP 日志。密钥在子进程运行期间需要留在该进程的环境中，这不是对本机同用户恶意软件的隔离保证。
- `MCP SSE probe returned 429` 无法单凭 Ready 定位。对照 `/health?details=true`、`/metrics` 与调用时间。ChatGPT 共用连接器曾有 [SSE 429 误分类并丢失 Retry-After 的公开记录](https://github.com/openai/tunnel-client/issues/103)，相似错误不证明同一根因。避免不停重建密钥/隧道或密集重试。
- 官方文档：[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)、[权限](https://github.com/openai/tunnel-client/blob/master/docs/permissions.md)。

## 开发与验收

```sh
python -m unittest discover -s tests -v
python -m compileall -q addon tools
python tools/build.py
```

发布前人工验收：在目标系统真实 Anki 中完成设置 → doctor → run → 状态 → ChatGPT 普通聊天 list_decks → 停止 → 关闭 Anki，检查子进程退出。还需检查错误密钥、无本地 MCP、程序路径含空格、无程序权限及重复启动提示。请勿使用修改牌组/卡片的工具作为连接测试。

MIT License。AnkiMCP 和 OpenAI tunnel-client 是单独的依赖，分别遵循各自许可证。
