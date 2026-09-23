# petoken

petoken 是一个 Windows 桌宠：跟随当前打开的 Codex 或 OpenCode 任务，按需显示本机准确的 token 用量、5 小时/每周额度（Codex）、重置倒计时和费用（Codex 为 API 等价估算，OpenCode 为已记录金额）；平时只显示已批准的角色形象。

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

## 亮点

- 自动跟随当前 Codex/OpenCode 任务（Windows 辅助功能标题与 verified activity），支持固定任务与任务/项目范围；设置中可在自动、Codex、OpenCode 之间切换跟踪提供方。
- 本地增量解析数字用量事件，不发送模型请求、不导出对话、不读取凭据；缓存输入与推理 token 不重复计入总量。
- 完整 Token Analytics：原始字段、派生指标、模型 / 会话 / 日期分组、本地 lifetime，未知值显示 `N/A` 而非假零。Codex 显示官方 total 与派生指标；OpenCode 显示 Input / Output / Reasoning / Cache Read / Cache Write 五个原始分类，以及已验证版本（1.18.31/1.18.32）的记录 Total（五类之和，非账单、非上下文；缺失/部分/未验证版本时为 N/A），费用为已记录金额且币种未知。
- Codex 工作 / 待机 / 打字 / 麦克风 / 音乐状态带进入与退出防抖；默认始终是批准的角色。

## 使用

1. 在 [GitHub Releases](https://github.com/windknows-ai/petoken/releases) 下载 Windows x64 压缩包。
2. 解压整个文件夹并双击其中的 exe（后续版本为 `petoken.exe`；V1.0.0 发布件名为 `CodexWisp.exe`）。`_internal` 文件夹也是程序的一部分，不要只复制 exe。
3. 按需保持所选数据源运行：跟踪 Codex 时保持 Codex 桌面客户端开启；跟踪 OpenCode 时保持 OpenCode 运行（有活跃任务时才显示实时 Working 状态）。可在设置中切换跟踪提供方；任一来源缺失时对应视图只会诚实显示不可用。

交互：悬停约 0.35 秒或单击桌宠显示用量面板，离开约 0.7 秒收起；拖动移动；右键打开菜单；`Alt + 方向键` 移动面板。详细行为见 [V1.0.0 发布说明](docs/RELEASE_NOTES_v1.0.0.md)。

## 数据与隐私

只读取：Codex 只读 SQLite 任务元数据与 JSONL 数字用量事件、只读 `account/rateLimits/read` 结果、OpenCode 只读 SQLite 会话/消息/步骤元数据（列白名单，不含标题、正文、工具参数、凭据、分享链接）、Windows 任务标题与活动布尔状态、媒体会话标题/作者/字幕元数据（仅内存显示）、加拿大央行公开汇率（USD/CAD/EUR/CNY，仅用于 Codex 估算）。不保存按键内容、音频、字幕或媒体名称，也不上传本地用量。

本地来源要求：Codex 桌面客户端（`~/.codex`）与/或已安装的 OpenCode（`~/.local/share/opencode/opencode.db`，opencode-ai 1.18.31 已验证）；任一来源缺失时对应视图诚实显示不可用，不影响另一提供方。

## 从源码运行

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe widget.py
```

测试与本地记录核对：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\verify_local.py
```

构建发行版：`.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`，然后运行 `.\build.ps1 -Package`，输出 `dist\petoken\` 与 `dist\petoken-Windows-x64.zip`。

## 版本与文档

- 当前版本：V1.2.0（[CHANGELOG](CHANGELOG.md)；历史版本详见 [V1.1.0 发布说明](docs/RELEASE_NOTES_v1.1.0.md)）
- Token 公式与字段：[docs/TOKEN_ACCOUNTING.md](docs/TOKEN_ACCOUNTING.md)
- 设计与交互约定：[DESIGN.md](DESIGN.md)
- 角色图片与归属：[docs/ARTWORK.md](docs/ARTWORK.md)
- 第三方组件：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

源代码采用 [MIT License](LICENSE)；角色图片不在 MIT 授权范围内。本工具是独立项目，与 OpenAI 或任何游戏发行商无隶属或背书关系。