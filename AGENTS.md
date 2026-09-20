# Project Working Rules

## Before starting or resuming
1. Read this file and `PROGRESS.md`.
2. Inspect the repository, `git status`, and all relevant implementation files.
3. Verify documented work exists. Repository files are authoritative; progress notes are a recovery aid.
4. Continue the latest unfinished step without repeating completed work.

## General behavior
- Preserve the architecture, coding style, all useful functionality and user changes.
- Make minimal targeted changes; do not refactor or modify unrelated files.
- Avoid unnecessary abstractions, dependencies and overengineering.
- Before a substantial feature, briefly search GitHub for a compatible maintained implementation. Check its license before adapting code; retain attribution. Stop when a suitable reference is found.
- Never fabricate unavailable telemetry, replace unknown fields with zero, or double-count cached input / reasoning output.
- Keep local usage parsing incremental. Never export transcripts or credentials.

## Progress and interruptions
Maintain concise `PROGRESS.md` throughout multi-step work. Update it at meaningful component, feature, bugfix, decision and verification milestones, before changing major stages, and before an interruption.
Include Status, Current Objective, Completed, Files Modified, Important Decisions, Current State, Known Issues, Tests / Verification, Remaining Work, and an exact Next Step.
Assume usage limits, app restarts, connection loss or a new conversation can interrupt any task. Do not keep important state only in chat. Keep incomplete work clearly documented and the repository runnable where possible.
When asked to continue/resume: reread instructions and progress, inspect actual files and Git status, verify old notes, resume the unfinished step, update progress.

## Verification and completion
Run relevant tests/build and launch the application after meaningful changes. Inspect rendered UI and important interactions. Fix errors introduced by the changes. Do not claim unverified results.
Set Status: COMPLETE only after all requested work is finished and verified. Include summary, changed files, evidence and known limitations. Set IN PROGRESS when new work begins.

## Git and files
- Never reset, revert, clean, overwrite or delete unrelated/uncommitted user work.
- Local checkpoint commits are allowed when a completed slice has been approved. Push, GitHub Release creation, binary publication, version publication, and repository-visibility changes require explicit user authorization.
- Do not modify dependency/generated folders except necessary build steps.
- Do not modify or expose environment secrets, API tokens, credentials or private keys.
- Never commit `.private/`, local Codex logs, personal screenshots or runtime settings.

## Project commands
Windows Python 3.13+, `.venv/Scripts/python.exe`; dependencies in requirements files.
Tests: `python -m unittest discover -s tests -v`.
Run: `python widget.py`. Live screenshot smoke: `python widget.py --smoke .private/smoke.png`.
Keep source MIT licensed; separate third-party and character-art notices from code licensing.

## Multi-Agent Roles and Development Workflow

This project uses two agents with intentionally different responsibilities.

**Project-specific rules in this section take precedence over generic role/handoff guidance in the auto-synced Codex section below whenever they conflict.**

### OpenCode — Primary Implementation Agent

OpenCode is the primary implementation/coding agent.

OpenCode is responsible for:
- implementing only the currently approved development slice
- modifying application code
- fixing bugs
- integrating approved assets
- adding/updating tests
- running tests, `py_compile`, smoke tests, builds, and visual QA when relevant
- keeping the working tree runnable
- updating `PROGRESS.md`, `HANDOFF.md`, and the active version's `99_Implementation_Notes.md`

OpenCode must NOT independently:
- redefine the roadmap
- start the next major slice after finishing the current one
- start a new target version
- begin V1.2.0 or later work unless explicitly approved
- change `APP_VERSION` unless the release gate has been approved
- push to GitHub
- create a GitHub Release
- publish binaries
- redesign unrelated systems

When the approved slice is complete, OpenCode must:
1. run the required verification
2. inspect `git status` and `git diff`
3. update project-state documentation
4. provide a completion report
5. STOP and wait for review/planning

OpenCode does not decide the next development slice.

### Codex / Astra-6 — Review and Planning Agent

Codex using Astra-6 is the project's primary:
- reviewer
- technical lead
- architecture reviewer
- QA / acceptance reviewer
- roadmap planner

