# V1.6 Codex assistant 接口

分支：`codex/v1.6-assistant`；基线：最新 main `ec4affb`。仅 Codex 模块、测试、usage.py 和本文件；无配置更改、合并或推送。

## 进度

- 完成第 1 项：任务小结，25 项合成测试通过。最初测试暴露 fixture SQLite 连接未关闭以及损坏日志被跳过，已分别修复并重新验证。
- IN PROGRESS：第 2 项窗口定位；其后派活命令、历史列表，每项独立提交。

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
