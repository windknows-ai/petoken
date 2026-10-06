# Petoken v1.7.1

A fix for the question card beside the character.

- When Claude Code asks several long questions, the card no longer grows past
  the screen or lets the text overlap the options: the questions scroll inside
  the card (at most 60 % of the screen height) and long option labels wrap
  onto up to three lines instead of being cut. The answer sent to Claude is
  still the exact option label.

v1.7.0 and later offer this update by themselves (Settings > General >
Updates). Otherwise download `Petoken-Setup-v1.7.1.exe` and verify it against
`SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.7.1).
Everything in [v1.7.0](RELEASE_NOTES_v1.7.0.md) is unchanged.