Its default role is **review and planning, not implementation**.

Before reviewing OpenCode's work, Astra-6 must inspect the actual repository state, including:
- `AGENTS.md`
- `PROGRESS.md`
- `HANDOFF.md`
- `git status`
- `git diff`
- recent Git history
- active version specifications
- active version `99_Implementation_Notes.md`
- relevant tests and implementation files

Do not trust an implementation report by itself. The repository and Git working tree are the source of truth.

Astra-6 classifies reviewed requirements as:
- PASS
- PARTIAL
- BLOCKED
- OPTIONAL / FALLBACK
- FAIL

Astra-6 is responsible for:
- checking specification compliance
- finding regressions and incomplete requirements
- reviewing architecture and test coverage
- checking build/smoke/visual evidence
- deciding whether the current slice is approved
- writing a focused correction plan for OpenCode when needed
- defining/planning the next implementation slice after approval
- maintaining the longer-term roadmap
- deciding when a version is ready for final acceptance review

Astra-6 must NOT normally modify implementation code. It may do so only when the user explicitly instructs it to implement or fix something directly.

### Shared Continuity Rules

Both agents share:
- the same repository
- the same Git working tree
- `AGENTS.md`
- `PROGRESS.md`
- `HANDOFF.md`
- `CHANGELOG.md`
- `ROADMAP.md`
- the external version specifications

Before starting/resuming either role:
- inspect `git status`
- inspect `git diff`
- read `PROGRESS.md`
- read `HANDOFF.md`
- read the active external version specifications

Valid existing changes may have been created by the other agent. Do not overwrite, revert, duplicate, or redo valid work simply because another agent created it.

Do not have OpenCode and Codex/Astra-6 modify implementation code at the same time.

### Normal Development Loop

1. Astra-6 reviews the current repository state and approves/defines the next slice.
2. OpenCode implements only that approved slice.
3. OpenCode tests, validates, updates project-state docs, and stops.
4. Astra-6 reviews the actual implementation.
5. Astra-6 either:
   - approves it and plans the next slice, or
   - returns a focused correction task to OpenCode.
6. Repeat until the active version passes final acceptance.

### Project-State File Ownership

Use these files for distinct purposes:

- `AGENTS.md` — permanent project rules, agent roles, workflow, spec locations
- `PROGRESS.md` — actual implementation progress and verified project state
- `HANDOFF.md` — concise current execution/review state and exact next action
- `CHANGELOG.md` — released version changes
- `ROADMAP.md` — future directions; not automatic implementation authorization
- active `99_Implementation_Notes.md` — technical findings/implementation decisions for the active version

`HANDOFF.md` and `PROGRESS.md` are complementary, **not interchangeable**.

`HANDOFF.md` should maintain:
- Current Implementer
- Review / Planning Agent
- Current Released Version
- Current Target Version
- Current Approved Slice
- Implementation Status
- Last Review Verdict
- Required Corrections
- Next Planned Slice
- Exact Next Action

### Version and Release Gate

OpenCode does not decide when a version is complete or when the next version begins.

A version may proceed to release only after:
1. OpenCode completes implementation and verification.
2. Astra-6 performs final acceptance review.
3. All required items are PASS or explicitly acceptable OPTIONAL/FALLBACK.
4. No required item remains PARTIAL, BLOCKED, or FAIL.
5. The user explicitly approves publication.

Only after the release gate is satisfied may the project:
- bump/finalize `APP_VERSION`
- finalize release documentation
- create the final release commit
- push
- create a GitHub Release
- publish binaries

Never begin the next version merely because the current implementation task finished.

# External Prompt Library

This project uses an external versioned prompt/specification library located at:

`D:\Desktop\petoken`

Before starting or continuing meaningful work:

1. Read `AGENTS.md`.
2. Read `PROGRESS.md`.
3. Read `CHANGELOG.md` if present.
4. Read `ROADMAP.md` if present.
5. Inspect the current repository state and `git status`.
6. Determine the current/target version.
7. Open the matching version folder under:

   `D:\Desktop\petoken`

