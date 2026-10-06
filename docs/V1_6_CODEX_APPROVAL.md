# V1.6 Codex 审批检测

完成：2026-10-05（America/Toronto）。分支 `codex/v1.6-approval`；从本地 main `98de5eb` 新建。

## 结论与覆盖范围

**已实现有条件的明确检测：只读连接任务所属的现有控制 socket，读取线程运行时 status.activeFlags。waitingOnApproval 是等待批准的明确证据。当前本机桌面版使用独立 stdio 服务器，不能通过共享 daemon 观察到；这种情况返回 None，不能声称桌面通知已全部修复。**

| 运行方式 | 可否明确检测 | 本次验证 |
|---|---|---|
| CLI/桌面内置引擎，任务在当前 CODEX_HOME 的 control socket 所属服务器里 | 可以；命令、文件、权限请求均有 waitingOnApproval | 两套 0.160.0 程序分别隔离验证三种请求 |
| 本机当前桌面 GUI：独立 stdio app-server | 无法外部只读连接其现有 stdin/stdout；返回 None | 启动参数与官方实现核对：stdio 不创建控制 socket；本机共享 daemon loaded/list 为 0，而桌面有活动任务 |
| CLI 使用共享 local daemon，且该服务器加载目标线程 | 可以 | 同一 socket 的真实 Codex 引擎隔离验证；未在真实 TUI 交互中触发审批 |
| CLI embedded / 独立 exec / 其他服务器 / 自定义远程 transport | 无已发现的对应只读入口时不可；返回 None | 官方 TUI 有 Embedded/LocalDaemon/Remote 路由，不能仅凭 source=cli 推断可达 |

没有接管 GUI 私有管道、恢复线程、插入中间人、重启 daemon 或改真实 Codex 配置。未知状态不会被当成“没等审批”。

## 本地文件调查

- state_5.sqlite.threads 的本机 schema 没有运行时审批状态字段；approval_mode 是策略，不是当前正在等待。
- thread_history_1.sqlite.thread_turns.status 的本机取值包括 inProgress/completed/failed/interrupted；审批期间仍为 inProgress，不能区分正常工作和等待批准。
- 隔离命令审批前有 function_call，文件审批前有 custom_tool_call，权限审批前有 function_call，但没有持久化的“审批未解决”状态。调用本身不证明手动审批：可能自动接受、被策略拒绝或已回答。
- 官方 rollout policy 把 ExecApprovalRequest、ApplyPatchApprovalRequest、RequestPermissions 等列为 transient/non-durable；实测一致。不能看到 require_escalated 就提醒。
- 日志 SQLite 的反馈正文可能含用户文本/工具内容及 approval 单词，不能用关键词搜索冒充结构化状态。实现不读取这些正文。

## 返回接口

usage.py 的每一项 active_tasks 都新增顶层字段：

```python
task['awaiting_approval']  # True | False | None
```

- True：同一服务器、同一线程的 status 为 active，且 activeFlags 含 waitingOnApproval。
- False：明确的已加载 idle，或 active 的已知标志不含 waitingOnApproval。单独 waitingOnUserInput 是问答等待，不属于本次批准范围。
- None：未加载在所连接服务器、无 socket/程序、连接失败/超时、RPC 错误、未知结构/标志、线程 ID 不匹配。

codex_approval.CodexApprovalReader(home).read(thread_ids) 批量返回 {thread_id: bool_or_none}。无跨轮缓存；连接/批量读取失败时整批回到 None，不保留旧 True。其他线程不能借用状态。

其他任务字段、活动任务成员判定、归档/子代理过滤、working_context、范围选择与数字计算不变。既有五分钟 freshness 窗口仍存在：很长的无日志等待可能先离开 active_tasks；本次按要求不改变成员语义。

Claude 通知中心仅在字段 is True 时产生批准提醒；False 可以清除等待；None 表示无法观测，不表示审批已获准。当前不可连接的 GUI 路径仍需 Codex 宿主提供可观察 transport，或由已连接宿主提供实时状态。界面把 None 转成 False 不能解决这个限制。本分支不改共享文件。

## 只读连接与边界

发现路径：<CODEX_HOME>/app-server-control/app-server-control.sock。不扫描无关目录，不创建常驻服务冒充任务所属服务器。

1. 使用已有 codex app-server proxy --sock <path>。它只转发原始字节，**不是 JSONL 桥**。
2. 实际传输是 WebSocket over Unix socket。标准库处理 Upgrade、nonce 校验、masking、分片、ping/pong；header 限制 8 KB、消息限制 1 MiB、队列有容量限制。Python Windows 无 AF_UNIX，由原生 Codex proxy 负责 socket/DACL 检查，不增依赖。
3. 只调用 initialize → initialized → thread/loaded/list → thread/read(includeTurns=False)。只保留状态，不输出/保存正文、命令、审批原因或凭据。
4. 不调用 thread/start/resume、订阅、turn/start/interrupt、审批回答或配置写入。收到服务器请求也不回答，没有成为线程 subscriber。
5. 仅关闭自己的 proxy，不关服务器。默认整批响应预算 750 ms，加进程启动/清理开销；缺少 socket 直接返回 None。环境使用当前 store 的 CODEX_HOME。

