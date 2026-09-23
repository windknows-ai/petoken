# Petoken v1.2.0 release notes

These are the notes published with the v1.2.0 GitHub Release. The release artifact is `Petoken-v1.2.0-Windows-x64.zip` (Windows x64); verify its SHA-256 against the hashes listed on the release page before running it.

Petoken v1.2.0

Highlights:
- Dual-provider companion support for Codex and OpenCode.
- Manual and automatic provider selection with provider-isolated state.
- OpenCode Active Session presentation and raw usage analytics.
- Source-backed OpenCode Recorded Total for verified compatible versions.
- Provider-local analytics and recorded cost handling.
- Improved concurrency, stale-result protection, lifecycle tracking, and shutdown safety.
- OpenCode unsupported quota/context UI is hidden rather than fabricated.
- Existing Codex behavior and V1.1 compatibility preserved.

Windows x64 release artifact:
Petoken-v1.2.0-Windows-x64.zip

SHA-256:
D6AA69071D1123A65AC4D93BDB3035A9DEF6AC0D583B1D54ED0D3BDC9C6F7270

Contained petoken.exe SHA-256:
3E5D04C405D6EBA84E8BD43100D1E2B1441F827BC79436C289E161FBBE34243F

Known non-blocking limitations:
- Pre-existing compact-layout overlap can occur at minimum width with very large totals.
- Fractional-DPR / physical drag behavior is primarily unit-covered.
- Under sustained heavy OpenCode database writes, activity may conservatively become unknown and recover on the next stable poll.
