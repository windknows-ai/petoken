# Petoken v2.5.0

The Stardust Wardrobe: spend the stardust you earn on outfits, weapons and decorations she really wears, wish on falling stars, and a redrawn, lighter app.

## Added

- **Stardust Wardrobe** (right-click her › Stardust Wardrobe, or the tray menu): its own window with three pages.
  - **Closet**: a mirror where she tries on anything at once, owned or not, in a few poses and at the size you like. Pick a piece to wear or take it off, nudge its size and angle by hand, save whole looks and put them back on in one click.
  - **Shop**: 88 items in three sets — 8 outfits, 20 weapons, 60 decorations (head, back, ground, a floating buddy, task-star styles) — in five rarities: Stars 200, Moon 800, Sun 1800, Galaxy 4500 stardust; Starsea pieces only come from wishes. Four picks each day, each with a discount you draw from face-down cards (60–95 %), for that day. A few items are only on sale at certain times of year.
  - **Milestones**: the Meteor and Aurora rings and the Starsea form, unlocked by the stardust you have ever earned. Spending never takes them back.
- **Outfits she really wears**: every outfit has its own pictures for her actions; the Frost coat and the Starsea gown come in several tiers, each richer than the one below. Weapons sit in her hand and hide when her hands are out of sight; decorations follow her head, back and feet, and head and back pieces are put away while she lies down.
- **Wishes**: 300 stardust for one, 3000 for ten. Falling stars cross the night sky and you fly her to them with the mouse or the arrow keys to catch them; each rarity opens in its own colours, with tall result cards and sounds. Odds are shown in the window (Starsea 0.6 %, Galaxy 1.5 %, Sun 4 %, Moon 15 %, Stars 78.9 %); a Starsea piece within 60 wishes, at least one Moon piece in every ten, and 100 stardust back for a duplicate.
- **More ways to earn stardust**: a daily sign-in (+10, +50 for seven days in a row), three AI tasks in a day (+20), keeping your weekly goal (+30), completing a set in the collection book (+100); wearing a matching outfit, weapon and decoration lights a soft glow behind her. A heavy day of work still earns about 600 at most.
- **Every action in every form**: the night pajamas, the game armour and the Starsea form now have their own pictures for all 41 actions.

## Changed

- **The whole app is redrawn** in Qt Quick: the usage panel, the workbench, Settings, dialogs and the cards beside her share one calm, readable look with clear text, icons and empty-list hints.
- **Lighter and smoother**: about half the CPU while idle, pictures loaded only when first needed, the star ring drawn once and reused, 30 frames a second when nothing moves fast. The workbench opens in about a second and the wardrobe faster than before.
- Reports are read in their own background process, so the app stays responsive while it reads long Codex and Claude logs.

## Fixed

- No freeze when an AI task finishes: its file recap and the todo outcome are read in the background.
- Quitting while a report is being read no longer hangs.
- Her outfit no longer flickers between pictures while she is dragged.
- Decorations no longer float in the wrong place when she lies down or reads.
- Closing the wardrobe in the middle of a wish ends the wish show instead of leaving it running unseen.
- Only one Settings window and one focus dialog open at a time.
- Lists and scroll areas no longer flicker their scroll bar on and off at certain sizes.

## Install

Download `Petoken-Setup-v2.5.0.exe`, check it against `SHA256SUMS.txt`, and run it. Petoken 2.x updates itself when automatic updates are on.
