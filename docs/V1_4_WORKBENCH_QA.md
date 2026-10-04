# V1.4 Workbench — isolated human visual QA

This is an unreleased development preview. The accepted v1.3.0 release remains
available separately. V1.4 adds a native workbench home, basic project spaces,
todos and plain-text notes. No cloud sync, notifications or automation yet.

## Open the isolated preview

Extract the entire development package and run **preview-workbench.cmd** beside
petoken.exe. It opens the workbench and synthetic companion controls. It uses
temporary settings, a temporary SQLite database and synthetic Codex tasks;
closing the preview removes all sample records. It does not start live provider,
microphone or keyboard monitoring, or acquire the normal personal instance lock.

Do not use this disposable preview to keep real notes. Close it before testing
another package. The regular executable uses the user's existing settings
directory: `%LOCALAPPDATA%\CodexWisp\workbench.sqlite3`. It opens this database
only when the workbench is requested and starts with no sample records. Its
SQLite records are local plain text, not encrypted and not uploaded.

The embedded application version stays 1.3.0 during development. The workbench
preview window explicitly identifies the new V1.4 candidate. A new release
version/package requires its own acceptance and publication decision.

## What to check

- **Selection controls:** Todo/project Edit and Delete appear only after a valid
  row is selected; note Delete and task Details/Link follow their selected record.
  Empty or deselected lists hide these controls. The completed-todo filter has a
  visible tick when checked; mouse and Space toggle it without changing records.

- **Getting started:** the first normal application launch (or first workbench
  visit) opens a five-step optional guide:
  moving/opening the pet, projects, todos, saving notes, and Codex task stars.
  Its buttons use the real controls. Try Back/Next, Skip/Finish and replay from
  the workbench header, character right-click menu or tray. Skip/Finish are
  remembered after a successful settings save; closing the guide only dismisses
  it for this session. The guide creates no sample records automatically.
  Canceling a note action must keep its unsaved draft.

The refreshed launcher starts with an empty workbench and zero synthetic Codex
tasks, matching a newcomer. The QA controls can add synthetic tasks. For seeded
samples, run `petoken.exe --preview-workbench`; for a bounded tutorial capture,
use `--tutorial --tutorial-step 0..4 --smoke SECONDS --output PATH.png`.

- **Home:** character header, counts, pending items and current Codex tasks are
  readable in Chinese and English, including at the smallest supported window.
- **Projects:** create/edit a name and optional folder; filter with the sidebar.
  Duplicate names retain separate identities. Open Folder only opens that path.
- **Todos:** add, edit, move to another project, complete, reopen and delete an
  item. The completed filter is reversible; long names remain accessible.
- **Notes:** create, edit, move and save with the button or Ctrl+S. Switching note,
  project, closing the workbench or exiting Petoken asks Save/Discard/Cancel.
  Cancel retains the editor and application; failed saves retain the draft.
- **Project deletion:** todos and notes move to Unassigned; deleting a project
  never deletes a Codex task or its folder.
- **Task links:** select a current Codex task, choose Link Project, then filter.
  View Details opens the existing Star detail. Try 24 tasks and an off-page task.
  Retiring a task removes it from the workbench without deleting personal notes.
- **Companion:** open/close the workbench and Hub; resize/move the character.
  The ring stays enabled unless deliberately disabled in Settings/QA controls.
- **Layout:** resize the workbench, navigate with Tab/Enter, and switch language
  from the synthetic controls while a note has an unsaved draft.

The requested minimum is 680 × 460 logical pixels. Qt may increase the height
slightly to accommodate the selected language, empty-state text or an error.
Lists and the note editor scroll; splitters adjust the available space.

Sample records are marked **QA**. Empty-state testing is also available:

```powershell
.\petoken.exe --preview-workbench --empty --count 0 --language en
.\petoken.exe --preview-workbench --tab notes --width 680 --height 460
```

The former `preview-v1.4.cmd` is the historical star-ring preview developed
before the user chose to release those changes as v1.3.0. Use
**preview-workbench.cmd** for this new milestone.

## Acceptance

Technical and independent reviews establish only the tested boundaries. Human
judgment of appearance, desktop fit and daily usability remains required.
After technical validation the candidate waits at
**WAITING_FOR_HUMAN_VISUAL_QA**. It is not published or installed over a stable
copy automatically.
