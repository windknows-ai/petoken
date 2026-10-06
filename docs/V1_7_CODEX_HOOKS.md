# V1.7 Codex hooks / launch / approval performance

Branch: `codex/v1.7-codex-hooks`, base `52bb0d1` (v1.6.0).
Scope: Codex modules/tests/docs only. No shared code/config/UI changes,
no merge/push. OpenAI Docs research checked 2026-10-06.

## 1. Hooks: 实现与结论

配置可来自用户/项目的 `hooks.json` 或 `config.toml` 中的 `[hooks]`，另有
受管理配置和插件 hooks。多来源合并；项目来源需项目可信，非受管理 hook
还需逐项审核当前定义的 hash。CLI `/hooks` 提供审核入口。

本次只合并 `<CODEX_HOME>/hooks.json`，默认 `~/.codex/hooks.json`。
不修改 TOML、已有 notify、信任记录、项目配置或插件。原 computer-use notify
不需要转发器，因为 hooks 独立于单程序 notify 槽。

支持的生命周期事件：SessionStart、SessionEnd、UserPromptSubmit、Stop、Interrupt、
PreToolUse、PermissionRequest、PostToolUse、PreCompact、PostCompact、SubagentStart、
SubagentStop。**没有 StopFailure；工具非零退出、hook 本身失败和任务失败不能混为一谈。**

| 需求 | 采用的明确证据 | 边界 |
|---|---|---|
| 开始 | UserPromptSubmit + session_id/turn_id | SessionStart 仅表示会话打开/恢复，不当作任务开始 |
| 完成 | Stop | 同一 turn 去重；若其他 Stop hook 继续任务，它只是停下的候选信号，最终状态需校验 |
| 失败 | 同服务器 app-server 的 turn/completed，status=failed；否则现有轮询 | 本次真实合成失败只有 failed 终态，没有 Stop；不添加虚构错误 hook |
| 待批 | PermissionRequest | 只在策略确实要求批准时触发；不是普通 request_user_input 问答 |
| 中断 | Interrupt | 留元数据，但 normalize 不生成 failed/finished 通知 |

### 宿主覆盖与实测

本机 npm CLI 和桌面内置二进制都是 0.160.0，hooks feature 为 stable。
分别用临时 HOME/cwd、localhost 合成 Responses 服务启动其 app-server，引入一轮
成功、明确 HTTP 失败、命令待批、无心跳回落原生审批。

| 路径 | 实测结果 | 请求到文件可见 |
|---|---|---:|
| npm CLI 二进制的隔离 app-server | 开始/Stop/阻塞命令审批有效；拒绝后无原生审批请求；无心跳恢复原生请求 | 1009.90 ms |
| 桌面内置二进制的隔离 app-server | 同上 | 822.23 ms |
| npm `codex exec --json`（非交互） | 成功可见 SessionStart/UserPromptSubmit/Stop；失败无 Stop | 未发生人工审批：引擎明确报告 approval policy Never |
| 桌面 GUI / VS Code 的真实交互宿主 | 使用同一引擎/配置机制是支持依据；未改真实配置或触发用户任务 | **未端到端实测；不能声称已验收** |
| CLI TUI | 官方 `/hooks` 明确支持；本次验证 CLI 引擎和 exec，未操纵用户 TUI | 未实测 TUI UI |

文件可见时间包含 PowerShell 启动和引擎调度，不含 Petoken 下一次 poll。
小样本 0.82–1.01 s 不是延迟上限。先前桌面引擎样本为 0.70–0.72 s；
负载、冷启动与进程调度会改变结果。UserPromptSubmit 异步日志可能晚于终态，
Claude 必须按 turn ID/at 去重，迟到 started 不应复活已结束任务。

首次隔离探针没有文件：app-server 不把 CLI 顶层 trust bypass 自动用于 thread/start。
随后仅在测试 thread/start 的 config 覆盖中设置 bypass_hook_trust=true，验证成功。
产品代码**从不**设置这个字段或 CLI bypass 开关。

最初异步 Stop 在 exec 快速退出时丢失，改成同步 Stop，最长 3 s；正常脚本仅写元数据，
不输出 developer context。其他非审批生命周期预算 3 s，PermissionRequest 预算 50 s。
UserPromptSubmit 保持异步，避免延迟每个输入。

