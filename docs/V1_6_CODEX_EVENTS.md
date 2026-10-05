# V1.6 Codex 事件接口验证

完成日期：2026-10-05（America/Toronto）。基线：已发布 main `98de5eb`；分支 `codex/v1.6`。

**结论：事件接口确实可用，但不是一个覆盖所有进程的自动广播。V1.6 推荐“原有轮询保底 + 可选 notify 完成提示”；app-server 仅在能连接任务所属服务器并取得线程订阅时补充五类事件。不要另启动服务器就宣称观察到了桌面/CLI 的全部任务。**

本次不改真实 config.toml，不安装回调，不调用真实 computer-use 程序，不启动/恢复真实用户线程，不改 usage.py、UI、通知中心或资源接入代码。

## 1. 实测方法与版本

- npm CLI：`codex-cli 0.160.0`。
- 桌面程序内置 Codex：`codex-cli 0.160.0`。
- 本机运行的共享 daemon 程序：`codex-cli 0.160.1`；另外以其程序单独启动隔离 app-server 验证，未连接/重启真实 daemon。
- 从三套程序生成/检查对应 JSON Schema；核心事件方法一致。网页文档和本地版本存在字段差异，原型只接受本次实际方法/状态。
- 每次使用独立 CODEX_HOME 和空白临时 cwd；不复制 auth.json、不读取真实会话/SQLite。模型名称固定 gpt-6.1-sol，所有 Responses 请求指向临时 127.0.0.1 HTTP 服务，**没有调用真实模型，也没有使用 Astra**。
- 本机服务注入：正常结束、不可重试 HTTP 400、请求审批的 exec_command 调用及额度响应头。审批只取消，不批准；命令没有执行。
- CLI 程序和桌面内置程序各运行 9 回合：成功、失败、审批各 3 次。0.160.1 程序另运行这三种场景各 1 次。
- 实际 `codex exec --json` 再运行成功/失败各 3 次，验证 CLI 入口的 notify 和 JSONL 输出。
- 两个 WebSocket 客户端连接同一个隔离 app-server，验证 observer 在 thread/read 前后、thread/resume 订阅前后的收到范围。

### 测量定义

所有时间用同一机器 `perf_counter_ns`。开始事件以 turn/start 发送为起点；完成、失败、审批以本机服务发送对应响应为起点；额度以发送额度响应头为起点；notify 以响应结束到原型开始写入提示为区间。它们是**本机接口链路实测**，不是实际模型计算时间，也不是 Windows 通知/桌宠动画显示时间。开始时间包含服务接受请求开销，其余事件包含解析、状态落盘等处理；notify 另包含 Python 进程启动。小样本不能保证所有负载下的延迟上限。

## 2. notify 回调

官方支持的回调事件是 `agent-turn-complete`，一个 JSON 字符串作为最后一个 argv 参数。TUI 的 approval-requested 提示不是这个回调。

| 事件 | 实际 CLI exec | 桌面内置 app-server 隔离验证 | 判断 |
|---|---|---|---|
| 开始 | 没有回调 | 没有回调 | notify 不能提供 |
| 完成 | 3/3；178.39–191.82 ms，中位 181.71 ms | 3/3；211.62–303.09 ms，中位 212.53 ms | 可作为及时提示 |
| 失败 | 0/3；exec 退出 1 并输出 turn.failed | 0/3 | 不能当失败通知接口 |
| 等待确认 | exec 无交互审批，不适合验证等待 | 0/3；app-server 收到审批请求时没有 notify | 不支持 |
| 额度变化 | 正常回调不含额度事件 | 正常回调不含额度事件 | 不支持 |

CLI 程序的 app-server notify 另为 3/3，中位 241.59 ms（230.11–243.37 ms）；0.160.1 的隔离成功样本为 194.59 ms。

**桌面 GUI 说明：**测试对象是桌面安装目录内的实际 Codex 程序，在临时配置下启动 app-server；没有重启当前 GUI 去检查它加载改动配置的时机。因此证明的是桌面内置引擎的接口能力，不能据此说已部署到真实桌面 GUI。真实 GUI/TUI 的启用仍需 Claude 集成后验收。

### 转发器原型和配置/还原

`codex_events.py` 是独立实验原型，不被 Petoken import：