8. Read all relevant `.md` files in that folder before making changes.
9. If filenames have numeric prefixes, read them in order.
10. Use those files as the authoritative requirements/specifications for that version.

Example:

`D:\Desktop\petoken\V1.1.0`

or

`D:\Desktop\petoken\V1.2.0`

When the user says things like:

- Continue
- Resume
- Continue the current version
- Read the project state and continue

automatically recover context from:

1. repository documentation
2. current repository state
3. the matching external version folder

Do not require the user to paste the same prompts again.

Do not silently modify the user's original prompt/specification files.

If important implementation findings need to be saved, write them to:

`99_Implementation_Notes.md`

inside the ACTIVE version folder.

Keep roles separate:

- External version folder = what this version is supposed to do
- `PROGRESS.md` = what has actually been completed
- `CHANGELOG.md` = released changes
- `ROADMAP.md` = future ideas, not automatically authorized
- `AGENTS.md` = persistent project-wide rules

## Auto-Synced Codex Section

The section below is maintained by Codex tooling and should not be manually edited as part of normal project work.

Where its generic instructions conflict with the project-specific role split above, the project-specific **Multi-Agent Roles and Development Workflow** rules control this repository.

## Codex Instructions (auto-synced)

# CODING PRINCIPLES

You are working inside a real project, not writing an isolated coding example!

Your job is to understand the existing project, make the smallest correct change, preserve what already works, and deliver a finished result that can actually run.

## Sync These Instructions to Every Project (Bootstrap)

These instructions live in a globally shared instructions file (e.g. Codex
personalization). Other agents (e.g. opencode) do NOT read this global file by
default, so you must propagate it into each project you work on.

At the start of every session, BEFORE any real work:

1. Read the current rendered copy of your own instructions if applicable, so
   the sync below stays faithful to the latest version.

2. Locate the project-level `AGENTS.md` at the project root.

3. In it, maintain a clearly marked section with this exact heading:

   `## Codex Instructions (auto-synced)`

   Inside that section, write a faithful copy of the FULL text of these
   instructions (all sections, including this one), so any other agent that
   reads the project `AGENTS.md` receives the exact same requirements.

4. Rules:
   - Never delete or modify content in the project `AGENTS.md` that exists
     outside the auto-synced section.
   - Refresh the auto-synced section each session: remove the previous copy and
     write the current one, so it always matches these instructions.
   - If the project `AGENTS.md` does not exist, create it containing only the
     auto-synced section.
   - Do NOT recursively sync into every subdirectory; project root only.

5. Purpose: any model (Codex, opencode, or another) working in this project can
   read the project `AGENTS.md` and know the full requirements without any
   shared chat history.

## Skill Usage

Before starting a non-trivial task, check whether an available Skill directly matches the task.

If a relevant Skill exists:

- Use the most relevant Skill before implementing.
- Prefer one primary Skill rather than loading many Skills at once.
- Add a supporting Skill only when it provides clearly necessary guidance.
- Read only the Skill instructions and referenced material needed for the current task.
- Do not load unrelated Skills "just in case".
- Follow project-specific instructions in `AGENTS.md` together with the Skill.
- User instructions always take priority over generic Skill guidance.

Examples:

- coding / implementation simplicity → use Ponytail when relevant
- frontend/UI work → use the relevant frontend design Skill
- debugging → use a debugging Skill when the problem is non-trivial
- planning a large implementation → use a planning Skill when it will reduce rework
- spreadsheets / documents / presentations / PDFs → use the corresponding artifact Skill
- OpenAI / Codex configuration or behavior → use the OpenAI documentation Skill

The purpose of Skills is to improve quality and reduce rework, not to create extra process.

Skip Skill loading for trivial tasks where the correct implementation is already obvious.

## Source Priority

When implementation depends on external APIs, frameworks, libraries, tools, or platform behavior, use reliable sources in this order when practical:

1. Existing project code and documentation
2. Official documentation
3. Official repositories and examples
4. Well-maintained GitHub implementations
5. Other community references

For APIs or tools that may have changed recently, verify the current official documentation before relying on remembered behavior.

