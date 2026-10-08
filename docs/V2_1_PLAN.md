# Petoken 2.1 / 2.2 plan (agreed 2026-10-08)

## 2.1 Game mode

1. **Detection**: the foreground window is fullscreen (or borderless covering the
   monitor) **and** it is a game: under a Steam / Epic / other launcher library, in
   a built-in list of common games, or in the user's own list. A right-click
   toggle overrides it either way.
2. **Placement while gaming** (user choice): on the game's screen she shrinks into
   a corner and becomes click-through, so she never blocks the game. Exclusive
   fullscreen games cover every window anyway.
3. **Transformation** (from idle, continuous, no fades or transitions):
   rise (xform_rise_1..3) → star ring flies behind her → armor appears piece by
   piece (each piece = the difference between consecutive stage images, revealed
   by light tracing its outline) → weapon → MVP display (~2 s) → effects recede →
   form 2. Length 5–15 s; a 2× speed option. Target 60 fps minimum, 90–120 if the
   machine allows (high-resolution timer). Reverse it when the game ends.
   Art brief: `docs/V2_1_ART_PROMPTS.md` (~40 images, two batches).
4. **In game mode**: the star ring stands behind her with the same number of
   stars; running tasks keep their colours, no tasks shows a violet deep-space
   ring (breathing, uniform rotation; switchable). Task reactions, notices and
   curiosity are silent (still recorded under Notifications). Game-mode poses
   (watch, tense, cheer, victory, defeat, drink, bored).
5. **Usage display above her** (both, default rings): four small rings in a
   column (5 h + week for each app), or a horizontal bar with chosen items
   (limits, CPU, GPU, temperature, VRAM, RAM; FPS later via PresentMon). In game
   mode the user only chooses shown or hidden.
6. **Fixes**: a used-up limit shows in red ("used up"), never amber "out in 0m";
   report totals: the Analysis chart shows its range total, identical to the Data
   board for the same range, and range names say exactly what they cover.

Subagents (user choice): only for self-contained modules with tests (game
detection, hardware stats, the 2.2 push prototype) on Sonnet, and read-only
searches on Haiku. Animation and UI stay in the main session.

## 2.2 Phone notifications (ntfy)

Phase 1: push finished / failed / needs approval / limit notices to a private
random ntfy topic (iOS and Android apps, no account; self-hostable).
Phase 2: approve or deny Claude Code requests from the phone through ntfy action
buttons, with a one-time code so only the user's phone can answer.