1. JSON 只用于提取 kind/thread_id/turn_id；Petoken 提示不包含 cwd、用户输入、助手回复。
2. 先写内容无关的提示，再用 `subprocess.run([...原 argv, 原 JSON 字符串], shell=False)` 调用原程序。
3. 不重编码原 JSON、不拼 shell、不更改原参数顺序，保留原程序退出码；未知/畸形事件、提示写入失败也照常转发。
4. notify 的 kind 是 finished，**不把没有结果状态的旧回调猜成成功**。通知消费端应再核对本地状态并按 thread+turn 去重。
5. 实测原程序使用临时 dummy 代替 computer-use，3/3 原回调收到，前缀参数不变；单元测试另验证中文、空格、引号和原始 JSON 字符串完全相同。

未来启用需仅修改用户级 config.toml 的 notify：用 Python/原型 argv 替换该数组，将原数组完整序列化成 --forward-json 参数；不要覆盖 computer-use 的参数。桌面/TUI 需重新加载配置。项目级 .codex/config.toml 不能覆盖 notify。

安全还原：修改前保留 config.toml 原始字节和原 notify 数组，退出/重启相关入口后仅恢复该字段；若中间存在其他配置修改，不整文件覆盖它们。删除新增转发器配置/监听器，不修改原程序。本次只写临时配置，真实配置无需还原。

原型使用本地文件作为实验 sink；这不是正式通知中心。正式接入由 Claude 采用当前用户专属 IPC/队列、短超时、受限文件权限和退避，保证 Petoken 未运行或 sink 不可用时仍能转发。不得将完整回调内容写入 Petoken 日志。

## 3. app-server JSON-RPC

在 initialize → initialized → thread/start → turn/start 后读取双向流。无需修改 Codex config.toml 的 notify，二者可以并行使用。

以下为**已连接且已订阅的隔离服务器**结果；“CLI 程序”列也是 app-server，不等同 TUI 已自动提供订阅。时间为中位数 [最小–最大]，单位 ms。

| 事件及协议 | CLI 程序 0.160.0 | 桌面内置程序 0.160.0 | 重复结果 |
|---|---:|---:|---|
| 开始：turn/started，status=inProgress | 14.09 [12.86–66.25] | 13.72 [11.70–59.98] | 两套各 9/9 |
| 完成：turn/completed，status=completed | 48.46 [45.36–50.83] | 48.36 [47.15–52.88] | 各 3/3 |
| 失败：turn/completed，status=failed | 8.48 [8.36–9.58] | 9.16 [8.95–10.11] | 各 3/3 |
| 等待确认：item/commandExecution/requestApproval | 60.96 [60.88–90.86] | 65.44 [55.78–93.78] | 各 3/3 |
| 额度：account/rateLimits/updated | 72.88 [30.56–145.49] | 74.56 [31.40–151.94] | 各 6/6 |

0.160.1 的补充样本：完成 50.91 ms，失败 9.08 ms，等待确认 84.13 ms；方法/状态语义一致，样本数仅 1，不作稳定性上限保证。

### 语义边界

- 等待用户是带 id 的**服务器请求**，不是普通通知。原型还识别 fileChange、permissions、requestUserInput 和 MCP elicitation 方法；这些额外方法本次仅作合成协议测试，不能宣称均已端到端触发。
- 观察客户端不得替用户接受审批、回答问题或取消真实任务。实验只取消自身生成的假审批。serverRequest/resolved 表示等待解除。
- `turn/completed` 的 interrupted 不是 failed。临时 error/willRetry、单个命令非零退出不等于最终任务失败。
- 额度来自该服务器新接收的服务响应。它不是“账号在别处使用、窗口到期后必然立即广播”的保证；无活动时/跨设备变化仍需额度读取或轮询核对。没有额度数据保留 Unknown，不能补成 0。

### 跨连接观察实测

同一隔离服务器的 owner/observer：

