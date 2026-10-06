# Petoken

[English](README.md) | **简体中文**

> Codex 与 Claude Code 的桌面 AI 编程小伙伴：跟着你的任务，诚实地显示 token 用量、额度和费用。

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community（社区版）** 是 Petoken 免费、开源的版本。v1.7.0 能自动更新、带新用户上手、把待办定时或马上交给 Claude Code 或 Codex，Codex 的通知和审批也上了桌宠。从 v1.6 起它就是帮你省时间的 AI 助手：提前预测额度什么时候用完；在人物旁边直接批准 Claude Code 的权限请求、回答它的提问、审批它的计划；一键跳到任务所在的窗口；在任何地方快速派活；每天、每周告诉你 AI 帮你做了多少。之前版本的 Codex 和 Claude Code 用量跟踪、通知和本机工作台都还在。

## 能做什么

Petoken 是住在 Windows 桌面上的小伙伴。它会跟踪 Codex 和 Claude Code 中经过验证的任务，按对话、项目或全部三种范围显示 token 用量和费用估算。人物平时在桌面待机，点一下就能打开用量面板。

- **Codex + Claude Code**：在 设置 → 跟踪来源 里选择 自动（默认）、Codex 或 Claude Code。Codex 的星星是蓝色，Claude Code 的星星是金色。
- **任务星星**：人物周围有一圈立体星环，每个任务一颗星；超过 8 个任务时分页显示，点一颗星就能看这个任务的详情。
- **任务实时用量**：当前任务的输入 / 输出 / 推理 / 缓存明细。
- **额度和重置时间**：Codex 的 5 小时 / 每周额度和重置倒计时（Pro 账号只有每周额度）；Claude Code 的 Pro/Max 额度需要打开 **设置 → 同步 Claude 用量**。
- **用量卡片**：任务运行时，人物头顶的小卡片会为每个开着的 App 显示剩余的上下文、5 小时和每周额度，以及重置时间。
- **通知**：任务完成、出错、等你确认，或 5 小时额度快用完时，人物会欢呼、难过或招手，同时弹出通知；通知记录保留 30 天，还有免打扰和个人提醒。
- **预测和建议**（1.6 新增）：按现在的速度，额度什么时候用完；另一个开着的 App 还有多少额度；上下文快满了；任务长时间没有进展；用完的额度恢复了。
- **在人物旁边回复 Claude**（1.6 新增，需要打开）：权限请求（允许 / 以后都允许 / 拒绝）、Claude 的选择题、Claude 的计划（接受 / 接受并允许编辑 / 修改）。
- **任务小结和一键直达**（1.6 新增）：任务完成的通知会写改了哪些文件、用了多久、花了多少钱；点一下就能切到任务所在的窗口。
- **快速派活**（1.6 新增）：按快捷键弹出小窗口，写下要做什么、选项目文件夹和 Claude Code 或 Codex，就会在新终端里开始。
- **日报 / 周报**（1.6 新增）：今天 / 本周处理的任务、AI 工作时长、改过的文件、用量和费用，还有可以搜索的历史任务。
- **工作台**：本机的项目、待办、纯文本便签和提醒，可以把任务关联到项目。
- **跟着你做事**：你打字时她也在打字，你放音乐时她戴上耳机并显示歌名，你开麦克风时她拿起麦克风。
- **费用**：只有在模型价格和 token 数据都齐全时，才给出等价 API 费用估算（美元 / 加元 / 欧元 / 人民币），否则显示 `N/A`。
- **Token 统计**：按模型 / 会话 / 日期分组，保留本机历史记录。
- **诚实显示未知**：未知的模型就写「未知」，拿不到的数字就写 `N/A`，真正的 0 才写 0，不完整的数据会明确标出。
- 日常 / Token 两种模式，完整 / 简洁两种数字格式，简体中文 / 英文界面，固定显示、始终置顶、人物大小可调。

## 最新版本：v1.7.1

