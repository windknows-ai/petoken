"""Central visual tokens for the petoken desktop companion.

Silver-lavender hair and indigo clothing from the original artwork guide the
native companion palette. Large surfaces use dimmed silver to avoid glare;
outlined controls and notebook tabs retain the desktop toy treatment.
"""
from __future__ import annotations

# Core roles.
INK = '#231E56'
MUTED = '#484365'
ICE = '#324873'
VIOLET = '#483F86'
BG = '#BBB7CF'

# Original sampled hair #EEEBF6, clothing #231E56 and #483F86. Muted
# silver surfaces share that hue rather than introducing warm beige panels.
SURFACE_TOP = '#CFCBE2'
SURFACE_BOTTOM = '#C8C4DF'
CARD = '#D0CCE4'
TABLE_BG = '#D9D5EA'
TABLE_ALT = '#CDC9E1'
TABLE_HEADER = '#BCB5D5'
BADGE_BG = '#BCB2D8'
CONTROL_BG = '#D0CCE4'
PRIMARY_BG = '#BAB2DA'
CHECK_BG = '#B2BCDA'

# Borders and separators.
BORDER = '#81779F'
BORDER_SOFT = '#A098BC'
BORDER_CONTROL = '#81779F'
TRACK = '#ABA5C8'
DIVIDER = '#AAA3C5'
GRID = '#B5ADCE'

# Interaction.
TAB_PANE_BORDER = '#81779F'
TAB_SELECTED_BG = '#B2BCDA'
HOVER_BG = '#C4BDDE'
HOVER_BORDER = '#5E528B'
CHECKED_BG = '#BAB2DA'
MENU_BG = '#D0CCE4'
MENU_SELECTED = '#B2BCDA'
TOOLTIP_BG = '#D9D5EA'
TOOLTIP_BORDER = '#81779F'
SCROLL_BG = BG

# Corner radii: one consistent set, rounder for the companion feel.
RADIUS_SURFACE = 20
RADIUS_CARD = 12
RADIUS_BADGE = 12
RADIUS_BUTTON = 10
RADIUS_BAR = 3

# Font stacks. Hierarchy comes from size/weight/spacing/contrast.
FONT_UI = '"Segoe UI","Microsoft YaHei UI"'
FONT_DISPLAY = '"Segoe Print","Microsoft YaHei UI"'
FONT_CJK = '"Microsoft YaHei UI"'
FONT_NUM = '"Cascadia Mono","Consolas"'

# Per-provider task colors (V1.5): Codex is blue, Claude Code is gold.
# Stars use the full palette; the star ring and trails use ``ring`` so each
# stretch of the ring matches the stars nearest to it.
STAR_PALETTES = {
    'codex': dict(
        glow=((236, 244, 255, 170), (122, 170, 255, 100), (110, 150, 230, 0)),
        fill=('#e6f0ff', '#ffffff', '#cfe4ff', '#6f9fe8'),
        outline='#4f86e0',
        cuts=('#c9dcfb', '#8fb6f0', '#a9c5f2', '#f2f7ff'),
        halo=((140, 200, 255), (110, 160, 255)),
        body=((190, 214, 255), (245, 249, 255), (110, 160, 240)),
        inner=((216, 236, 255), (160, 205, 255)),
        ring=(112, 162, 255)),
    'claude': dict(
        glow=((255, 248, 230, 170), (255, 200, 90, 105), (230, 170, 60, 0)),
        fill=('#fff4d9', '#ffffff', '#ffe7ad', '#e0a93c'),
        outline='#c98f22',
        cuts=('#fbe3a8', '#f2c46a', '#f7d48a', '#fffaf0'),
        halo=((255, 214, 140), (240, 180, 80)),
        body=((255, 226, 160), (255, 250, 238), (226, 168, 60)),
        inner=((255, 241, 205), (255, 220, 140)),
        ring=(240, 182, 70)),
}


def star_palette(provider_id):
    """Task colors for one provider; unknown providers use Codex blue."""
    return STAR_PALETTES.get(provider_id, STAR_PALETTES['codex'])
