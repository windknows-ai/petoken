# V1.5 Codex + Claude Code — visual QA

V1.5 tracks exactly two providers: Codex and Claude Code. This checklist has two parts:
an isolated preview that never touches your data, and an optional real-data check.

## 1. Isolated preview (safe, recommended first)

Double-click `preview-v1.5.cmd` beside the development `petoken.exe`. Every value is
synthetic; nothing is read from Codex or Claude Code and no setting is saved.

- [ ] Stars of Codex tasks are **blue**, stars of Claude Code tasks are **gold**.
- [ ] Switching **Source** to `codex` leaves only blue stars; `claude` only gold; `mixed` both.
- [ ] Choosing a Claude task from the Hub task menu shows `Claude Code · …` at the top of the Hub.
- [ ] Star tooltips, the star detail, the Hub task menu and the workbench name each task after its
      **project** (two tasks in one project read `项目 · 1`, `项目 · 2`), matching the Hub title.
- [ ] While tasks run, a usage card sits above the character's head (it replaces the old bubble):
      one block per open app with **上下文 / 5 小时 / 1 周**, each showing what is left and when it resets.
      Source `codex` shows only Codex, `claude` only Claude Code, `mixed` both.
- [ ] Context bars go from white (little used) to deep blue (nearly full); 5 小时 is pale blue-white;
      1 周 is deep indigo like the clothing.
- [ ] Codex plan `pro`: the card has no 5 小时 row and the Hub's 5-hour limit reads `N/A`;
      `plus` shows both.
- [ ] Claude usage sync `off`: the Claude block says to turn on 同步 Claude 用量 in Settings,
      and a Claude task's Hub limits read `N/A` with the same hint at the bottom.
- [ ] Clicks pass through the usage card to the character and desktop.
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
- [ ] With only Codex open the usage card shows only Codex; with only Claude (desktop or CLI)
      only Claude; with both, both.
- [ ] Settings → **同步 Claude 用量** turns the Claude limits on (Pro/Max). After the next Claude Code
      reply in a terminal session, the Claude block shows 5 小时 / 1 周 with reset times.
      Turning it off and saving removes Petoken's line from Claude Code's settings.

Report anything that looks wrong with a screenshot; no technical detail is needed.