初次探针直接发送 JSON 行没有响应，原因是缺少 WebSocket 握手。修正后本机现有 daemon 的 initialize/loaded/list 成功；其 0 个已加载线程不会被误解成桌面任务都没有等待。

## 实测与延迟

临时 CODEX_HOME、空白 cwd、127.0.0.1 合成 Responses 服务，模型名称 gpt-6.1-sol；未调用真实模型/凭据，未使用 Astra。注入命令执行、apply_patch、request_permissions 三种请求。权限工具仅在实验配置里设置 features.request_permissions_tool=true。首次误写 request_permissions 导致 unsupported call，修正后重新验证；失败实验不计入成功结果。

npm CLI 0.160.0 与桌面内置 0.160.0 各产生三种实际待批请求；每个请求独立只读查询 3 次，全部 True；处理前 False，处理后 False。命令/文件请求取消，权限返回空权限；未执行待批命令或写测试文件。

| 请求 | 实际 RPC 方法 | CLI 查询中位数 [范围] ms | 桌面内置引擎中位数 [范围] ms |
|---|---|---:|---:|
| 命令 | item/commandExecution/requestApproval | 69.25 [68.22–71.03] | 77.58 [72.71–85.33] |
| 文件 | item/fileChange/requestApproval | 78.35 [76.52–88.39] | 75.35 [75.13–83.75] |
| 权限 | item/permissions/requestApproval | 76.30 [75.27–87.26] | 74.76 [73.70–78.51] |

时间是审批已经存在后，启动独立 proxy、握手、查询、清理的总耗时，不是模型计算或 UI 显示时间。实际提醒延迟约为“到下一次 CodexStore.read 的轮询间隔 + 70–90 ms”，小样本不保证负载下上限。

额外实测：两套引擎审批未处理时，实际调用 CodexStore.read，active_tasks 中目标线程 awaiting_approval=True；不是 mock store。引擎验证不等于当前 GUI 私有 stdio 已接入。

脱敏摘要保留在以下临时 evidence.json（本报告保存稳定结论，无需依赖临时文件交付）：

- 命令/文件：C:\Users\fengz\AppData\Local\Temp\pa-celsacxm\evidence.json
- 权限修正后：C:\Users\fengz\AppData\Local\Temp\pa-0yzcy80f\evidence.json
- store 真实字段：C:\Users\fengz\AppData\Local\Temp\pa-w5qj_o0v\evidence.json

## 合成回归

测试不依赖本机 Codex 安装、真实 socket、账户或数据；使用合成状态/帧/进程/连接替身及临时 SQLite/rollout fixtures。

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_codex_approval tests.test_usage tests.test_scopes tests.test_activity tests.test_providers tests.test_provider_poller tests.test_provider_selection tests.test_task_projection_closeout -q
```

**215/215 PASS（3.648 s），其中新增审批测试 20/20。** 覆盖 True/False/None、未知结构、未加载/错线程、断线清除、缺少/无权访问 socket、不启动 daemon、只读方法、masking/分片/ping/超大帧/截止时间，以及 desktop/VSCode/CLI/exec 新字段与原数字/元数据一致。未运行完整 UI 套件，不声称全项目测试全部通过。

## 交接

仅修改 usage.py（5 行添加）、codex_approval.py、tests/test_codex_approval.py、本报告。无依赖、UI/Claude/.autopilot 改动。不合并、不推送。

上轮美术未提交说明独立保存在 codex/v1.6 的 Git stash，没有带入本分支或覆盖美术资源。当前审批任务完成；等待用户安排。普遍覆盖桌面 stdio / embedded CLI 的观察入口仍是明确限制。

## 依据

- [官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)：runtime status、waitingOnApproval 与审批语义。
- [官方 rollout policy](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/policy.rs)：审批事件非持久化。
- [官方控制 socket](https://github.com/openai/codex/blob/main/codex-rs/app-server-transport/src/transport/unix_socket.rs)：WebSocket 握手；没有复制源代码。
- [官方线程状态](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/thread_status.rs)：未解决批准/权限请求生成标志。
- [官方 TUI 连接](https://github.com/openai/codex/blob/main/codex-rs/tui/src/app_server_connection.rs)：Embedded 与 LocalDaemon 路由区别。

官方 main 可能较新；结论以本机 0.160.0/0.160.1、真实 schema/进程及隔离实验为准。
