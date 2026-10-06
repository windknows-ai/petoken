# V1.6 Codex assistant 接口

分支：`codex/v1.6-assistant`；基线：最新 main `ec4affb`。仅 Codex 模块、测试、usage.py 和本文件；无配置更改、合并或推送。

## 进度

- 完成第 1 项：任务小结，25 项合成测试通过。最初测试暴露 fixture SQLite 连接未关闭以及损坏日志被跳过，已分别修复并重新验证。
- 完成第 2 项：窗口定位，20 项测试通过（含对测试自身进程的原生 helper 检查；没有 Codex 数据依赖或真人窗口前置）。
- IN PROGRESS：第 3 项派活命令；其后历史列表，独立提交。

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
