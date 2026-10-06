# V1.6 Codex assistant 接口

分支：`codex/v1.6-assistant`；基线：最新 main `ec4affb`。仅 Codex 模块、测试、usage.py 和本文件；无配置更改、合并或推送。

## 进度

- 完成第 1 项：任务小结，25 项合成测试通过。最初测试暴露 fixture SQLite 连接未关闭以及损坏日志被跳过，已分别修复并重新验证。
- 完成第 2 项：窗口定位，20 项测试通过（含对测试自身进程的原生 helper 检查；没有 Codex 数据依赖或真人窗口前置）。
- 完成第 3 项：派活命令，9 项测试通过，含实际 PowerShell → 合成 Python recorder 的安全转义检查。初次检测测试的 mock 未真正停止，已修正测试 patch 管理并复验。
- 第 4 项历史列表的 22 项合成测试通过。历史 fixture 扩展 schema 后暴露位置式 INSERT 不兼容额外列，已改为显式列名；不影响运行时代码。
- 四项实现和验证完成，等待 Claude 接入及用户验收；无实际 Codex 派活、配置改动、合并或推送。
- 前三项提交：recap `a9e979d`，focus `aa6e870`，launch `0e96a4c`；历史接口为本文件最后一次所在的独立提交，可用 `git log --oneline main..HEAD` 获取完整四项 SHA。
- 最终回归：337 项 PASS（9.039 秒）；新增接口测试 76 项（25 recap / 20 focus / 9 launch / 22 history）。测试覆盖 Codex approval/events/usage/scopes/activity/providers/poller/selection/task projection/analytics/pricing/notifications 及四个新模块；git diff --check PASS。没有重跑共享 UI 全量套件或构建 Windows 包，因此没有声明视觉/打包验收。

## 1. 任务小结

`codex_recap.recap(home, thread_id)` 返回 `files, started_at, finished_at, duration_s`。
时间单位为 UTC epoch 秒；用时为 thread 首次有证据的开始到最后结束的墙钟时间，包含多轮交互间隔，不是模型计算时间。最后一轮仍在运行时结束和用时为 None。

只读 `state_*.sqlite` 定位 rollout，按线程核实 session_meta；生命周期认 task_started/turn_started、task_complete/turn_complete、turn_aborted。优先使用事件的 started_at/completed_at，旧格式使用明确的事件时间。不使用 mtime、updated_at 或闲置时长。没有 rollout 生命周期时，只读 thread_history_1.sqlite 中该线程的 turn 时间和明确终态。

文件来源：成功 patch_apply_end.changes；新分页日志的 item_completed/FileChange/completed；同一 apply_patch 调用的实际工具成功路径摘要。只输出相对项目目录的规范路径；包含已删除和重命名路径，排除目录外路径，不保留内容。这里是有明确成功证据的路径集合，不保证覆盖 shell 脚本、外部工具、其他线程或子代理的任意写入。无受支持的成功记录时 files=None；显式空成功记录可返回 []，不代表整个项目从未变化。

桌面、VS Code、CLI、exec 使用同一读取方式；source 不是支持程度的保证。缺文件、schema 不识别、未结束、日志尾部未写完、损坏记录、缺时间均保持相应未知值；fork 排除创建时间之前的继承历史，缺 fork 时间时不猜。未知字段不补零。

官方结构参考（仅学习协议，不复制外部实现，无新依赖）：

- [Codex protocol](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/protocol.rs)：任务时间、patch 成功状态和路径结构。
- [Codex items](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/items.rs)：分页 FileChange。
- [Rollout persistence policy](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/policy.rs)：legacy/paginated 保存方式不同，不能假定所有来源都有 patch_apply_end。

## 2. 窗口定位

`codex_focus.focus(home, thread_id) -> 'exact' | 'app' | None`。只在 Windows 实现；其他系统返回 None。仅在用户点击直达时调用，CIM/辅助进程可能用数秒，应由整合方在工作线程调用。

- desktop：按已验证的 Codex 安装路径定位当前可见 App 窗口，成功前置返回 app；不切换具体 thread。
- cli/exec：只有运行中 codex.exe 的明确 `resume <thread_id>` / `exec resume <thread_id>` 参数才能与 thread 关联。用隔离辅助进程 AttachConsole/GetConsoleWindow 查询；存在可见控制台窗口时返回 exact。
- Windows Terminal 的 pseudoconsole HWND 隐藏，不冒充标签页定位；若祖先进程明确属于一个有唯一窗口的 WindowsTerminal.exe，可前置该窗口并返回 app。新任务、不带 ID 的 resume picker、复杂全局参数排列、共享 daemon、已退出任务和 VS Code 暂无可靠映射，返回 None。
- 不用标题、项目名、cwd 或 prompt 中出现的 UUID 猜窗口。多个关联进程/终端窗口时返回 None；前置前重新核实 HWND 所属 PID，并核对实际前台 HWND。权限/Windows 前台策略拒绝也返回 None。
- 不启动 Codex、不自动恢复 thread、不改配置或向终端输入任何文字。App 未运行时返回 None，不冷启动。进程可能在快照后退出；这属于 best effort，不宣称跨用户/远程会话精确定位。