### 可用接口

```python
codex_hooks.state(home=None)   # on | off | partial | unreadable
codex_hooks.enable(home=None) # 同上；写脚本并备份/合并 hooks.json
codex_hooks.disable(home=None)# 同上；备份后仅删自己 handler
codex_hooks.events_path()     # %LOCALAPPDATA%/CodexWisp/codex-events.jsonl
codex_hooks.normalize(record) # 统一通知 dict 或 None
codex_hooks.CodexEventReader().poll() # 自启动以来完整新行，不重播历史
```

state 是**配置安装状态，不是信任状态或实时可运行性**。enable 之后用户仍须在 Codex
审核；定义变更需要重新审核。损坏/未知配置返回 unreadable，不覆盖。
安装命令内含脚本文本 SHA256，脚本更新会改变定义，交由 Codex 重新审核。
已有非 Petoken 脚本不覆盖。
两次 enable 幂等；每次实际配置写入前有唯一备份；关闭保留用户 handler，
包括用户与 Petoken 混在同一 group 中的 handler。保留脚本、日志和备份便于恢复。
卸载后的原文件语义保持不变；需要字节级恢复时可手动使用对应备份，但不要覆盖后续用户修改。

事件记录字段 at/event/kind/session/turn/project，仅 ID/时间/事件类型/项目末级目录。
不写 prompt、assistant message、工具命令、完整 cwd 或凭据；命名 mutex 串行追加。
normalize 输出 kind/provider/task_key/at/project/detail/dedupe/source，provider=codex，
task_key 是**裸 Codex thread ID**。字段集合与 claude_events.normalize 相同。
没有来源的 failed 不被合成；可选 `event='turn/completed', kind='failed'` 仅供
拥有现有连接的 app-server emitter 使用，本模块不创建通知订阅。

### 阻塞审批协议

目录固定为 `%LOCALAPPDATA%/CodexWisp/claude-approvals`，沿用 alive、32 hex ID、
request.json、pid、decision.json 协议。request 顶层包含 provider=codex、
hook_event_name=PermissionRequest、session_id、cwd、真实 tool_name，以及
tool_input.command 或 file_path 和 description。请求中工具参数是用户需要批准的
动作，不进入事件日志；不保存对话。没有 command/file_path 的权限输入保留原生处理，
不为网络/MCP 等未知形状虚构命令。

alive 缺失/超过 10 s/未来时间均不作决定；等待中也检查。最多等 45 s，
空文件、损坏数据、未知选择、I/O 错误、心跳消失或超时，stdout 为空并 exit 0。
脚本仅清理自己请求 ID 的文件。PID 与原子 request 发布和现有读者一致。

