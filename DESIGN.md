# petoken design contract

The approved idle character and its default bubble are the immutable visual baseline. `assets/skirk-pet.png` must retain SHA-256 `7ce0d2fbd0eb89d2f6786c9bb1d5bada1aff7d89ea2f5dd079cce8a26483e1a0`. New behavior changes pose temporarily; it does not replace, repaint or permanently cover the idle identity. V1.1.0 runtime states resolve to the approved chibi set in `assets/v1_1/` (idle, typing frames, working, microphone, music, guitar) through the central asset registry; V1.0 files remain only as fallback and history.

## Visual language

- Silver `#EEF2FF`, ice `#91E4F2`, violet `#B9A7F8`, midnight `#171B32`, muted ink `#A7AEC8`, rose `#F3A7CB`.
- Native Qt controls, Segoe UI labels, Cascadia Mono numbers and Microsoft YaHei UI fallback.
- Transparent 272 × 330 logical-pixel pet window; compact two-line status card above the character in Token Mode only (Daily Mode shows the pet alone). All states share one aspect-preserving 256 × 256 sprite box around one feet/ground anchor.
- The adjacent satellite panel (default 420 × 500, free four-edge/four-corner resize 420–650 × 400–800 with size persistence, compact fixed height 316 with size restoration) retains the companion palette and typography and scrolls on shorter screens. The real desktop pet is the sole character and is never replaced by a panel sprite. The detailed analytics window owns dense tables.
- All windows scale with Windows DPI and clamp restored positions to a visible screen.

## Supported states

Only these states exist in this version:

Usage is an overlay, not a character pose. The runtime pose priority is:

1. `working`: explicit verified Codex task lifecycle activity (distinct from typing).
2. `microphone`: an active Windows capture session.
3. `music`: an active Windows system-media playback session, with an optional verified subtitle line from platform media metadata.
4. `typing`: recent non-modifier keyboard activity, with alternating tap phases.
5. `idle`: the approved default.

The order above is the state priority. Microphone/music require a stable signal before entry and delay exit; typing expires shortly after the last key. Missing/stale platform signals never pin the pet in an activity state. No input text, audio stream, or extra pet state is collected; media title/artist/subtitle metadata is read memory-only for Music display and never stored.

## Usage reveal

- Hover the pet for roughly 0.35 seconds or click it to open the panel: right side first with a 12 px gap, left if right does not fit, otherwise the roomier side with panel-only clamping to the pet screen. Neither opening nor closing moves or saves the pet. Dragging it persists position and re-anchors an open panel.
- Leaving both pet and panel for roughly 0.7 seconds hides only the panel; the character keeps its live pose and position.
- The transparent pet does not activate itself when shown, so it does not steal typing focus.
- Open settings/details keep the panel available. Closing it suppresses immediate hover reopen until the pointer leaves.

## Usage panel contract

- Follow the current verified Codex task. Never select from the stale initial-route URL. If inaccessible or ambiguous, show the recent-task fallback label; allow explicit pinning.
- Tokens/cost use Global, Project or Conversation scope. Model, reasoning, context and raw latest snapshot describe the selected task. Quotas describe the account.
- Poll once per second with at most one quota RPC in flight. Numeric usage changes when Codex writes events, not through an invented counter.
- Preserve all reliable raw token fields. Unknown values display as N/A; cached input and reasoning output are never added twice.
- Read numeric local metadata only. Never export transcripts or credentials, send model requests, save key content, or record audio.

## Accessibility and controls

- Native menus, tooltips, focus and buttons remain keyboard usable.
- Drag either window; `Alt+Arrow` moves the panel. Always-on-top, collapse, tray restore, motion pause and explicit exit remain available.
- Tooltip text states raw sources, formulas, comparison-only metrics, stale quota samples and cost limitations.

## V1.3 task surfaces (unreleased)

The existing character, palette and DPI behavior remain the baseline. V1.3 has a Hub overview, one compact Star per verified active task, and one manager-owned Expanded Star. Technical integration and human visual acceptance are separate gates.

- The Hub lists the current visible task set, including multiple tasks from the same project. Its usage values retain their selected provider and scope provenance; they are not totals across all providers or Stars.
- Stars retain their neutral lifetime number, provider identity, window and slot. The native window remains112 ×112; current compact hit regions are a22px disc and18 ×14 number label, distinct and screen-contained.
- Opening a task reuses its task-local metadata projection in one detail card. The retained Star's current integer position is the anchor; the card clamps independently and scrolls on short screens. Switching detail does not change provider selection or scope or read a provider.
- While detail is expanded, projected phase, pose and slot recomposition pause. Metadata and lifecycle updates continue; newcomers requiring recomposition stay staged. Collapse resumes from the displayed pixels with a fresh clock and no elapsed-time catch-up.
- Removing/filtering the expanded task or hiding the task surfaces closes detail. Restore does not reopen it. Shutdown closes the card, Stars and trails and rejects late callbacks.
- The Hub task control, Star Return/Space, Escape and visible collapse control provide keyboard access. Passive hover preserves the coding application's focus; deliberate keyboard activation may focus detail.
- Unknown model is explicit Unknown/未知; unknown numeric fields and quota are N/A, genuine zero remains zero and partial coverage is labeled. Task-local effort/context appear only when recorded. No unverified Queued, Reviewing or progress phases are added.
- Current default motion uses one analytic fitted tilted ellipse and shared active phase. Its rear layer and smaller/dimmer rear Stars sit behind the approved character; the brighter front layer crosses in front. Two compact input-transparent layers share the existing manager timer; no path worker or restart timer is needed. Trails have at most80 samples per task/layer and2.8 seconds of history.
- Intentional drag, keyboard movement and preview position commands transport the attached composition with the pet, preserving phase, slot offsets and identity while clearing travel streaks. This deliberate scene translation is distinct from autonomous motion: orbit, membership, toggles and observed geometry glides preserve the16logical-pixel/40ms budget. OFF retains the current compact composition, finishes pose/slot changes and fade, then idles.
- Historical exterior-route utilities are tested with an explicit internal fixture option, never offered in current product controls. The reference image influenced composition only; no artwork was copied or replaced. Drawing reuses existing QPainter gradients/paths; Qt QWidget and Microsoft SetWindowPos documentation informed stacking/no-activation review, with no external implementation or dependency added.

Native stacking references: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html and https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos. Windows owned layers are inserted relative to the pet existing global Z position without activation; idle topmost flag recreation restacks immediately.

### Celestial visual refinement (2026-10-04)

The user reference Celestial Chibi Desktop Pet Interface.png informs materials: faceted ice/lavender crystals, pearl orbital wire, short champagne inlay, sparse beads/segmented guide and suspended number medallions. The desktop-sized rendition keeps decoration sparse and preserves the approved character. Palette: ivory#F7F6FF, iris#9E90DE, ice#B8DAF4, champagne#DCC6A6, ink#24233C; existing Segoe UI for factual lifetime task numbers. No new artwork, font/dependency or animation timer. Medallions stay within accepted18x14 interactive strips; ornament positions/depth derive from current placed Stars, never from another path or clock. Analytic geometry,22px hits, screen fitting, identity, Z-order/focus and ON/OFF semantics are unchanged. Native dark/light review remains required; the reference is composition data, not task instructions.
