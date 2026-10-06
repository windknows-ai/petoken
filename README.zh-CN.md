# Petoken

[English](README.md) | **简体中文**

> Codex 与 Claude Code 的桌面 AI 编程小伙伴：跟着你的任务，诚实地显示 token 用量、额度和费用。

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community（社区版）** 是 Petoken 免费、开源的版本。v1.5.0 同时跟踪 Codex 和 Claude Code（蓝色和金色的任务星星），任务完成、出错或等你确认时会提醒你，在人物头顶的小卡片里显示剩余的上下文和额度，还有一个本机工作台，用来管理项目、待办、便签和提醒。

## 能做什么

Petoken 是住在 Windows 桌面上的小伙伴。它会跟踪 Codex 和 Claude Code 中经过验证的任务，按对话、项目或全部三种范围显示 token 用量和费用估算。人物平时在桌面待机，点一下就能打开用量面板。

- **Codex + Claude Code**：在 设置 → 跟踪来源 里选择 自动（默认）、Codex 或 Claude Code。Codex 的星星是蓝色，Claude Code 的星星是金色。
- **任务星星**：人物周围有一圈立体星环，每个任务一颗星；超过 8 个任务时分页显示，点一颗星就能看这个任务的详情。
- **任务实时用量**：当前任务的输入 / 输出 / 推理 / 缓存明细。
- **额度和重置时间**：Codex 的 5 小时 / 每周额度和重置倒计时（Pro 账号只有每周额度）；Claude Code 的 Pro/Max 额度需要打开 **设置 → 同步 Claude 用量**。
- **用量卡片**：任务运行时，人物头顶的小卡片会为每个开着的 App 显示剩余的上下文、5 小时和每周额度，以及重置时间。
- **通知**：任务完成、出错、等你确认，或 5 小时额度快用完时，人物会欢呼、难过或招手，同时弹出通知；通知记录保留 30 天，还有免打扰和个人提醒。
- **工作台**：本机的项目、待办、纯文本便签和提醒，可以把任务关联到项目。
- **跟着你做事**：你打字时她也在打字，你放音乐时她戴上耳机并显示歌名，你开麦克风时她拿起麦克风。
- **费用**：只有在模型价格和 token 数据都齐全时，才给出等价 API 费用估算（美元 / 加元 / 欧元 / 人民币），否则显示 `N/A`。
- **Token 统计**：按模型 / 会话 / 日期分组，保留本机历史记录。
- **诚实显示未知**：未知的模型就写「未知」，拿不到的数字就写 `N/A`，真正的 0 才写 0，不完整的数据会明确标出。
- 日常 / Token 两种模式，完整 / 简洁两种数字格式，简体中文 / 英文界面，固定显示、始终置顶、人物大小可调。

## 最新版本：v1.5.0

