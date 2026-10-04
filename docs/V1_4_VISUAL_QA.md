# Historical V1.4 working-name visual QA

**Historical development guide.** The user accepted this candidate on
2026-10-04 and authorized its release as **v1.3.0**. See the current
[V1.3 visual QA guide](V1_3_VISUAL_QA.md); V1.4 is not a separate release.
The previous V1.3 package is preserved separately. This version addresses the
reported centering, resize, visibility and front-plane occlusion defects, adds
task-detail transitions and paging, and strengthens the reference-inspired
celestial effects. Technical evidence belongs to the accompanying engineering
reports; a passing test is not human aesthetic acceptance.

## Open the isolated preview

Extract the development ZIP into its own folder and run **preview-v1.4.cmd**
beside petoken.exe. The preview uses temporary settings and conspicuous synthetic
Codex tasks. It starts no live provider, keyboard or activity monitor and never
replaces the stable installation. Exit using **Exit preview**.

```powershell
.\petoken.exe --preview-v1-4 --count 24 --language zh_CN --pose music
```

Source equivalent: `python tools/preview_v1_3.py --count 24 --language zh_CN`.
The old --preview-v1-3 entry remains compatible; current preview title is V1.4.

## Walkthrough

1. **Appearance:** compare 1/3/8 tasks on light and dark desktops. Inspect the
   luminous pearl/violet hoop, champagne inlay, dotted outer arc, crystal beads,
   faceted Stars, suspended factual numbers and longer tapered ribbons. The
   supplied illustration guides the composition; approved pet art is unchanged.
2. **Centered composition:** drag to every side/corner, then use the position
   selector. The whole composition stops at its safe boundary; the pet must
   stay centered in the ring. It can therefore stop slightly inside the edge.
   Rear arcs naturally pass behind the pet; front arcs and front Stars must
   stay in front after clicking the pet or toggling topmost.
3. **Size:** open real Settings and move Character Size through50/100/150%.
   The ring must resize/reposition immediately, without adding tasks. Cancel
   restores the saved size. Repeat with MotionOFF and at screen corners.
4. **Visibility:** show/hide/click the Hub/Usage Panel, open Settings/Analytics,
   change pages and set source unavailable/0tasks. The decorative ring remains
   enabled; unavailable/empty sources honestly show0Stars. Explicit **Show star
   ring and task Stars** in Settings or **Show Ring** in QA is the disable control.
   Disabling survives a task refresh; exiting closes every visual window.
5. **Detail motion:** click a Star, then collapse or click it again. Inspect a
   short smooth Star-origin unfold/fade and reverse close. Rapidly reverse or
   switch tasks, resize/drag, retire the task and exit during a transition: no
   stale card, opaque ghost or stranded animation. Return/Space opens focused
   keyboard detail; Escape collapses. MotionOFF opens/closes immediately.
6. **More than8:** try9/16/24/64 tasks. At most8Stars occupy a ring page. Use the
   adjacent arrows/page selector; every task retains its factual lifetime number.
   The Hub task menu and QA Detail task number can open an off-page task directly.
   Overview count reflects all accepted tasks; retire/change source while on
   the final page and while detail is open. No task metric merges or hidden overflow.
7. **Original poses:** select idle, typing, working, microphone and music.
   These are distinct approved images; typing includes two tap frames. Usage
   is an idle alias, not a sixth new image. QA is synthetic: it proves artwork
   rendering, not detection of an actual microphone/playing app/key press.
   Normal activity retains timestamp-only keyboard pulses, capture-session
   activity and verified media playback; no audio/key text is recorded.
8. **Native desktop:** check topmostON/OFF, another editor remaining visible and
   focused, pointer holds/releases, MotionON/OFF, fractional DPI and real monitor
   crossings. Inspect actual windows, not just exported composition screenshots.

## Capture and limits

```powershell
.\petoken.exe --preview-v1-4 --count 24 --expand 24 --pose microphone --anchor bottom-right --smoke 2 --output C:\QA\v14.png
```

PNG/JSON exports contain only this application's owned Qt windows, with native
window opacity and transition layers respected. They never copy desktop content.
Tasks≤64 are available in the QA fixture selector; production task identity is
not truncated to64. Safe ring hit containment requires enough logical workarea
for the pet and8fixed-size targets together. Physically impossible tiny workareas
retain a centered decoration but cannot provide that containment guarantee.
Human approval of appearance, perceived motion, DPI and monitor behavior remains
required; release/publication needs separate explicit authorization.
