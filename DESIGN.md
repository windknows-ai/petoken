# petoken design contract

The approved idle character and its default bubble are the immutable visual baseline. `assets/skirk-pet.png` must retain SHA-256 `7ce0d2fbd0eb89d2f6786c9bb1d5bada1aff7d89ea2f5dd079cce8a26483e1a0`. New behavior changes pose temporarily; it does not replace, repaint or permanently cover the idle identity.

## Visual language

- Silver `#EEF2FF`, ice `#91E4F2`, violet `#B9A7F8`, midnight `#171B32`, muted ink `#A7AEC8`, rose `#F3A7CB`.
- Native Qt controls, Segoe UI labels, Cascadia Mono numbers and Microsoft YaHei UI fallback.
- Transparent 242 × 378 logical-pixel pet window; small rounded status bubble above the character.
- The separate 360-pixel panel uses restrained glow, compact hierarchy and scrolls on shorter screens. The detailed analytics window owns dense tables.
- All windows scale with Windows DPI and clamp restored positions to a visible screen.

## Supported states

Only these states exist in this version:

1. `usage`: while the adjacent usage panel is actively hovered/opened.
2. `microphone`: an active Windows capture session.
3. `music`: an active Windows system-media playback session.
4. `typing`: recent non-modifier keyboard activity.
5. `idle`: the approved default.

The order above is the state priority. Microphone/music require a stable signal before entry and delay exit; typing expires shortly after the last key. Missing/stale platform signals never pin the pet in an activity state. No input text, audio stream, media title or extra pet state is collected.

## Usage reveal

- Hover the pet for roughly 0.35 seconds or click it to open the panel next to the pet.
- Leaving both pet and panel for roughly 0.7 seconds hides the panel and restores the correct underlying activity pose.
- The transparent pet does not activate itself when shown, so it does not steal typing focus.
- Open settings/details keep the panel available. Closing it suppresses immediate hover reopen until the pointer leaves.

## Usage panel contract

- Follow the current accessible Codex task title. Never select from the stale initial-route URL. If inaccessible or ambiguous, show the recent-task fallback label; allow explicit pinning.
- Tokens/cost can use task or project scope. Model, reasoning, context and raw latest snapshot describe the selected task. Quotas describe the account.
- Poll once per second with at most one quota RPC in flight. Numeric usage changes when Codex writes events, not through an invented counter.
- Preserve all reliable raw token fields. Unknown values display as N/A; cached input and reasoning output are never added twice.
- Read numeric local metadata only. Never export transcripts or credentials, send model requests, save key content, or record audio.

## Accessibility and controls

- Native menus, tooltips, focus and buttons remain keyboard usable.
- Drag either window; `Alt+Arrow` moves the panel. Always-on-top, collapse, tray restore, motion pause and explicit exit remain available.
- Tooltip text states raw sources, formulas, comparison-only metrics, stale quota samples and cost limitations.
