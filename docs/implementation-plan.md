# petoken implementation plan

Historical initial delivery plan. Current V1.3 work follows
`../PETOKEN_CODEX_EXECUTION_STATE.md`; publication instructions below do not
authorize a push or release. Human visual acceptance and separate publication
authorization remain required.

Goal: deliver a double-clickable, Skirk-colored Windows usage companion and publish source and a binary to the existing GitHub repository.

Architecture: Python standard library reads Codex SQLite metadata read-only and incrementally consumes numeric JSONL events. Windows UI Automation supplies the active task title. A hidden Codex app-server child performs only initialization and account/rateLimits/read. Qt renders the panel on the UI thread; background workers handle I/O. Spec: ../DESIGN.md.

1. Data core (`usage.py`, `tests/test_usage.py`): test cost math, deduplication, model changes, incomplete lines, task selection and quota expiry, then implement. Use actual local schemas as evidence; retain unknown states.
2. Integrations (`desktop.py`): active accessible document title, single hidden RPC child with timeout/backoff, public FX refresh with last-known date. Verify against this installed Codex without changing its tasks or authentication.
3. UI (`widget.py`): native controls, original ice spirit, data worker, task picker, scope and pricing settings, tray and saved placement. Render at normal and high DPI and exercise controls.
4. Delivery: unit + live checks, frozen app smoke test, README, MIT license, third-party notice, release build script. Scan tracked files for local/private data; push to the authorized repository and attach a Windows zip to a GitHub release. Keep its existing visibility.