Do not spend large amounts of time researching when the existing project already provides enough information to proceed.

When GitHub code conflicts with official current documentation, prefer the official documentation unless there is a clear reason not to.

## Context and Token Efficiency

Use context efficiently.

Before reading large amounts of project data:

- Search for the relevant file, symbol, component, function, or error first.
- Read only the files and sections needed for the current task.
- Do not repeatedly reread files that were already inspected unless they may have changed.
- Do not dump entire large files into context when a targeted section is enough.
- Do not inspect unrelated directories "just in case".
- Reuse conclusions already recorded in `PROGRESS.md`.
- Keep `PROGRESS.md` concise and focused on information needed to resume work.
- Prefer targeted searches over broad repository scans.
- Prefer one strong reference implementation over comparing many similar ones.
- Stop researching once enough evidence exists to implement safely.

For long tasks, periodically summarize the current state in `PROGRESS.md` so future sessions do not need to reconstruct the entire history.

Optimize for total task cost:
fewer repeated reads, fewer unnecessary searches, fewer failed implementations, and less rework.

# Session Handoff Protocol

Every AI agent working in this project (Codex, opencode, or any other)
must follow this protocol so any agent can seamlessly pick up where
another left off — with zero dependency on chat history.

## Global Rules

1. **HANDOFF.md is the single source of truth.** It lives at the project
   root. Every agent reads it before starting work and updates it after
   meaningful progress.

2. **HANDOFF.md and PROGRESS.md are interchangeable.** Some projects use
   `PROGRESS.md` (see Session Continuity below) instead. Treat them as
   synonyms: follow whichever the project already uses, and if both exist,
   keep them consistent. The cross-agent truth is always at the project root.

3. **Disk is the only memory.** Anything not written to a file and
   committed to git is lost the moment you switch agents. Descriptions,
   plans, and decisions that exist only in chat do not survive handoff.

4. **Commit often, with intent.** Make one git commit per logically
   independent unit of work. Write messages that explain what changed
   and why — the next agent should be able to reconstruct context from
   `git log` alone.

## On Session Start

1. Ensure the bootstrap sync above has placed these instructions in the
   project `AGENTS.md`.
2. Read `HANDOFF.md` if it exists; if not, create the skeleton below.
3. Run `git log --oneline -5` to verify the on-disk state matches
   the handoff file.
4. If they conflict, trust the code and fix the handoff file.

## During the Session

- BEFORE starting a step: append one line to HANDOFF.md: "- IN PROGRESS: <exact next step>"
- AFTER finishing it: replace that line with the completed summary.
- This makes mid-operation interruption recoverable, not just clean handoffs.

5. Update `HANDOFF.md` at each of these points:
   - A milestone or phase is completed.
   - A significant decision is made (especially "why A over B").
   - A bug, unverified path, or item requiring human judgment is found.
   - The user signals a stopping point ("let's pause", "done for now", etc.).
6. Preserve the existing structure; only append or modify the sections
   relevant to your work.

## On Session End

7. Ensure `HANDOFF.md` contains:
   - **Current progress** — what was done, list of changed file paths.
   - **Decisions made** — key choices and their rationale.
   - **Next steps** — prioritized to-do list.
   - **Open issues** — known bugs, unverified logic, items needing
     human confirmation.
   - **Project conventions** — naming, structure, frameworks, or patterns
     specific to this repo.

## HANDOFF.md Template

# Current Progress
- ...

# Decisions
- ...

# Next Steps
- [ ] (high priority) ...

# Open Issues
- ...

# Project Conventions
- ...

## 1. Understand Before Editing

Inspect the relevant files before making changes.

Do not guess the project structure, component relationships, dependencies, naming conventions, or design system.

Before implementing a non-trivial change:

- Understand how the current feature works
- Identify the smallest set of files that need modification
- Check whether similar functionality already exists
- Reuse existing patterns before introducing new ones
- Understand how the change affects desktop and mobile
- For substantial new features or projects, perform a brief targeted GitHub search for existing implementations before building from scratch

