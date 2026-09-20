# petoken v1.1.0

Major visual and interaction refinement of the petoken desktop companion.

## Highlights

- Daily / Token modes: the pet shows live Codex information only while a Codex project is actively running, and returns to a clean pet-only Daily Mode otherwise.
- Working Context: the Token view follows one verified working session, binding project identity, model, context usage, and that session's Token totals together.
- Global / Project / Conversation scopes with fork-deduplicated, nullable token accounting.
- Full / Compact Token number formatting with K / M / B / T suffixes and explicit units in Token Analytics.
- Bilingual UI: Simplified Chinese / English with live switching and a persistent preference.
- Estimated Cost in USD / CAD / EUR / CNY from one internal price table (USD-canonical conversion via dated Bank of Canada rates); unknown prices stay honestly partial, and manual pricing controls are gone from normal Settings.
- Compact two-line Token card (project · status + live Tokens) and a grouped, resizable expanded panel.
- V1.1 chibi character set: idle, two reactive typing frames, distinct Codex Working pose, microphone, music, and guitar — all sharing one ground anchor and DPI-aware rendering.
- Reactive typing: timestamp-only key pulses alternate tap phases with inactivity decay; no key content is ever read or stored.
- Music subtitle capability: shows the platform-provided SMTC subtitle line when a media app supplies one, otherwise Music Mode works normally with no placeholder. Stated accurately: availability depends on the media app providing subtitle metadata.
- Responsive panel (300–480 × 380–800 with size persistence), Reset to Defaults in Settings, and a centralized visual theme.

## Privacy guarantees

Local-first numeric/metadata reading only. No transcript export, model calls, keystroke content, audio recording, subtitle persistence, or uploads. The V1.0 idle asset is preserved byte-for-byte as history and fallback.

## Verification

- 170+ unit/UI tests (accounting, scopes, Working Context, modes, localization, pricing/currency, geometry, assets, typing, responsive, acceptance edge cases).
- Live quota/token/FX verification, isolated zh_CN and English smokes, render QA at 100–200% DPI, frozen-executable smoke, and PyInstaller packaging verification.