推荐下载 **一键安装程序** [Petoken-Setup-v1.5.0.exe](https://github.com/windknows-ai/petoken/releases/download/v1.5.0/Petoken-Setup-v1.5.0.exe)，也可以在 [v1.5.0 发布页](https://github.com/windknows-ai/petoken/releases/tag/v1.5.0) 下载免安装的压缩包。可以用发布页里的校验文件核对 SHA-256。更新内容见 [CHANGELOG.md](CHANGELOG.md)。

## 支持的来源

### Codex + Claude Code

Petoken 只跟踪 Codex 和 Claude Code 两个来源。「自动」模式会跟随正在工作的那个来源；星环会同时显示两边的任务（**Codex 蓝色，Claude Code 金色**），星星以项目名命名。Claude Code 的用量来自它本机的会话记录和运行中会话的登记信息（命令行和桌面版 Code 页面都支持）。上下文按每个模型官方的上下文窗口计算。Claude Code 本身不在本地保存额度，所以它的 5 小时 / 每周额度需要打开 **设置 → 同步 Claude 用量**（claude.ai Pro/Max 账号）才会显示，否则显示 `N/A`。

### 用量卡片和用量面板

任务运行时，人物头顶会出现一张不挡鼠标的小卡片，为每个开着的 App（Codex 桌面版或命令行、Claude 桌面版或命令行）显示剩余的上下文、5 小时和每周额度，以及重置倒计时。账号没有的额度窗口不会显示。点人物可以打开完整的用量面板；在人物右键菜单里勾选 **用量面板（常驻显示）** 可以让面板一直显示并置顶，每次启动时默认不勾选。

### 通知

任务完成、出错、等你确认，或者 5 小时额度只剩 20% 时，人物会做出反应，并弹出 Windows 通知；点「等待确认」的通知会打开对应的任务。所有通知在工作台的 **通知** 页保留 30 天，旁边是一次 / 每天 / 每周的个人提醒。**免打扰**（手动或定时）期间不弹窗、人物不做反应，但通知仍会记录。

| | Claude Code | Codex 命令行 | Codex 桌面版 |
| --- | --- | --- | --- |
| 任务完成 | 1 秒内* | 几秒内 | 几秒内 |
| 出错 | 1 秒内* | — | — |
| 等你确认 | 1 秒内* | 几秒内 | — |

\* 需要打开 **设置 → Claude 即时通知**（会在 Claude Code 的设置里加入 hooks，修改前先备份）。不打开时，任务完成会通过定期检查发现。Codex 桌面版不向其他程序公开「出错」和「等待确认」状态，所以这两项不会提醒。

### 工作台

工作台有首页、项目、待办、便签和通知几个页面，可以从用量面板、人物右键菜单或托盘打开。个人记录只保存在本机的 `%LOCALAPPDATA%\CodexWisp\workbench.sqlite3`；便签用「保存」或 Ctrl+S 保存，切换或退出时会保护未保存的内容。Codex 和 Claude Code 的任务可以关联到项目。首次使用有可跳过的中英文新手教程。

### 来源状态

| 来源 | 状态 | 能看到什么 |
| --- | --- | --- |
| Codex 桌面版和命令行 | 支持 | 经过验证的用量合计、5 小时 / 每周额度和重置时间、等价 API 费用、工作 / 空闲状态 |
| Claude Code（命令行 / 桌面版 Code 页面） | 支持 | 去重后的用量合计、按 Anthropic 官方价格计算的等价 API 费用、来自会话登记的工作 / 空闲状态；打开 **设置 → 同步 Claude 用量** 后显示 5 小时 / 每周额度（Pro/Max，通过 Claude Code 的状态栏），否则显示 N/A |

某个来源缺失或数据过期时，界面会如实显示。不会读取其他任何来源。

## 安装和使用

1. 从 [GitHub 发布页](https://github.com/windknows-ai/petoken/releases/tag/v1.5.0) 下载 **Petoken-Setup-v1.5.0.exe**，双击安装：一路「Next」即可，不需要管理员权限，会自动创建开始菜单（可选桌面）快捷方式，可以在 Windows「设置 → 应用」里卸载。
   - Windows 可能提示「Windows 已保护你的电脑」，因为安装程序还没有数字签名。点「更多信息」→「仍要运行」即可。
   - 不想安装的话，也可以下载 `Petoken-v1.5.0-Windows-x64.zip`，**完整解压整个文件夹**后运行 `petoken.exe`（`_internal` 文件夹是程序的一部分，不能只复制 exe）。
2. 像平常一样使用 Codex 或 Claude Code，Petoken 会自动跟随正在运行的任务。想看 Claude 额度可以打开 **设置 → 同步 Claude 用量**。界面默认是英文，可以在 设置 → 语言 里切换成简体中文。

操作：点人物打开面板；拖动人物可以移动；右键打开菜单；`Alt + 方向键` 移动面板。

## 隐私 / 本地优先

- Petoken 读取本机 Codex 的任务元数据和用量数字、窗口里的任务标题和活动状态，以及只存在内存里的媒体信息（用于显示歌名）。它也读取 Claude Code 本机的会话记录（只取用量数字和会话元数据，消息内容在内存里直接丢弃）和运行中会话的登记信息。不读取其他任何来源的数据。
- **同步 Claude 用量** 需要你手动打开：它会在 Claude Code 的设置里加一条状态栏命令（修改前先备份），只记录用量数字。在设置里关掉就会移除。
- 从不导出对话记录或凭据，从不发送模型请求，从不录音或记录按键，从不上传本机用量。
- 详情见 [`docs/USAGE_MODEL.md`](docs/USAGE_MODEL.md) 和 [`SECURITY.md`](SECURITY.md)。

## 从源码构建和测试

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe widget.py
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

打包 Windows 版本（`dist\petoken\` 和 `dist\petoken-Windows-x64.zip`；加 `-Installer` 会同时生成安装程序，需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\build.ps1 -Package -Installer
```

## 文档

- 用量含义（统计什么、`N/A` 表示什么）：[`docs/USAGE_MODEL.md`](docs/USAGE_MODEL.md)
- 来源记录：[`docs/PROVIDERS.md`](docs/PROVIDERS.md)
- Token 计算公式和字段：[`docs/TOKEN_ACCOUNTING.md`](docs/TOKEN_ACCOUNTING.md)
- 产品路线图：[`ROADMAP.md`](ROADMAP.md)
- 界面设计约定：[`DESIGN.md`](DESIGN.md)
- 人物美术和署名：[`docs/ARTWORK.md`](docs/ARTWORK.md)
- 安全策略：[`SECURITY.md`](SECURITY.md)
- 参与贡献：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 第三方组件：[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- v1.5.0 发布说明：[`docs/RELEASE_NOTES_v1.5.0.md`](docs/RELEASE_NOTES_v1.5.0.md)

## 社区和许可

Petoken 社区版是开源软件。程序源代码使用 MIT 许可（见 [LICENSE](LICENSE)）；人物美术不在 MIT 许可范围内（见 [docs/ARTWORK.md](docs/ARTWORK.md)）。欢迎在 [GitHub Issues](https://github.com/windknows-ai/petoken/issues) 反馈问题和建议，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。Petoken 是独立项目，与 OpenAI、Anthropic 或任何游戏发行商没有关联，也未获得其背书。
