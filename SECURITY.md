# Security

## Design principles

- The Codex integration reads **local task and numeric usage metadata**. It never exports transcripts, credentials, prompts, responses, or tool contents, and it never uploads local usage anywhere.
- Current V1.3 reads Codex only; no OpenCode adapter is registered, imported, instantiated or polled. Isolated historical adapter tests retain the former allowlisted-column parsing evidence.
- Media titles/artists/subtitle metadata are memory-only for the music display and are never stored.
- The unreleased V1.4 workbench stores only user-entered project names/folder paths,
  todos, plain-text notes and explicit Codex task-to-project links in a separate
  local SQLite database. It does not scan project folders, parse new chat content,
  upload or encrypt these records. Its disposable QA preview never uses this
  personal database. Back up the complete database while Petoken is closed.

## Reporting a vulnerability

If you find a privacy or security issue (e.g. the app reading more than documented, or a release package containing unexpected files), please open a GitHub issue with the `security` label, or contact the maintainer privately via the email listed on the GitHub profile. Do **not** post suspected credentials or personal data in public issues.

## Release integrity

Each GitHub Release lists the executable and ZIP SHA-256 hashes. After downloading, you may verify the archive hash before running it.