1. observer 的 thread/loaded/list 能看到 owner 的线程。
2. 仅 thread/read 不会获得 turn/started、turn/completed 或额度通知；本次只见 thread/status/changed。它不能提供可靠的成功/失败归因。
3. observer 对该线程 thread/resume 后，下一回合收到 turn/started、item/*、thread/tokenUsage/updated、account/rateLimits/updated、turn/completed。
4. 因此没有现成的“一条 subscribe-all 监听所有桌面、CLI、exec 进程”假设可用。独立 app-server 不共享其他进程的运行时；同目录 SQLite 可见也不代表事件流共享。

未来接入需先发现任务所属服务器和可用 transport，再初始化并订阅对应线程。当前 CLI 提供 app-server proxy/共享 daemon，WebSocket/Unix socket 也有协议支持，但**本次没有连接真实 daemon/control socket，没有验证所有 GUI/TUI/exec 任务均进入同一服务器**。thread/resume 也应由 Claude 核对不会改变既有任务配置/生命周期后再用；不要后台恢复未知线程或代替用户启动新回合。

本次 stdio 仅观察自己启动的实例；WebSocket 仅绑定临时 127.0.0.1。正式方案需认证/当前用户权限，不把控制接口暴露到公网。程序升级后重新核对本地 schema。

安全还原：关闭实验客户端和自建服务器，停止本机 mock HTTP listener；仅删除确认属于本次实验的临时目录。不要执行真实 daemon stop/restart/update，不改真实配置，也无需恢复真实账户或线程。

## 4. 推荐给 Claude 的 V1.6 接入顺序

| 事件 | 能订阅任务所属 app-server 时 | 默认独立 Petoken 的保底 |
|---|---|---|
| 开始 | turn/started | 轮询本地生命周期 |
| 完成 | turn/completed(completed) | 可选 notify finished 提示 + 轮询确认最终状态 |
| 失败 | turn/completed(failed) | 轮询明确的终止/错误证据；缺少证据保持 Unknown |
| 等待确认 | 审批/用户输入服务器请求 | 轮询明确的等待状态；无法识别则 Unknown，不因静默猜测等待 |
| 额度变化 | account/rateLimits/updated | 保留额度读取/轮询，尤其空闲期和跨设备变化 |

1. 第一阶段保留现有读数/范围选择逻辑，用事件唤醒刷新，而非替换全部数据读取。去重键采用 provider/thread/turn/kind；连接中断后进行状态对账。
2. notify 只作为用户明确启用的补充，转发原 computer-use 回调。没有原型安装动作，也没有共享文件改动。
3. app-server 属于能接入同服务器后的增强路径；连接/订阅不可达时明确回落轮询，不报告虚构延迟或虚构任务状态。
4. 原型 API：normalize_event(message, source) → dict 或 None，kind 为 started/completed/failed/interrupted/waiting_for_user/confirmation_resolved/quota_changed/finished；source、thread_id、turn_id 和可选 request_id。只提供事件提示，无费用/用量数字、无 UI。

## 5. 验证和复现

合成测试完全不依赖本机 Codex 数据或安装：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_codex_events -v
```

结果：13/13 PASS。连同 tests.test_usage、tests.test_scopes 共 68/68 PASS；没有改动既有数字解析或 UI。

隔离端到端实验需要显式指定已安装的 Codex 可执行文件和**尚不存在**的新临时目录：

```powershell
$probeOut = Join-Path ([IO.Path]::GetTempPath()) ('petoken-v16-' + [guid]::NewGuid())
.\.venv\Scripts\python.exe codex_events_probe.py --binary '<CLI 或桌面内置 codex.exe>' --out $probeOut --label probe --scenarios success,success,success,failure,failure,failure,approval,approval,approval
```

原型拒绝复用已有实验目录，不复制账户数据。evidence.json 记录回合结果、单调时钟、方法列表和合成服务请求结构；不能作为真实账号使用量。详细原始实验文件保留在本机临时目录 `C:\Users\fengz\AppData\Local\Temp\petoken-v16-probe-f37z8bz_`（cli-final、desktop-final、daemon-final、exec-evidence.json、observer-evidence.json）；文档以上表格保存稳定结论，交付无需依赖临时目录。

曾有一次审批探针超时：最初注入旧 shell 函数名，0.160.0 实际使用 exec_command，因此未产生审批请求；改成实际函数名后两套程序各 3/3 正常。该失败样本没有被算成接口“不支持”，也没有改真实环境来绕过审批。

## 官方参考

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)：初始化、双向 RPC、回合/审批/额度事件、线程读取与恢复。
- [Advanced Configuration / Notifications](https://learn.chatgpt.com/docs/config-file/config-advanced)：notify 与 TUI notifications 的区别、回调 argv。
- [Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)：用户级 notify 与项目级覆盖边界。

网页提供语义参考；上述重复次数/延迟/订阅边界来自本机实测。没有把协议文档中的可用方法当成真实 GUI 已部署证明。