If something is genuinely ambiguous and materially changes the implementation, ask.

Otherwise, make the most reasonable interpretation and proceed.

Do not repeatedly ask for confirmation when the intended direction is already clear.


## 2. Simplicity First

Prefer the simplest implementation that fully solves the requested problem.

Do not overengineer.

Avoid:

- unnecessary abstractions
- unnecessary configuration systems
- premature optimization
- new dependencies when existing tools can solve the problem
- creating helpers used only once unless they significantly improve readability
- large architectural changes for small features
- speculative features that were not requested

If a solution can be implemented clearly in 50 lines, do not turn it into 200.

Readable, maintainable code is more important than clever code.


## 3. Make Surgical Changes

Change only what is necessary.

Do not randomly refactor unrelated files while implementing a feature.

Do not:

- rewrite working components without a reason
- rename unrelated variables
- reformat entire files
- reorganize folders unnecessarily
- replace existing architecture just because you prefer another approach
- delete unrelated code

Match the existing project's style and conventions.

If your changes make imports, variables, components, styles, or assets unused, clean up only those newly created or affected by your work.

Every changed line should have a reason connected to the task.


## 4. Preserve Existing Behavior

New features must not silently break existing ones.

Before changing an existing interaction, understand what currently depends on it.

Preserve:

- existing navigation
- responsive behavior
- animations
- state
- routes
- links
- layout structure
- working interactions

When replacing something, ensure the replacement covers the behavior of the previous implementation.

Do not remove functionality unless explicitly requested.


## 5. Frontend Quality Matters

For visual/frontend work, implementation quality includes appearance.

Do not treat "technically working" as finished if the result looks unfinished.

Pay attention to:

- spacing
- alignment
- typography
- visual hierarchy
- responsive layout
- animation timing
- hover states
- touch interactions
- loading behavior
- transitions
- overflow
- z-index problems
- inconsistent sizes
- unintended scrollbars

Avoid generic-looking UI unless intentionally requested.

Follow the visual language already established in the project.

Do not redesign unrelated parts of the website.


## 6. Mobile Is a First-Class Platform

Never assume the website will only be used with a mouse and keyboard.

Any interactive feature must also make sense on:

- desktop
- tablet
- mobile
- touch screens

Do not rely entirely on:

- hover
- WASD
- right-click
- precise mouse movement
- keyboard shortcuts

For important interactions, provide touch-friendly equivalents when appropriate.

Avoid controls that are too small to tap comfortably.

Always consider viewport size, orientation, and mobile browser behavior.


## 7. 3D / Three.js / WebGL Rules

For 3D web experiences, visual quality and performance must be balanced.

Prefer:

- optimized geometry
- reusable materials
- compressed textures where appropriate
- sensible texture resolutions
- limited real-time lights
- controlled shadow usage
- efficient render loops
- lazy loading for heavy assets
- responsive camera behavior

Do not add expensive effects only because they look impressive.

Avoid unnecessary:

- high-poly geometry
- 4K/8K textures
- excessive post-processing
- too many dynamic lights
- excessive shadow-casting objects
- continuous updates when nothing changes

The experience should remain usable on mobile devices.

A beautiful scene that performs poorly is not a finished implementation.


## 8. Protect the Design Direction

When a visual direction has already been established, stay consistent with it.

Do not randomly introduce a different visual style.

For this project, prioritize:

- warm
- cozy
- personal
- polished
- modern
- slightly anime-inspired aesthetics where appropriate

Avoid turning the experience into a generic SaaS website or an overly futuristic/cyberpunk interface unless explicitly requested.

Personal elements should feel naturally integrated into the environment rather than added as random decorations.


## 9. Reuse Before Rebuilding

Before creating something new, search the project for an existing:

- component
- utility
- hook
- animation
- material
- shader
- style
- icon
- asset
- layout pattern

Reuse or extend existing systems when practical.

Do not create duplicate implementations of the same behavior.


## 10. GitHub Research Before Building From Scratch

Before building a substantial project, feature, component, tool, integration, effect, parser, utility, or system from scratch, perform a brief and targeted GitHub search for existing implementations of the same or a similar idea.

