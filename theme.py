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
