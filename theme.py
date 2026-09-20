"""Central visual tokens for the petoken desktop companion.

One compact palette source (spec 04: dark navy / violet / cyan). Components
reference these names instead of scattering hex literals, so the visual
language stays consistent. Values match the verified V1.0 direction; this
module centralizes them without redesigning anything by itself.
"""
from __future__ import annotations

# Core roles.
INK = '#EEF2FF'        # primary text, near-white
MUTED = '#A7AEC8'      # secondary text, cool gray-lavender
ICE = '#91E4F2'        # live / positive accent, ice cyan
VIOLET = '#B9A7F8'     # emphasis accent, soft lavender
BG = '#171B32'         # main background, very dark navy

# Surfaces (slightly lighter navy cards/panels).
SURFACE_TOP = '#242641'
SURFACE_BOTTOM = '#22243D'
CARD = '#232740'
TABLE_BG = '#1C2139'
TABLE_ALT = '#242B45'
TABLE_HEADER = '#303752'
BADGE_BG = '#34304F'
CONTROL_BG = '#282D48'

# Borders (thin lavender/violet, never heavy).
BORDER = '#515473'
BORDER_SOFT = '#575076'
BORDER_CONTROL = '#555C80'
TRACK = '#33374F'      # progress-bar track
DIVIDER = '#3C405B'
GRID = '#3A415F'

# Interaction.
TAB_PANE_BORDER = '#4C5575'
TAB_SELECTED_BG = '#41486C'
HOVER_BG = '#383B57'
HOVER_BORDER = '#555A7B'
CHECKED_BG = '#34344F'
MENU_BG = '#232740'
MENU_SELECTED = '#3D4263'
TOOLTIP_BG = '#252B46'
TOOLTIP_BORDER = '#626A8C'
SCROLL_BG = BG

# Corner radii: one consistent set.
RADIUS_SURFACE = 23
RADIUS_CARD = 16
RADIUS_BADGE = 8
RADIUS_BUTTON = 8
RADIUS_BAR = 3

# Font stacks. Hierarchy comes from size/weight/spacing/contrast.
FONT_UI = '"Segoe UI","Microsoft YaHei UI"'
FONT_CJK = '"Microsoft YaHei UI"'
FONT_NUM = '"Cascadia Mono","Consolas"'