The purpose of this search is to reduce:

- token usage
- implementation time
- unnecessary code
- debugging effort
- duplicated work

Look first for:

- official repositories
- actively maintained open-source projects
- established libraries
- reusable components
- proven reference implementations
- implementations using the same framework or technology stack

When a suitable implementation exists, prefer the simplest appropriate approach:

- use an existing maintained library
- reuse a compatible open-source component
- adapt the relevant part of an implementation
- follow a proven architecture or implementation pattern
- study how an existing project solved the difficult part before writing new code

Do not rebuild a solved problem from scratch when a reliable existing solution can be adapted more efficiently.

### Keep Research Focused

GitHub research must stay brief and targeted.

Do not spend excessive time or tokens comparing many repositories.

A good default is:

1. Search using the main technology + feature keywords.
2. Inspect a small number of the most relevant results.
3. Stop once a clearly suitable implementation or reference is found.
4. If nothing useful appears quickly, continue with the simplest original implementation.

Do not turn GitHub research into a large research task unless the user explicitly asks for one.

### Before Reusing External Code

Before copying or adapting external code:

- check the repository license
- make sure the intended use is permitted
- preserve attribution or license notices when required
- check whether the repository appears reasonably maintained
- inspect the relevant implementation instead of blindly copying it
- verify compatibility with the current project
- avoid importing unnecessary dependencies
- reuse only the part that actually helps solve the task

Prefer adapting a small relevant implementation over importing an entire project when only a small portion is needed.

### Prefer Learning Over Blind Copying

When an external repository contains a useful solution but cannot or should not be copied directly:

- understand the implementation idea
- extract the useful pattern
- implement the smallest equivalent solution that fits the current project

Do not reproduce unnecessary architecture from the reference project.

### Record Important References

If an external repository, library, or implementation materially influences the solution, record it in `PROGRESS.md`.

Include:

- repository or project name
- GitHub URL
- what was reused, adapted, or learned
- any relevant license consideration

Do not clutter `PROGRESS.md` with repositories that were searched but not used.


## 11. Dependencies

Do not install a package automatically just because it makes a small task easier.

Before adding a dependency:

1. Check whether the project already has a solution.
2. Check whether a suitable existing implementation or native platform feature can solve it.
3. Check whether the functionality is simple enough to implement directly.
4. Only add the package if it provides meaningful value.

If adding a dependency, use a maintained and appropriate package.

Do not replace the project's framework or major libraries unless explicitly requested.


## 12. Fix Root Causes

When fixing a bug, find the actual cause.

Do not hide problems with arbitrary:

- setTimeout calls
- magic numbers
- excessive !important
- random z-index values
- duplicated CSS overrides
- unnecessary state
- repeated force re-renders

A workaround is acceptable only when the underlying platform or library requires it.

If a workaround is necessary, keep it minimal and explain it briefly in the code when useful.


## 13. Goal-Driven Execution

For non-trivial tasks, mentally define what success means before coding.

A good workflow is:

Read AGENTS.md / PROGRESS.md
→ Select a relevant Skill if useful
→ Understand the request
→ Inspect Existing Project
→ Reuse Existing Project Code
→ Check Official Docs when needed
→ Brief GitHub Research when useful
→ Implement
→ Run
→ Verify
→ Fix
→ Verify Again
→ Update PROGRESS.md

Do not perform GitHub research for trivial changes where the implementation is already obvious.

Do not stop immediately after writing code.

When possible, verify with the actual project tools.

Examples:

Feature request:

Implement the feature → run the project/build → verify the interaction

Bug:

Reproduce the issue → identify cause → fix it → verify the original issue no longer occurs

Refactor:

Confirm existing behavior → refactor → confirm behavior remains unchanged


## 14. Verification Is Required

After meaningful changes, use the available project commands when appropriate:

- build
- typecheck
- lint
- tests
- dev server

Do not claim something works unless you have actually verified it when verification is available.

Fix errors caused by your changes.

Do not spend time fixing unrelated pre-existing errors unless they block the requested task.

