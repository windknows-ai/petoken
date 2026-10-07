# Petoken v2.0.1

Two fixes after v2.0.0.

- **Background refresh of Claude's limits stays invisible.** While the
  refresh asked Claude its tiny question, Claude Code briefly registered it as
  a session, so the star ring flickered. The refresh now runs in its own
  folder and the task list and notifications skip it.
- **Curious only about new tasks.** She leaned in with curiosity every time an
  AI task went quiet and busy again. Now only a task she has not seen before
  counts, and at most every ten minutes.

v1.7.0 and later offer this update by themselves (Settings > General >
Updates). Otherwise download `Petoken-Setup-v2.0.1.exe` and verify it against
`SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v2.0.1).
Everything in [v2.0.0](RELEASE_NOTES_v2.0.0.md) is unchanged.

---

# Petoken v2.0.1（中文）

v2.0.0 之后的两处修复。

- **后台刷新 Claude 额度不再惊动星环。** 刷新时 Claude Code 会短暂登记一个会话，星环会闪一下。现在刷新在专用文件夹里运行，任务列表和提醒都会跳过它。
- **只对新任务好奇。** 以前 AI 任务每次从空闲变回进行中，她都会好奇一下。现在只有第一次见到的任务才算，而且最多每 10 分钟一次。

v1.7.0 及以后的版本会自己提示这次更新（设置 → 常规 → 更新）。也可以在 [GitHub 发布页](https://github.com/windknows-ai/petoken/releases/tag/v2.0.1) 下载 `Petoken-Setup-v2.0.1.exe`，并用 `SHA256SUMS.txt` 核对。v2.0.0 的其他内容不变。
