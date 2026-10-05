# V1.5 Codex + Claude Code — visual QA

V1.5 tracks exactly two providers: Codex and Claude Code. This checklist has two parts:
an isolated preview that never touches your data, and an optional real-data check.

## 1. Isolated preview (safe, recommended first)

Double-click `preview-v1.5.cmd` beside the development `petoken.exe`. Every value is
synthetic; nothing is read from Codex or Claude Code and no setting is saved.

- [ ] Stars of Codex tasks are **blue**, stars of Claude Code tasks are **gold**.
- [ ] Switching **Source** to `codex` leaves only blue stars; `claude` only gold; `mixed` both.
- [ ] Choosing a Claude task from the Hub task menu shows `Claude Code · …` at the top of the Hub.
- [ ] For a Claude task, 5-hour and weekly limits read `N/A`, and the bottom status says
      "此来源不提供额度" / "No limits from this source".
- [ ] Opening a star's detail names the right provider.
- [ ] Workbench (打开工作台) lists Claude tasks with `· Claude Code`, and **Link** puts them in a project.
- [ ] Decorative beads, the dotted guide and trails beside gold stars are gold too.
- [ ] A Claude task shows Context used, cache hit and new work values.
- [ ] Chinese and English both read correctly; nothing overflows.

## 2. Real data (optional)

Running the development `petoken.exe` directly reads your real Codex and Claude Code data and uses
your normal settings file. The first run upgrades the saved provider choice from the forced `codex`
of earlier builds to **Auto** (once); the released v1.3.0 still opens normally afterwards.

- [ ] Settings → Tracking provider shows Auto / Codex / Claude Code (default Auto).
- [ ] While a Claude Code session is running a reply, a gold star appears and the Hub follows it in Auto.
- [ ] When the Claude reply ends, its star retires; Codex tasks keep their blue stars.
- [ ] Choosing Codex (or Claude Code) in Settings hides the other provider's stars and Hub data.
- [ ] If Codex shows `部分兼容` / `Partly compatible` beside its name, hovering explains why;
      the other numbers still display.

Report anything that looks wrong with a screenshot; no technical detail is needed.