在 [v1.7.1 发布页](https://github.com/windknows-ai/petoken/releases/tag/v1.7.1) 下载 **一键安装程序** [Petoken-Setup-v1.7.1.exe](https://github.com/windknows-ai/petoken/releases/download/v1.7.1/Petoken-Setup-v1.7.1.exe)，可以用发布页里的校验文件核对 SHA-256。更新内容见 [CHANGELOG.md](CHANGELOG.md)。

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

\* 需要打开 **设置 → Claude → Claude 即时通知**（会在 Claude Code 的设置里加入 hooks，修改前先备份）。不打开时，任务完成会通过定期检查发现。Codex 桌面版不向其他程序公开「出错」和「等待确认」状态，所以这两项不会提醒。不是你亲自打开的后台 Claude 会话（`claude -p`、脚本、agent）完成时只记进历史，不弹窗。Petoken 运行时会关掉 Claude 桌面版自己的弹窗，避免同一件事弹两次（设置 → Claude；退出 Petoken 时恢复你原来的设置）。

### 省时间的 AI 助手（v1.6）

- **预测和建议。** 根据最近一小时（或者从额度窗口开始到现在）的用量速度，预测 5 小时和每周额度什么时候用完、会不会在重置之前用完；如果另一个开着的 App 还有额度，会建议你先切过去。上下文快满（该 `/compact` 了）、任务 20 分钟没有进展、用完的额度或速率限制恢复了，也会提醒你。提示会显示在用量卡片里的一行，每种情况也会发一条通知。可以在 设置 → 助手与通知 → 预测和建议 里关掉。
- **在人物旁边回复 Claude**（需要打开：设置 → Claude → 在桌宠上批准 Claude）。Claude Code 请求权限时，人物旁边会弹出卡片：允许、以后都允许（保存到项目的本地设置里，可以在「已允许的规则」里查看和撤销）、拒绝，或者交回 Claude 自己处理。Claude 的选择题和计划有专门的卡片：点选项或者自己写答案；接受计划、接受并允许编辑，或者写意见要求修改。一段时间没有回答（权限请求 45 秒，提问和计划 5 分钟），或者 Petoken 没在运行，Claude Code 会像平常一样自己问你。命令行和桌面版 Code 页面都支持。Codex 目前还不允许其他程序代为回答。
- **任务小结和一键直达。** 任务完成的通知会写改了几个文件、这一轮用了多久、等价 API 费用（Codex 显示改过的文件）。点通知、星星详情里的 ↗ 或者报告里的一行，就会切到任务所在的窗口（Claude 桌面版、终端、VS Code；Codex 在能确认对应窗口时支持）。
- **快速派活。** 按 Ctrl+Alt+Space（可以在 设置 → 助手与通知 里换成别的快捷键或者关掉），或者从人物右键菜单、托盘打开一个小窗口：写下要做什么、选项目文件夹（会列出最近用过的）、选 Claude Code 或 Codex。点「开始」就会打开新终端运行对应的命令行工具，任务随后会变成一颗星星。你写的内容作为数据传递，不经过任何 shell，也不会加任何跳过权限的参数。
- **日报 / 周报。** 工作台 → 报告（人物右键菜单里也有）：今天或本周处理的任务、AI 工作时长（每一轮从你提问到回复完成）、改过的文件、用量、等价 API 费用和比上期的变化，下面是可以搜索的 Claude 和 Codex 历史任务。双击一行就能切到那个任务的窗口。

### v1.7 新增

- **自动更新。** Petoken 每天向 GitHub 读取一次最新版本（只读请求，不发送这台电脑的任何信息）。有新版本时会显示更新内容，可以选择现在更新、以后再说或跳过这个版本；下载的安装程序必须和发布页的 SHA-256 校验值一致才会使用，然后静默安装并自动重新打开。勾选「自动安装」后，会在没有任务运行时自己更新。在 设置 → 常规 里设置。
- **新手引导。** 第一次打开时，向导会带新用户设置语言、Claude Code 和 Codex 的集成（每项都写明会改什么）以及助手选项。升级的用户不会看到，可以在设置里重新打开。
- **把待办交给 AI。** 工作台 → 待办 →「交给 AI…」：选 Claude Code 或 Codex、文件夹、模型和推理强度，现在开始或者定时。任务会和待办对应起来，第一次真正完成时自动勾掉待办并写一条小结便签（被你中断的不算）。「收回」可以取消。错过时间的待办按 设置 → 助手与通知 里的选择处理：下次提醒我，或者自动补跑。
- **Codex 也上了桌宠**（需要打开：设置 →「Claude 和 Codex」）：Codex 的 hook 会即时送来完成和等待确认的通知，Codex 的权限请求也会变成卡片（单次允许 / 拒绝）。需要在 Codex 里用 `/hooks` 信任一次，而且 Codex 的审批模式要会询问（不能是 `never`）。Codex 的提问和计划目前还不能由其他程序回答。
- **快速派活升级。** 模型和推理强度从各个 App 自己的实时列表里选（Claude Code 的模型目录、Codex 的模型列表：有新模型会自动出现，下线的会自动消失）；勾选「只是聊聊」就不需要项目文件夹。
- **报告更快、诊断导出、安装包更小。** 报告从后台缓存直接显示；设置 → 关于数据 →「导出诊断信息」会先显示全部内容再保存成 zip，方便反馈 bug；安装包不再带 Pillow。

### 工作台

工作台有首页、项目、待办、便签和通知几个页面，可以从用量面板、人物右键菜单或托盘打开。个人记录只保存在本机的 `%LOCALAPPDATA%\CodexWisp\workbench.sqlite3`；便签用「保存」或 Ctrl+S 保存，切换或退出时会保护未保存的内容。Codex 和 Claude Code 的任务可以关联到项目。首次使用有可跳过的中英文新手教程。

### 来源状态

| 来源 | 状态 | 能看到什么 |
| --- | --- | --- |
| Codex 桌面版和命令行 | 支持 | 经过验证的用量合计、5 小时 / 每周额度和重置时间、等价 API 费用、工作 / 空闲状态 |
| Claude Code（命令行 / 桌面版 Code 页面） | 支持 | 去重后的用量合计、按 Anthropic 官方价格计算的等价 API 费用、来自会话登记的工作 / 空闲状态；打开 **设置 → 同步 Claude 用量** 后显示 5 小时 / 每周额度（Pro/Max，通过 Claude Code 的状态栏），否则显示 N/A |

某个来源缺失或数据过期时，界面会如实显示。不会读取其他任何来源。

## 安装和使用

1. 从 [GitHub 发布页](https://github.com/windknows-ai/petoken/releases/tag/v1.7.1) 下载 **Petoken-Setup-v1.7.1.exe**（v1.7.0 及以后的版本会自动更新），双击安装：一路「Next」即可，不需要管理员权限，会自动创建开始菜单（可选桌面）快捷方式，可以在 Windows「设置 → 应用」里卸载。升级时会保留你的设置和工作台。
   - Windows 可能提示「Windows 已保护你的电脑」，因为安装程序还没有数字签名。点「更多信息」→「仍要运行」即可。
2. 像平常一样使用 Codex 或 Claude Code，Petoken 会自动跟随正在运行的任务。在 **设置 → Claude** 里可以打开「同步 Claude 用量」（显示额度）、「Claude 即时通知」和「在桌宠上批准 Claude」。界面默认是英文，可以在 设置 → 常规 → 界面语言 里切换成简体中文。

操作：点人物打开面板；拖动人物可以移动；右键打开菜单（快速派活、工作台、报告、设置；显示相关的选项在「更多」里）；`Alt + 方向键` 移动面板。

不需要管理员权限，也不需要改系统设置。Petoken 给 Claude Code 装的 hook 是当前用户自己的 PowerShell 脚本，启动时带 `-ExecutionPolicy Bypass`，只对那一次运行生效，所以在 Windows 默认的脚本策略下也能运行。公司管理的电脑如果用组策略强制了脚本策略，hook 可能会被拦住，这时 Claude Code 会照常自己问你。

## 隐私 / 本地优先

- Petoken 读取本机 Codex 的任务元数据和用量数字、窗口里的任务标题和活动状态，以及只存在内存里的媒体信息（用于显示歌名）。它也读取 Claude Code 本机的会话记录（只取用量数字和会话元数据，消息内容在内存里直接丢弃）和运行中会话的登记信息。不读取其他任何来源的数据。
- **同步 Claude 用量** 需要你手动打开：它会在 Claude Code 的设置里加一条状态栏命令（修改前先备份），只记录用量数字。在设置里关掉就会移除。
- **在桌宠上批准 Claude** 需要你手动打开：hook 通过 `%LOCALAPPDATA%\CodexWisp\claude-approvals` 里的文件把请求交给 Petoken，回答后马上删除；一个小日志只记录时间和工具名。任务小结、报告和预测只从本机记录里读取工具名、文件路径、时间和用量数字，不读取对话内容和文件内容。
- 关掉 Claude 桌面版的弹窗，只改你自己 Windows 通知设置里 Claude 这一项，退出 Petoken 时恢复。
- 从不导出对话记录或凭据，从不发送模型请求，从不录音或记录按键，从不上传本机用量。唯一的联网请求是每天一次的更新检查（只读取 GitHub 上最新版本的信息），以及你选择更新时下载安装程序和校验文件；可以在 设置 → 常规 里关掉检查。
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

打包一键安装程序（生成 `dist\Petoken-Setup-v<版本号>.exe`，需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\build.ps1 -Installer
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
- v1.7.1 发布说明：[`docs/RELEASE_NOTES_v1.7.1.md`](docs/RELEASE_NOTES_v1.7.1.md)（修复）；v1.7.0：[`docs/RELEASE_NOTES_v1.7.0.md`](docs/RELEASE_NOTES_v1.7.0.md)
- 之前的发布说明：[`docs/RELEASE_NOTES_v1.6.0.md`](docs/RELEASE_NOTES_v1.6.0.md)、[`docs/RELEASE_NOTES_v1.5.0.md`](docs/RELEASE_NOTES_v1.5.0.md)

## 社区和许可

Petoken 社区版是开源软件。程序源代码使用 MIT 许可（见 [LICENSE](LICENSE)）；人物美术不在 MIT 许可范围内（见 [docs/ARTWORK.md](docs/ARTWORK.md)）。欢迎在 [GitHub Issues](https://github.com/windknows-ai/petoken/issues) 反馈问题和建议，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。Petoken 是独立项目，与 OpenAI、Anthropic 或任何游戏发行商没有关联，也未获得其背书。
