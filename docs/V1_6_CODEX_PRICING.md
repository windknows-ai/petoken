# V1.6 Codex 价格与问题回答接口调研

查询日期：**2026-10-06（America/Toronto）**。分支：`codex/v1.6-pricing-research`，基于本地 `main` `ec4affb`。

本次仅交付本文档。未修改 pricing.py、usage.py、Codex 配置或其他共享文件，未实现问题接入；不合并、不推送。下文代码块都是供 Claude 接入的建议。原 `codex/v1.6-assistant` 的提交保留在原分支。

## 一、模型价格

### 官方价格表

单位：**美元 / 百万 token**；采用 Standard、短上下文（输入不超过 272,000 token）的文本价格。不是 ChatGPT/Codex 订阅账单，也不含工具、区域处理等附加收费。

| rollout 模型 ID | 用户提供的记录数¹ | Input | Cached input | Cache writes | Output | 官方来源 | 查询日期 |
|---|---:|---:|---:|---:|---:|---|---|
| `gpt-6.1-sol` | 2913 | 2.00 | 0.10 | 2.50 | 10.00 | [价格总表](https://developers.openai.com/api/docs/pricing)、[模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol) | 2026-10-06 |
| `gpt-6-sol` | 2116 | 2.00 | 0.20 | 2.50 | 10.00 | [价格总表](https://developers.openai.com/api/docs/pricing)、[模型页](https://developers.openai.com/api/docs/models/gpt-6-sol) | 2026-10-06 |
| `gpt-6-luna` | 1557 | 0.10 | 0.01 | 0.125 | 0.50 | [价格总表](https://developers.openai.com/api/docs/pricing)、[模型页](https://developers.openai.com/api/docs/models/gpt-6-luna) | 2026-10-06 |
| `gpt-5.5` | 81 | 5.00 | 0.50 | 未列独立价格（官方表为 `-`） | 30.00 | [价格总表](https://developers.openai.com/api/docs/pricing)、[模型页](https://developers.openai.com/api/docs/models/gpt-5.5)、[缓存机制](https://developers.openai.com/api/docs/guides/prompt-caching) | 2026-10-06 |
| `codex-auto-review` | 241 | N/A | N/A | N/A | N/A | [模型目录](https://developers.openai.com/api/docs/models)、[价格总表](https://developers.openai.com/api/docs/pricing)、[Auto-review 用途](https://learn.chatgpt.com/docs/sandboxing/auto-review) | 2026-10-06 |

¹ 记录数来自本次用户说明，不是独立全量统计，更不是计费请求数；rollout 的累计计数、fork 复制与去重规则仍由现有 usage.py 处理。

`codex-auto-review` 的**精确 ID**在本次查阅的官方价格总表/公开模型目录中没有价格。官方 Auto-review 文档说明的是审批审查用途，没有建立此 ID 到某个公开计费模型的映射。不能从名字证明其内部实现，也不能借用 GPT-6 Sol、Astra 或其他审查模型的价格；应继续返回 None / N/A。没有价格不等于免费。

### MODEL_PRICES 四列的真实含义

当前 pricing.py:19 的顺序已经明确为：

```python
# USD / million tokens
(uncached_input, cached_input, cache_writes, output)
```

第三列是**缓存写入单价**，不是 reasoning、总价或未知备用列。当前 estimate_usd() 的分类为：

```text
plain = max(0, input_tokens - cached_input_tokens - cache_write_input_tokens)
USD = (plain * input_rate
       + cached_input_tokens * cached_rate
       + cache_write_input_tokens * write_rate
       + output_tokens * output_rate) / 1,000,000
```

reasoning 已包含在 output_tokens，不应重复收费；计数缺失不能补成一个“已知的 0”。现有估算器会把缺失 cache_write_input_tokens 按 0 计算，同时 usage.py 附加 `note_cache_write_unavailable`，所以即使补全价格，也不能把这类记录宣称为完整准确账单。

### Claude 可直接增加的三条价格

```python
MODEL_PRICES.update({
    'gpt-6.1-sol': (2.00, 0.10, 2.50, 10.00),
    'gpt-6-sol':   (2.00, 0.20, 2.50, 10.00),
    'gpt-6-luna':  (0.10, 0.01, 0.125, 0.50),
})
```

这里三条都是四个官方已知单价；本次只在隔离 Python 进程内临时替换字典验证，没有写入源码。

### GPT-5.5 需要处理三分类计费，不能猜第三列

官方缓存文档区分 GPT-5.6 及之后的显式缓存写入计费，与之前模型的缓存机制；GPT-5.5 公开价格只有 input / cached input / output。不要套用 1.25 倍推导出 6.25 美元，也不要把 `-` 翻译成官方公布的 0 美元。

建议扩展表格以容纳“此模型没有独立 cache-write 费率”后，再加入：

```python
# 需要 estimate_usd() 同步支持；当前实现不能直接粘贴这一条！
'gpt-5.5': (5.00, 0.50, None, 30.00),
```

Claude 接入要求：

- `write_rate is None` 时按该模型明确的三分类策略计算，不对 None 乘法；本次证实现有函数连 `0 * None` 都会 TypeError。
- 只有明确的 GPT-5.5 计数结构可以走三分类。若数据包含正数 `cache_write_input_tokens`，其语义与官方旧缓存机制不一致，应返回 N/A / partial，不能把它当免费写入或猜价。
- 若 cache-write 计数缺失，要区分“已识别的 GPT-5.5 官方旧结构不含独立写入分类”和“未知/残缺结构”。前者采用 `(input_tokens - cached_input_tokens) * 5 + cached_input_tokens * .5 + output_tokens * 30`；后者继续不可用。可以使用明确的按模型缓存机制策略，不能对所有模型统一忽略该字段。
- 在此保护逻辑与回归测试实现之前，GPT-5.5 继续 N/A；先加上面三条已知价格即可解决主要缺失。
- `codex-auto-review` 不增加条目、不映射成 0 或其他模型。

### 长上下文与服务档位

对上述三个 GPT-6 模型，官方长上下文价格分别是：`gpt-6.1-sol=(4,.20,5,15)`、`gpt-6-sol=(4,.40,5,15)`、`gpt-6-luna=(.20,.02,.25,.75)`。当前函数的 input/cache/write ×2、output ×1.5 与这些表行一致；Fast ×2、Batch/Flex ×0.5 也一致。[官方价格总表](https://developers.openai.com/api/docs/pricing)

GPT-5.5 Standard 长上下文是 input 10、cached 1、output 45。其 Fast 短上下文是 12.5 / 1.25 / 75（×2.5），官方 Fast 长上下文表为不可用；不能直接沿用当前通用 Fast ×2。模型页还将长上下文规则描述为整段 session，当前按 last request 判断的估算不证明能完整重建这一范围。建议 Claude 将 GPT-5.5 的服务档位和上下文策略一并显式处理；未知档位、区域处理或无法重建请求边界时注明估算/partial。[GPT-5.5 模型页](https://developers.openai.com/api/docs/models/gpt-5.5)、[价格总表](https://developers.openai.com/api/docs/pricing)

### 模型名规范化检查及映射建议

检查 usage.py 的 `SessionUsage.consume()` 和 `add_record()`：turn_context.model 的字符串原样保存，并原样传给 estimate_usd()；pricing.py 用 MODEL_PRICES.get(model) **精确匹配**。当前没有把 `-sol/-luna/-astra` 去掉。`value.strip()` 仅用于判空，没有将清理结果赋给 model。effort / reasoning_effort 单独读取，不应从模型名里推断。

建议只增加可溯源的精确条目/白名单别名，保留原始 model 作为显示与审计信息：

| 输入名 | 推荐计费键/行为 | 原因 |
|---|---|---|
| `gpt-6.1-sol`、`gpt-6-sol`、`gpt-6-luna`、`gpt-6-astra` | 各自精确 ID | 独立模型；6.1 Sol 与 6 Sol 的缓存价也不同 |
| `gpt-5.5-2026-04-23` | 白名单映射到 `gpt-5.5`，随三分类策略接入 | [模型页](https://developers.openai.com/api/docs/models/gpt-5.5)明确列出的 snapshot |
| `gpt-5.6` | 可选精确映射到 `gpt-5.6-sol` | [官方模型指南](https://developers.openai.com/api/docs/guides/latest-model)明确说明该别名；本机记录未要求新增它 |
| `gpt-6`、未知日期、未知 `-high/-fast/-sol/-luna/-astra` 组合、`codex-auto-review` | 无官方对应关系时 None / N/A | 不按相似名字、后缀或同代号借价 |

可选仅对计费键做空白清理，不改历史显示字段；不要任意大小写转换或自动去除后缀建立未证实的别名。Codex Desktop/CLI 用相同的精确 ID 时价格相同；不同 UI、reasoning effort 不改变基础 token 单价，Fast 等服务档位按官方规则另处理。

## 二、Petoken 能否回答 Codex 的问题

### 结论

**协议可行，任意现有任务的无配置接入尚不可行。** 已连接任务所属 app-server、收到其 server request 的客户端可以发送结构化答案/审批决定。只有 rollout 或只读 thread/read 状态，不足以得到可回答的问题对象。本机现有共享 control socket 的 loaded/list=0，当前桌面任务未因此获得外部回答入口。

另一个有条件方案是官方 **PermissionRequest hook**，适合命令/文件审批；它不等于 request_user_input 的问题回答接口。本文没有安装 hook、改变 transport、恢复线程或回答用户的真实任务。

### 本地证据与入口

| 来源 | 能确定什么 | 不能确定什么 |
|---|---|---|
| state_*.sqlite.threads | thread ID、来源、rollout 路径等持久化元数据；本机无 status/wait/pending 字段 | 当前是否等待、具体问题、可回复的 RPC ID |
| rollout response_item.function_call | 历史工具调用名及可能的参数/答案，可用于历史显示 | 工具调用可能被模式拒绝、已取消、已超时或已回答；缺少 output 不证明仍等待 |
| 明确 EventMsg | 上游 rollout policy 把 RequestUserInput、ExecApprovalRequest、ApplyPatchApprovalRequest、RequestPermissions 列为不持久化 | 不能依靠这些实时事件在日志里总是出现 |
| 同一现有 app-server 的 thread/read / status changed | `activeFlags` 的 waitingOnUserInput / waitingOnApproval 是明确运行时标志 | 只有标志，没有问题文本、选项、request ID；notLoaded 不能当成未等待 |
| 任务所属连接上的 server request | 完整问题/选项、RPC ID、threadId、turnId、itemId；具备回答所需上下文 | 其他服务器或其他任务不会因为共用 CODEX_HOME 就自动可见 |

上述非持久化与状态推导依据官方源码：[rollout policy](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/rollout/src/policy.rs)、[runtime flags](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/app-server/src/thread_status.rs)。这是固定的上游快照，不宣称等于本机二进制全部实现。

本次只读抽样：各 source 最新未归档 rollout，实际有 vscode、cli、exec 三份，约 227.66、0.23、0.25 MiB；没有 desktop 来源样本。vscode 那份包含 4 条 request_user_input_async 历史调用，三份均未找到上述明确审批/问题 EventMsg；这只是抽样结果，不能推出全量没有事件。UI 来源标签不等于 transport；桌面会话也可能记为 vscode。

### 桌面版、CLI、VS Code 的区别

| 场景 | 检测 / 回答能力 | 接入要求或限制 |
|---|---|---|
| 桌面 GUI 私有 stdio app-server | rollout 只能看历史；外部程序无法直接订阅现有私有管道并回答 | 本机发现桌面内置二进制 app-server，无显式 --listen；按协议默认 stdio。不能接管它的 stdin/stdout；新起一个服务器也不是原任务的 pending request |
| CLI Embedded / 独立进程 | 没有已发现远程 endpoint 时同上 | 官方 TUI 明确拒绝给 Embedded 建远程连接 |
| CLI LocalDaemon / Remote，或 GUI/IDE 实际使用可达的共享服务器 | 可只读查 flags；收到该线程 server requests 后可回答 | 必须匹配原服务器、线程及连接的订阅路由；不能从 source=cli/vscode 推定可达 |
| VS Code 扩展 | 使用 app-server 协议时回答格式相同；私有连接不自动向 Petoken 暴露 | 本次没有在 VS Code 中触发真实问题/审批，也没有建立该扩展的控制入口；不能承诺覆盖 |
| Petoken 将来显式托管的任务/连接 | 协议上可以显示问题并回传答案 | 需单独实现持续连接和任务生命周期；不是本次已完成能力 |

本机实测：CLI 与桌面内置引擎均 `0.160.0`；现有 daemon 为 `0.160.1`。三者生成的 JSON schema 都有 `item/tool/requestUserInput`、相同的问题/回答字段，以及 waitingOnUserInput / waitingOnApproval。只读初始化共享控制 socket 成功，但 thread/loaded/list 返回空列表；不进一步 thread/resume 去制造可见性。真实 config.toml 探测前后 SHA-256 相同。[协议与默认传输](https://learn.chatgpt.com/docs/app-server)、[TUI Embedded/LocalDaemon 路由](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/tui/src/app_server_connection.rs)

### 收到请求后的回传格式

本机 0.160.0 / 0.160.1 schema 的精确方法名为 **`item/tool/requestUserInput`**。官方文档部分标题/列表简称 tool/requestUserInput，不应据此丢掉 `item/`；以本地生成 schema 和实际 wire method 为准。

```json
{
  "id": 41,
  "method": "item/tool/requestUserInput",
  "params": {
    "threadId": "thread-example",
    "turnId": "turn-example",
    "itemId": "call-example",
    "isBlocking": true,
    "autoResolutionMs": null,
    "questions": [{
      "id": "direction",
      "header": "方向",
      "question": "希望使用哪种布局？",
      "isOther": true,
      "isSecret": false,
      "options": [{"label": "紧凑", "description": "占用较少空间"}]
    }]
  }
}
```

选择选项时填写选项 label，自由输入时填写用户原文；结果按 question.id 映射，**响应的 id 必须是 server request 的 RPC ID**，不是 itemId、threadId 或 question.id：

```json
{"id": 41, "result": {"answers": {"direction": {"answers": ["紧凑"]}}}}
```

这是 JSON-RPC response，不是向 Codex 发送新 method、追加 assistant 文本或 turn/start。本机协议消息可以省略 jsonrpc 字段。Plan 的问题可以阻塞；异步/非阻塞问题不一定暂停工作，必须使用 isBlocking，而不是统一宣称“回答后才继续”。autoResolutionMs 若有值，还要处理到期清除。[官方 App Server](https://learn.chatgpt.com/docs/app-server)、[官方回答示例实现](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/app-server-test-client/src/request_user_input.rs)

审批使用不同 schema，不能伪装成普通问题答案：

- `item/commandExecution/requestApproval` / `item/fileChange/requestApproval`：`result={"decision":"accept"}` 或用户明确选出的 decline/cancel 等；只显示请求允许的决策。
- `item/permissions/requestApproval`：`result={"permissions": <用户批准的请求权限子集>, "scope":"turn"}`，不是 decision 或 answers。
- `serverRequest/resolved` 带 threadId/requestId，表示已回答**或被清除**；不能单凭它证明 Petoken 的答案被采用。[审批协议](https://learn.chatgpt.com/docs/app-server)

普通 assistant 消息里的问句没有统一的 pending-question 结构，不能靠问号或“很久没动”猜状态；turn/steer 或新 turn 的用户消息也不等于回答某个挂起的审批/问题。

### 获取 pending 的关键限制

本机 schema 没有公开的 `questions/pending/list`、`serverRequest/list` 或纯只读 `thread/subscribe` 方法。仅 initialize + thread/read 不会将读取器变成问题接收客户端。

上游实现有内部 pending 请求表，以及给订阅连接重放未解决请求的路径；普通问题/审批的请求可以面向线程的多个连接，先解决者获胜；敏感 user-verification 请求则绑定所有者，不向其他连接重放。参见 [outgoing_message.rs](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/app-server/src/outgoing_message.rs)、[thread_lifecycle.rs](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/app-server/src/request_processors/thread_lifecycle.rs)。

目前可见的订阅入口与 thread/start / thread/resume 生命周期相关。resume 带配置、模型、cwd 等可覆盖字段，也会附加监听和生命周期行为，**不是纯只读查询**。本次没有调用它。不能把内部重放函数当成公开 API，更不能仅拿历史 rollout 中的 call_id 就发一个 response 到随机新连接。

### 建议的 codex_questions 接口（尚未实现）

可以复用 codex_approval.py 的 proxy 定位、WebSocket 握手、限长/限时和错误处理思路；不能照搬每次查询后关闭连接的生命周期，因为问题回答需要保持服务器路由与待决请求上下文。

```python
pending(home) -> list[dict]
# 仅返回已从可达、已订阅连接收到且尚未解决的请求。
# 每项建议：id（不透明句柄）、thread_id、turn_id、item_id、kind、
# questions、is_blocking、auto_resolution_ms、can_answer。

availability(home) -> dict
# status: connected | unreachable | unsupported | unknown
# reason: 无 endpoint、线程不在该服务器、无合法订阅路径、断线等。
# pending=[] 不代表所有桌面/CLI/IDE 任务都没有问题。

answer(home, id, answers) -> bool
# 如保留 bool：True 仅表示校验通过且响应写入了当前有效连接；
# 不等于服务器确认采用答案，False 为不可发送。
# 推荐另给 delivery_state(id): sent | resolved | expired | unknown。
```

实现必须：将句柄绑定 endpoint/连接世代、原 RPC ID 的字符串或整数类型、thread/turn/item；断线清空句柄，不把旧请求发到新服务器；按类型分开 `answer()` 与 `decide_approval()`；处理重复点击、GUI 先回答、超时、turn 中断及自动清除；保护 isSecret，问题与回答不写普通诊断日志。发送后也不能把 resolved 当成“我的答案被采用”的唯一证据，协议通知没有回显胜出的答案。

建议首期：原服务器可达但只有 flags 的任务只显示“需要你查看”，引导回 Codex；私有桌面/IDE 管道没有入口则保持 unknown。只为 Petoken 明确拥有的 app-server 连接，或未来获用户授权且经过验证的订阅入口，启用问题卡片内回答。

### 另一路：官方 PermissionRequest hook

最新官方 [Hooks 文档](https://learn.chatgpt.com/docs/hooks)支持 PermissionRequest，输入包含 session_id、turn_id、tool_name 和 tool_input。命令 hook 可以在用户于 Petoken 作出决定后返回：

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
```

拒绝可用 `behavior="deny"`，附 message；无决定则继续原审批流程。多个 hook 同时决定时 deny 优先。这是 hook 的返回值，不是 app-server 的 approval response。

此方案可在不拥有 GUI 私有管道的情况下增加审批桥：hook 通过本地受控 IPC 向 Petoken 发请求，等待用户决定，再在原 hook 的 stdout 返回结果。需用户安装/信任对应 hook 定义；匹配配置可放 hooks.json 或 config.toml，并保留已有 hook。没有必要抢占单程序 notify 槽。失败/超时应不批准并回落原提示；先验证与当前审批策略、Auto-review、多 hook 的交互，不能承诺所有权限类型与各宿主版本都已覆盖。

官方没有给出通过 PermissionRequest hook 回传 request_user_input 的 question answers 的约定。该 hook 在审批路径运行，普通问题不是审批；UserPromptSubmit 是用户提交新输入的 hook，也不是回答现有 RPC 的入口。本机二进制生成 schema 不证明 hook 在三个宿主的完整行为；本次**未安装、未触发或端到端验证 hook**。可作为 Claude 的命令/文件审批独立实现候选，一般问题仍采用前面的条件性 app-server 方案。

## 三、已执行验证与交付边界

| 验证 | 结果 / 范围 |
|---|---|
| 官方价格总表和四个精确模型页实际获取 | 四个模型 input/cache/output 已核对，三个 GPT-6 的 write 价也已核对；GPT-5.5 write 和 auto-review 价格不补猜 |
| 文档来源与示例检查 | 17 个引用的官方页面/固定源码均成功获取；公开模型目录未包含精确 codex-auto-review ID；3 个 JSON 示例均可解析 |
| 只读合成价格与模型处理校验 | **43 条断言 PASS**：三套费率与模型页比对；18 个短/长上下文与 standard/fast/flex 计算；9 个必要计数缺失；5 个现有未定价 ID；7 个原样保留模型名/effort；1 个 GPT-5.5 None write-rate 不兼容复现 |
| 现有相关测试 | `python -m unittest tests.test_pricing tests.test_usage tests.test_codex_approval tests.test_codex_events -q`：**88/88 PASS，1.221 秒**。使用 `.venv/Scripts/python.exe`，未新增或改写测试文件 |
| 本机 CLI/Desktop/daemon 的 schema 生成 | 0.160.0、0.160.0、0.160.1 均成功，在临时目录生成后核对 request/response 字段与方法名；未启动新 Codex 任务 |
| 现有 control socket 只读探测 | initialize + initialized + thread/loaded/list 成功，loaded=0；没有 resume、start、回答或批准。仅退出自己创建的 proxy |
| 数据库与 rollout 抽样 | 只读 metadata/schema 和三个最新样本的事件类型/工具名计数；未输出问题、对话、文件内容或凭据 |
| 配置保护 | 控制 socket 探测前后 config.toml SHA-256 相同；未修改真实配置、信任设置或 transport |
| 真实问答/审批 round trip | **本次未执行**；研究限定只读，未向任何现有任务提交答案/审批。不将 schema、源码或既往审批测试充当新接口端到端验收 |

临时只读探测代码通过终端 stdin 执行，未加入仓库；不留正式功能或共享文件改动。一次探测引用 assistant 分支独有的 recap helper 时失败，已改为直接只读 SQLite 后成功；一次上游源码旧路径 404，已从固定快照目录定位新路径，最终结论使用成功获取的资料。

交给 Claude 的最小实施顺序：

1. pricing.py 增加三个 GPT-6 精确条目；保持未定价模型 N/A，不改现有 token 去重/累计语义。
2. 增加 GPT-5.5 三分类保护、官方 snapshot 白名单与独立 Fast/上下文规则及回归，然后启用该模型估算。
3. 通知先使用明确 runtime flags + 回到原窗口；别把私有连接任务显示为“无问题”。
4. 后续分别验证受信任的 PermissionRequest 审批桥、可合法订阅的 app-server 问题桥；测试竞争回答、断线、超时、取消和三种宿主后再开放卡片内回答。

推荐依据仅为本次实际获取的官方页面、固定官方源码与上述只读验证。没有复用第三方代码、新增依赖或更改生产逻辑。
