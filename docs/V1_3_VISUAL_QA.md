# Historical V1.3 Codex companion: human visual QA

Superseded for the current development preview by [V1.4 visual QA](V1_4_VISUAL_QA.md). The following records the prior V1.3 package and its historical technical scope.

**Human visual acceptance pending.** The current compact tilted star ring, pearl/cyan/lavender Stars, longer tapered trails, attached drag and Codex-only product have passed873 native regression tests and independent native source/layering review. Screen-edge motion is driven by the shared ring phase and does not require a travel path. Native topmost toggles and depth crossings preserve correct occlusion, editor visibility and focus. The isolated development package is for the walkthrough below; it does not replace the stable installation. No release or publication is authorized.

Current celestial refinement adds faceted crystal highlights, fine champagne/silver inlay, sparse orbit beads and suspended number medallions. Compare those at the actual desktop size on both dark and light backgrounds; the reference illustration is inspiration, not a promised pixel-for-pixel copy. Geometry, task identity, screen-edge behavior and Codex-only scope retain the accepted contract.

## Open the isolated preview

Extract the refreshed development package separately and run `preview-v1.3.cmd` beside `petoken.exe`. The real Hub, task Stars and task detail use conspicuous synthetic markings, temporary settings and no provider polling. The stable installation is not replaced.

Source equivalent with an existing project Python environment:

```powershell
python tools/preview_v1_3.py --count 3 --language en --case partial
```

Packaged equivalent:

```powershell
.\petoken.exe --preview-v1-3 --count 3 --language en --case partial
```

All fixtures are Codex-only. Controls set 0–8 tasks, known/zero/unknown/partial/same-project/long-label usage, English/Chinese, position, motion ON/OFF, source availability, pet pose, visibility and topmost. Choose a task number and open detail through its button, the actual Star or the Hub task control. Exit with **Exit preview**. Preview preferences are not kept.

Positions are `center`, `left`, `right`, `top`, `bottom`, `top-left`, `top-right`, `bottom-left`, `bottom-right`; they move the actual pet through its clamped placement path. Drag the pet too: static edge captures do not replace movement testing. The selector moves within the current monitor; drag onto another monitor to inspect that monitor/DPI.

For a bounded owned-window capture:

```powershell
.\petoken.exe --preview-v1-3 --count 8 --language zh_CN --anchor top-right --smoke 3 --output C:\QA\ring-top-right.png
```

The adjacent JSON records synthetic scenario/count/detail/isolation evidence. Capture composition uses the actual manager-owned back ring, rear Stars, pet, front trail, front Stars and detail, followed by the Hub/preview controls. It never captures desktop contents. These captures prove paint/content and intended layer order; human inspection must still check native desktop occlusion, focus and perceived motion.

## Focused walkthrough

1. **Distance and art direction:** start with 1, then 3, then 8 tasks, detail closed. The ring should hug the character and feel attached to it. Inspect tilt, a clear rear/front relationship, pearl/cyan/lavender highlights and richer Star silhouettes. There should be no giant empty orbit or flat blue circle. Inspect several positions around the moving ring.
2. **Trails:** inspect graceful length, taper, glow and decay while rotating and after stopping. The trail must support the ring without covering labels, the character or detail text. Turn motion OFF/ON, hide/restore and remove tasks; no permanent streaks, ghost particles or old task trails may remain.
3. **Every edge and corner:** with 1/3/8 tasks and motion ON, select each of the eight edge/corner positions. Drag slowly along the edge, into the corner and back to center. Stars must keep visibly moving when no travel path is active or a previous path is exhausted. A blocked position must not freeze the entire ring.
4. **Motion OFF and geometry changes:** repeat edges/corners with motion OFF. Move the pet while the composition is settling, add/retire a task, then leave the scene alone. Every remaining task must settle to a safe finite position; controls stay responsive. Turn motion ON before and after settlement and verify immediate, continuous resumption. Detail/hover can deliberately pause motion; close detail and move the pointer away when checking edge liveness.
5. **Identity and expansion:** use same-project tasks with distinct synthetic task counters. Open each numbered Star, switch tasks, collapse, then try Hub task menu, Return/Space, rapid Escape and the visible collapse button. Details must belong only to that task; its Star/object/anchor must be retained. No identity exchange, stale detail or elapsed-time catch-up jump.
6. **Refresh/lifecycle:** keep detail open while changing fixture/language/topmost, adding/retiring a sibling and toggling motion. Turn source availability OFF/ON; unavailable tasks and old detail close and do not reopen on their own. Hide/restore and retire the expanded task; no orphan Stars, ring layers, trails or details.
7. **Truth and readability:** inspect known/zero/unknown/partial in English and Chinese. Zero stays zero, unknown model is explicit, unavailable numeric/quota/cost values are N/A, partial remains visible. Long labels have readable tooltips and reachable collapse controls on short screens and fractional DPI. Only Codex appears in current provider/settings/preview presentation; there is no mixed-provider choice.
8. **Focus and responsiveness:** type in a separate editor while hovering over pet/Stars; the editor keeps focus until an intentional control click. Click controls while eight Stars move/replan, repeat hide/restore, then exit/reopen. No stalls, timer/particle accumulation or leftover windows. Observe native front/back layering directly: owned-window screenshots cannot establish actual OS z-order.

## Source limits

The Typing/Working selector simulates visual poses. It does not prove live keyboard or Codex detection; check those separately in an ordinary development run if needed. The synthetic model label is explicitly fictional and has no pricing quote, so its estimate is N/A rather than a fabricated price/currency. Real Codex Working/Idle and availability evidence do not prove Running, Reviewing, Queued, Blocked/Attention or Completed phases. Check retirement and source loss/recovery without guessing those finer phases.

## Record the human result

Record language, task count, fixture, motion ON/OFF, selected edge/corner, interaction, monitor/DPI and screenshot/recording. Judge proximity, spatial depth, Star/trail quality, smoothness, readability, occlusion and usability. Only the user can give final human visual acceptance. Engineering must stop at **WAITING_FOR_HUMAN_VISUAL_QA** after the refreshed technical gates; no release follows automatically.