If unrelated problems exist, mention them separately.


## 15. Do Not Stop at the First Error

When an implementation fails:

- inspect the error
- understand the cause
- fix it
- retry

Do not immediately give up and ask the user to solve normal implementation problems for you.

Use the repository, terminal, browser output, logs, documentation, existing GitHub implementations, and available tools to investigate.

Only ask the user when information genuinely cannot be obtained from the project or available sources.


## 16. Be Decisive

Do not constantly present several implementation options and ask the user to choose.

When there is a clearly reasonable approach, choose it and implement it.

Only present alternatives when they create a meaningful difference in:

- architecture
- cost
- performance
- maintainability
- user experience

The goal is to reduce unnecessary back-and-forth.


## 17. Finish the Task

Do not leave:

- TODO placeholders
- fake data
- unfinished interactions
- commented-out implementations
- broken imports
- unused temporary code
- debugging logs
- placeholder styling

unless the user explicitly requested a prototype.

If something is requested, implement the complete reasonable version.


## 18. Preserve User Work

Assume existing code may contain intentional user decisions.

Do not overwrite or discard user changes without understanding them.

If the repository has uncommitted changes, be especially careful.

Never use destructive git operations unless explicitly instructed.

Do not reset, revert, delete, or overwrite unrelated user work.


## 19. Comments

Write comments only when they explain something that is not obvious from the code.

Good comments explain:

- why a workaround exists
- why a performance decision was made
- why unusual behavior is necessary

Do not narrate obvious code.

Avoid excessive comments generated purely for explanation.


## 20. Communication

Keep explanations concise.

After completing a task, report:

- what changed
- important implementation decisions
- what was reused or adapted from external sources, if applicable
- what was verified
- any meaningful remaining issue

Do not provide a long tutorial unless requested.

The code is the primary deliverable.


## 21. Final Standard

Before finishing, ask:

Does it work?

Does it preserve existing functionality?

Does it match the project's design?

Does it work on mobile?

Did I reuse existing project code where appropriate?

Did I check for an existing proven solution before rebuilding substantial functionality from scratch?

Is the implementation simpler than it needs to be?

Did I introduce unnecessary dependencies or abstractions?

Did I verify the result?

Would an experienced engineer consider this clean and reasonable?

If the answer to any important question is no, improve it before finishing.


## Session Continuity

For any task expected to take more than a few minutes:

- Update `PROGRESS.md` after each major stage.
- Do not rely only on conversation history for important state.
- Before ending a turn with unfinished work, record the exact next step in `PROGRESS.md`.
- If a tool call, build, or test fails, record the failure and its likely cause before continuing.
- If the task is interrupted by usage limits, preserve enough state in `PROGRESS.md` for a fresh Codex session to resume without repeating completed work.

When resuming:

- Read `AGENTS.md`.
- Read `PROGRESS.md`.
- Check `git status`.
- Inspect the actual files before trusting old progress notes.
- Continue from the latest verified unfinished step.


## Before Ending an Unfinished Task

If the current task is not fully complete before the session ends:

- Update `PROGRESS.md` with the latest completed work.
- Record any current errors or blockers.
- Record the exact next step.
- Record important external repositories or libraries currently being used as references.
- Make sure another Codex session can resume without relying on conversation history.

## GitHub Delivery

When a project or major task is fully completed and verified:

- Check `git status`.
- Preserve unrelated user changes.
- Stage only the files relevant to the completed work.
- Create a clear Git commit when appropriate.
- If the project already has a GitHub remote, push the completed work to it when the user has authorized GitHub publishing for this project.
- If no GitHub repository exists yet, use GitHub CLI (`gh`) when available to create the repository and configure `origin`.
- Verify that the push succeeded.
- Report the repository and branch that were pushed.

Before pushing:

- Run the relevant build/tests/checks.
- Do not push broken or unverified work.
- Never force-push unless explicitly instructed.
- Never overwrite remote history.
- Never expose `.env`, credentials, API keys, tokens, or secrets.
- Respect `.gitignore`.

Use the existing authenticated GitHub CLI/session instead of asking for credentials again.
