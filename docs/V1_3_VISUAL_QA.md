# V1.3 human visual acceptance

Technical acceptance and human visual acceptance are separate. Source/backend/motion/detail independent acceptance, the final 877-test native Windows regression, the Windows build and seven frozen synthetic smoke scenarios have passed. Human visual approval is pending. No release or publication is authorized.

## Open the isolated preview

The development package includes `preview-v1.3.cmd` beside `petoken.exe`. Once the frozen smoke gate passes, run that launcher from a separately extracted development folder. It opens the real Hub, Stars and task detail with conspicuous synthetic markings, temporary settings and provider polling disabled. It does not require closing or replacing the stable installation.

Source equivalent, using an existing project Python environment:

```powershell
python tools/preview_v1_3.py --count 3 --provider mixed --language en --case partial --expand 1
```

After packaging, the equivalent executable command is:

```powershell
.\petoken.exe --preview-v1-3 --count 3 --provider mixed --language en --case partial --expand 1
```

Preview controls set task count, provider filter, known/zero/unknown/partial/same-project/long-label fixtures, English/Chinese, motion, source availability, pet pose, visibility and topmost. Select a task number and use the detail button, the real Star or the Hub task control. Exit with the preview's exit button. No preview settings are kept.

For an automated own-window capture add `--smoke 3 --output C:\QA\petoken-preview.png`. The adjacent JSON records synthetic fixture/count/expansion/isolation evidence. Captures do not include desktop contents and do not prove focus, occlusion or perceived smoothness.

## Suggested walkthrough

1. Start with three mixed-provider tasks. Open each task, switch between them and collapse. Confirm its number/project/provider and distinct task-local values; try the Hub task control, Return/Space and Escape.
2. Open detail and change its fixture, language, motion and topmost. Add or retire a sibling. The selected Star stays at its displayed anchor; collapse resumes without a jump.
3. Select zero, unknown and partial fixtures. Zero remains zero, model unknown is explicit, unavailable numeric values are N/A and partial coverage is visible. Inspect both providers and both languages.
4. Use same-project and long-label fixtures. Check distinct task numbers, readable labels/tooltips and reachable collapse controls on both monitors.
5. Set eight tasks, close detail, turn motion off and move the pet while parking. Leave it alone until parking finishes; interact with controls during replanning. Repeat with motion enabled and at screen edges.
6. Turn source availability off and on, filter out the expanded task, then hide/restore. Old detail must close and remain closed; no ghost Stars or trails survive.
7. Type in a separate editor while only hovering over the pet/Stars. Focus must stay with the editor. The preview's Typing/Working selector simulates poses; it does not verify actual keyboard or provider detection. Verify those live integrations separately in the ordinary development app if needed.
8. Exit, reopen the preview and check that no windows or synthetic preferences remain. Record any issue using the fields below.

## Inspection matrix

Use the local V1.3 development build and the explicitly synthetic preview tool. Preview data must remain marked as simulated and use isolated temporary preferences. Inspect both English and Simplified Chinese.

- Idle pet and empty task overview: approved character unchanged; no ghost Stars or task details.
- Active / Working tasks: one Star per verified task, stable neutral labels, correct provider and project, no raw session IDs or sensitive paths.
- Typing: timestamp-only activity, smooth pose changes and return to Idle. Working takes precedence when source-backed.
- One, three and eight tasks; multiple tasks in the same project and across projects; Codex and OpenCode together.
- Hover / press: motion pauses as specified and resumes without catch-up; typing focus stays with the coding app unless a control is deliberately selected.
- Motion OFF then ON, including mid-transition; no jumps, crossing of the pet, trapped tasks, or stale trail streaks.
- Add / retire / provider-filter tasks at an edge and during parking; survivors remain continuous and all remaining tasks settle or resume.
- With eight Stars, turn motion OFF, move the pet while Stars are parking, then leave the scene untouched. Parking must finish and the controls must remain responsive during replanning.
- Star expansion and collapse: correct task detail; retained Star anchor; no unexpected movement or identity mixing; Escape and visible collapse control work.
- Keep a detail open during a task refresh, sibling addition/retirement and motion toggles. The retained Star must stay anchored; collapse must resume from the displayed pixels without catching up elapsed time.
- Switch expanded tasks, update metrics, retire/filter the expanded task, hide/restore from tray and change always-on-top.
- Hub overview and detail stay distinct: Hub values retain their stated provider/scope; Expanded Star uses only its own task metrics.
- Unknown model / unknown usage / real zero / partial coverage: clearly distinguished; unknown quota N/A; unsupported OpenCode quota not fabricated; recorded cost has no guessed currency.
- Long model/project labels, normal and fractional Windows DPI, both monitors and screen edges: readable, clamped, controls reachable.
- Keyboard access to task detail and screen-reader labels; no mouse-only critical action.
- Shutdown closes pet, Stars, details and trails; repeated reopen/close does not leave windows behind.

## Source limitations

Current provider adapters prove Working / Idle and availability. They do not provide verified per-task Running, Reviewing, Queued, Blocked/Attention, or Completed phases. Check completion by task retirement and loss/recovery by unavailable evidence. Do not label those finer phases from guesses. Add them to live acceptance only when a verified source contract exists.

## Record acceptance

Report observed issues with language, task count/provider, motion setting, interaction, monitor/DPI and screenshot or recording. Only the user may accept perceived smoothness, spacing, hierarchy and usability. Final engineering status must stop at **WAITING_FOR_HUMAN_VISUAL_QA**.