参考：[Microsoft GetConsoleWindow](https://learn.microsoft.com/en-us/windows/console/getconsolewindow)，官方明确说明 pseudoconsole HWND 不是本地可见终端窗口。接口决策测试全部使用合成进程/窗口；原生检查仅测试合成命令行的 Windows 参数解析及辅助脚本对测试进程自身的查询，没有切换真人窗口。

## 3. 命令行派活

`codex_launch.available() -> bool` 探测 Windows 上本机可用的原生 codex.exe 与 PowerShell；不检测登录、网络、权限或模型额度。复用现有 `_proxy_binary()` 的发现规则，不采用 .cmd/.ps1 wrapper。如果只有未知安装位置的包装脚本，available=False。

`launch_command(folder, prompt) -> list[str]` 只生成 argv，不启动任务。优先 `wt.exe --window new new-tab`，否则 PowerShell。目录必须实际存在，prompt 必须非空且没有 NUL；非法输入/超出 Windows 32767 字符命令行限制抛 ValueError，缺执行程序抛 RuntimeError。

prompt 和目录通过 UTF-8 JSON/base64 数据嵌入，再把固定脚本整体 UTF-16LE 编码为 EncodedCommand。原生 CLI 用 ProcessStartInfo/UseShellExecute=False 启动，并使用标准 Windows argv quoting，绕开 PowerShell 5.1 原生命令引用重组。prompt 放在 `codex --cd <folder> -- <prompt>` 的 `--` 后，不被当成 CLI 选项；原始文本也不进入 wt 的分号命令语法。无 Invoke-Expression、cmd /c、shell=True 或配置改动；不用 bypass 审批/沙箱参数。

Claude 接入：使用 `subprocess.Popen(argv, shell=False)`。PowerShell fallback 从有控制台的进程启动时，调用方需传 `creationflags=subprocess.CREATE_NEW_CONSOLE`，保证新窗口；Windows GUI 主进程没有控制台时也可统一传此 flag。不要自行把 argv 拼接成 shell 命令；本模块没有真正运行 Codex。

原生转义验证用后台 PowerShell 将合成参数传给 Python argv recorder，包含中文、引号、分号、换行、反斜杠和注入文本；只运行 recorder，不启动终端窗口或 Codex 任务。

参考：[Windows Terminal 参数](https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments)、[PowerShell EncodedCommand](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe)、[Codex CLI 参数](https://developers.openai.com/codex/cli/reference/)；只学习命令格式，没有复制代码。

## 4. 历史列表

`CodexStore(home).task_history(since_epoch) -> list[dict]`；另提供 `usage.task_history(since_epoch)`，采用现有 CODEX_HOME/default home 发现方式。每项字段：

| 字段 | 含义 |
|---|---|
| thread_id | 本地明确线程 ID |
| title | 现有 conversation_title 规则的名称/标题首行；未知为 None |
| project | 现有 project_identity 规则的项目名称（metadata、git origin、cwd）；未知为 None |
| started_at / finished_at | 与 recap 一致的 UTC epoch 秒；未知/最后一轮仍运行时结束为 None |
| total_tokens | 该线程自己的可核实本地 token 合计，沿用 SessionUsage/unique_records/summarize；未知或不完整为 None |
| usd | 现有定价表逐段计算的 API 等价 USD 估算；不是 ChatGPT/Codex 订阅账单。任一段未知价格/模型/必要计数（含 cache write）时为 None，不将已知段的部分费用当成总费用；旧实时面板的估算逻辑保持不变 |

按首次开始时间倒序、同时间 thread_id 排序。since_epoch 是包含边界的开始时间过滤；非法日期类型/非有限数/负值抛 ValueError。时间未知的线程不归入日期范围；传 None 可查询全部本地历史，未知开始的排最后。已归档任务及尚未结束任务均包括；只包括 desktop/vscode/cli/exec 根线程，不单列 subagent、不汇总子代理到父线程，不包含 Claude 数据。

复用现有重复事件、累计快照、counter reset、fork 继承去重和多模型估算。相同 DB 行去重，冲突的重复 ID 不猜；缺 session identity、截断/损坏/消失的 rollout、缺 fork 边界均不复用旧数字。即便某项指标为 None，其可读的标题/项目/时间仍可返回。不存在本地数据或 schema 不认识时返回 []，不宣称远端任务不存在。

这是显式报表查询，可能扫描全部本地 rollout（含日期范围之前的父线程，用于正确去重），目前不做跨调用缓存；应在 worker 中按需调用，不放进 UI 每几秒的常规轮询。全生命周期 elapsed 含等待和用户间隔，不可直接用于估算模型执行速度。thread 重新开始后结束时间重新未知；数字是查询时本地累计工作量，不是已经固定的财务账单。

since_epoch 过滤的是 thread 首次开始，而非最近活跃/结束时间；旧 thread 在今天恢复工作也不变成新的历史条目。日报周报若要当日 token/费用，需用现有 analytics 按 usage event 时间分配增量，不能把本接口的整个 thread 累计数当作当日消耗。

### Claude 接入需求

由 Claude 的 provider/通知/报表包装调用以上四个接口；这里只提供数据和明确的降级结果。费用标注 API 等价估算、未知时间不要分配给日报周报、focus='app' 不显示为“已打开具体任务”、派活按 argv + shell=False + 新控制台 flag 执行。无需修改 Codex 配置，本分支没有界面、通知中心、provider wrapper 或构建文件改动。
