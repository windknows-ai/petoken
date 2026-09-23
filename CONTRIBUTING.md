# Contributing

## Welcome contributions

- **Bug reports**: file an issue with the `Bug report` template (Windows version, petoken version, tracking provider, reproduction steps).
- **Feature ideas**: file an issue with the `Feature request` template and describe the usage scenario.
- **Code**: pull requests against `main` — Python 3.13, Qt/PySide6 desktop app. New behavior needs focused tests; run the full suite (`python -m unittest discover -s tests -v`) and `git diff --check` before submitting.
- **Docs and translations**: README, USAGE_MODEL, ROADMAP, and UI string fixes (see `localization.py`).
- **Examples and screenshots**: only synthetic or fully desensitized data — never real session titles, project paths, or cost figures.

## Not accepted

- Credentials, tokens, log excerpts, or private configuration.
- Real usage screenshots containing session titles, project paths, or undisguised costs.
- Unverified capability claims (describe unreleased ideas as proposals, never as available).

## PR conventions

- One PR does one thing; title it clearly (e.g. `fix: ...`, `docs: ...`).
- Screenshot/example PRs must state the data source (synthetic or desensitized).