Claude 格式决定翻译为 Codex 格式：

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
```

deny 可携带 message。必须剥离 updatedInput/updatedPermissions/interrupt；
这些字段在 Codex 当前 PermissionRequest 不支持。多个 hook 的 deny 优先。
**仅一次允许，不实现“始终允许”或配置规则写入。**

### Claude 接入事项（共享文件尚未改）

1. 设置 opt-in 时调用 enable/disable；说明 state=on 还需 Codex `/hooks` 信任，
   宿主重载配置/新会话后生效，不能静默绕过信任。
2. 读取 CodexEventReader().poll() 并送入通知中心，裸 thread ID 与 usage.active_tasks 一致。
   Stop 是候选；其他 hook 可继续时需终态核验；failed 继续用明确 RPC/轮询。
3. `claude_approval.parse_request` 当前会丢 provider，并为 Bash 等创建 Claude 规则。
   **必须保留 provider=codex、展示 Codex 标签、禁用始终允许，不为 Codex 保存 Claude 规则。**
   保留同一 exchange 格式；“回原应用”对 Codex 写空 decision 文件。
4. 现有 alive 心跳可复用；不要替 Codex 启动另一个与目标任务无关的 daemon。
5. 分发包仅需标准 Windows PowerShell；脚本文本嵌入 codex_hooks.py，运行 enable 时安装，
   不依赖外置 Python。安装路径含引号/百分号用 EncodedCommand 安全传递。
6. 不调用本模块回答计划问题；PermissionRequest 不是 request_user_input 的通用回答接口。

### 验证

`python -m unittest tests.test_codex_hooks tests.test_codex_events -q`：
**33 PASS，6.508 s**（20 hooks + 13 既有 events）。真实 PowerShell 验证允许/拒绝、
Claude-only 字段剥离、空/坏答案、失效/消失心跳、缩短测试截止时间、并发 JSONL、
安装命令的引号/百分号路径；所有测试用合成输入，无真实 Codex 数据依赖。
随后增加超大未知时间值的同一测试断言，最终总回归会再核验。

## 2. 派活与待办对应

```python
argv = codex_launch.launch_command(folder, prompt, external_id='todo-uuid')
```

新增可选 keyword 参数 external_id，旧双参数调用不变。只接受 1–128 字符
ASCII ID（字母/数字/点/下划线/冒号/短横线），不接受正文、换行、NUL、shell
表达式。ID 与需求均作为 JSON/Base64 数据传给 PowerShell，不拼进命令源码。
Codex 的 --cd/--/prompt argv 完全不变，不向需求插入标签。

生成脚本只在 Codex 子进程 ProcessStartInfo.EnvironmentVariables 设置
PETOKEN_TODO_ID，不改父进程/用户/系统环境。未指定 ID 时删除继承的旧值，
防止无关启动误配。优先 Windows Terminal 和安全 argv 行为保持原样。

可信 SessionStart hook 只在 source=startup 时读取此环境 ID，写一条
元数据关联；resume/compact 不重新绑定。用户 hook 信任、宿主环境快照传递
都是前提；缺失就不返回关联，不能保证任意宿主会保留任意环境变量。

Claude 读取方式：

```python
notifications = reader.poll()
bindings = reader.launch_bindings  # 本次 poll，不是累积队列
# [{thread_id, external_id, at, project}, ...]
```

也可 `codex_hooks.launch_binding(raw_record)` 单独转换。SessionStart 不生成
started 通知，避免把打开/恢复会话误当工作。launch_bindings 每次 poll 重置，
Claude 必须在同一次 poll 消费；reader 应在派活前创建并完成初次 poll。
这里只生成命令，没有启动实际派活、保存待办或改共享模型。

没有可信 hook/环境传递时，不声称精确对应。Claude 可在启动前记录
external_id、启动 epoch、规范化完整 folder、SHA256(prompt)，筛选随后出现的
主线程；仅在 folder/时间窗口匹配且能读到首条真实用户输入并核实 hash、
候选唯一时关联。多个同目录任务或无 prompt 证据时必须等待选择。
这是降级建议，本次没有增加 prompt 内容扫描或猜测式匹配。

新增 3 个 launch 测试与 2 个 hooks 测试：ID 参数/注入拒绝、真实 PowerShell
子进程环境隔离与旧值删除、SessionStart 元数据/读者与 resume 排除。
`tests.test_codex_launch tests.test_codex_hooks` **34 PASS，8.877 s**。
随后补充脚本所有权/更新 hash 检查，最终合并回归再次核验。
两套 0.160.0 隔离 app-server 均实际把环境 todo-synthetic 带入启动 hook，
生成的 thread_id 与 thread/start 返回值完全一致；没有把真实任务派给 Codex。

## Current execution state

- Item 1 complete, local commit `d99c0d6`.
- Launch correlation implemented; both isolated engines propagate the explicit ID.
- IN PROGRESS: approval reuse/performance evaluation after item 2.

## Sources

- [Official hooks reference](https://learn.chatgpt.com/docs/hooks).
- [Official app-server reference](https://learn.chatgpt.com/docs/app-server).
- [Official hook command launcher](https://github.com/openai/codex/blob/e32365a2c61a78c8b4f00b15e3559e0391f4eb60/codex-rs/hooks/src/engine/command_runner.rs).

The engine probe uses a temporary CODEX_HOME and a localhost synthetic Responses
service, without account credentials or real model inference. The one-invocation
hook trust bypass is restricted to these freshly generated test hooks. Production
installation never changes trust and requires user review in Codex.
