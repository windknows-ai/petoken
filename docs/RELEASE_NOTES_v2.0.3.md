# Petoken v2.0.3

Fixes for text that could be cut off and for Claude's limits, and a new
quick-launch shortcut.

- **Quick launch is now Alt+Shift+Space.** If you still had the old default
  (Ctrl+Alt+Space), it moves over once; choose another shortcut in Settings >
  Assistant and Notifications whenever you like.
- **No more cut-off text.** Wrapped text in every window, card and dialog now
  always gets the height it needs, and a window grows (within the screen)
  instead of cutting lines off. The focus summary card also widens when its
  buttons need it. Every window was checked in Chinese and English.
- **Claude's limits past 100%.** When the 5-hour limit was used up, Claude Code
  reports a little over 100% (for example 101%). Petoken treated that as
  invalid and showed an older number instead (such as 85 left). It now shows 0
  left.

v1.7.0 and later offer this update by themselves (Settings > General >
Updates). Otherwise download `Petoken-Setup-v2.0.3.exe` and verify it against
`SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v2.0.3).

---

# Petoken v2.0.3（中文）

修复文字被截断和 Claude 额度显示的问题，快速派活换了快捷键。

- **快速派活改成 Alt+Shift+空格。** 如果你还在用原来默认的 Ctrl+Alt+空格，会自动换过来一次；之后也可以在 设置 → 助手与通知 里随时换。
- **文字不再被截断。** 所有窗口、卡片和对话框里会换行的文字，现在都会留够高度；放不下时窗口会自己变大（不超出屏幕），不会把字切掉。专注结束卡片在按钮放不下时也会变宽。所有窗口都用中文和英文检查过一遍。
- **Claude 额度超过 100% 时显示正确。** 5 小时额度用完后，Claude Code 报的用量会略超 100%（比如 101%）。以前 Petoken 把它当成无效数据，改用了更早的旧数字（比如显示还剩 85）。现在会正确显示还剩 0。

v1.7.0 及以后的版本会自己提示这次更新（设置 → 常规 → 更新）。也可以在 [GitHub 发布页](https://github.com/windknows-ai/petoken/releases/tag/v2.0.3) 下载 `Petoken-Setup-v2.0.3.exe`，并用 `SHA256SUMS.txt` 核对。
