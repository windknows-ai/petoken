# petoken

petoken 是一个 Windows 桌宠：跟随当前打开的 Codex 任务，按需显示本机准确的 token 用量、5 小时/每周额度、重置倒计时和 API 等价成本估算；平时只显示已批准的角色形象。

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

## 亮点

- 自动跟随当前 Codex 任务（Windows 辅助功能标题），支持固定任务与任务/项目范围。
- 本地增量解析数字用量事件，不发送模型请求、不导出对话、不读取凭据；缓存输入与推理 token 不重复计入总量。
- 完整 Token Analytics：原始字段、派生指标、模型 / 会话 / 日期分组、本地 lifetime，未知值显示 `N/A` 而非假零。
- 待机 / 打字 / 麦克风 / 音乐状态带进入与退出防抖；默认始终是批准的角色。

## 使用

1. 在 [GitHub Releases](https://github.com/windknows-ai/petoken/releases) 下载 Windows x64 压缩包。
2. 解压整个文件夹并双击其中的 exe（后续版本为 `petoken.exe`；V1.0.0 发布件名为 `CodexWisp.exe`）。`_internal` 文件夹也是程序的一部分，不要只复制 exe。
3. 保持 Codex 桌面客户端开启。

交互：悬停约 0.35 秒或单击桌宠显示用量面板，离开约 0.7 秒收起；拖动移动；右键打开菜单；`Alt + 方向键` 移动面板。详细行为见 [V1.0.0 发布说明](docs/RELEASE_NOTES_v1.0.0.md)。

## 数据与隐私

只读取：Codex 只读 SQLite 任务元数据与 JSONL 数字用量事件、只读 `account/rateLimits/read` 结果、Windows 任务标题与活动布尔状态、加拿大央行公开 USD/CAD 汇率。不保存按键内容、音频或媒体名称，也不上传本地用量。

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

- 当前版本：V1.0.0（[CHANGELOG](CHANGELOG.md)）
- Token 公式与字段：[docs/TOKEN_ACCOUNTING.md](docs/TOKEN_ACCOUNTING.md)
- 设计与交互约定：[DESIGN.md](DESIGN.md)
- 角色图片与归属：[docs/ARTWORK.md](docs/ARTWORK.md)
- 第三方组件：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

源代码采用 [MIT License](LICENSE)；角色图片不在 MIT 授权范围内。本工具是独立项目，与 OpenAI 或任何游戏发行商无隶属或背书关系。