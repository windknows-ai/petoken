"""Central visual tokens for the petoken desktop companion.

Soft companion direction (V1.1 polish slice): the same dark navy / violet /
cyan family, but lifted, rounder, and calmer — a cute pet-companion surface
instead of a dense enterprise dashboard. Components reference these names
instead of scattering hex literals, so the visual language stays consistent.
"""
from __future__ import annotations

# Core roles.
INK = '#F0F3FF'        # primary text, near-white
MUTED = '#B3B9D4'      # secondary text, soft lavender-gray
ICE = '#91E4F2'        # live / positive accent, ice cyan
VIOLET = '#C0AEFA'     # emphasis accent, light lavender
BG = '#1C2140'         # main background, soft dark navy

# Surfaces (lifted lavender-tinted navy cards/panels).
SURFACE_TOP = '#2D3157'
SURFACE_BOTTOM = '#272B4D'
CARD = '#2B2F52'
TABLE_BG = '#21263F'
TABLE_ALT = '#292F52'
TABLE_HEADER = '#363D66'
BADGE_BG = '#3B3460'
CONTROL_BG = '#2D3252'

# Borders (soft lavender, defined but never harsh).
BORDER = '#5E628A'
BORDER_SOFT = '#6B6594'
BORDER_CONTROL = '#5F6690'
TRACK = '#3A4063'      # progress-bar track
DIVIDER = '#454B70'
GRID = '#434A70'

# Interaction.
TAB_PANE_BORDER = '#555C82'
TAB_SELECTED_BG = '#485074'
HOVER_BG = '#3E4468'
HOVER_BORDER = '#60668C'
CHECKED_BG = '#3A3A5C'
MENU_BG = '#2A2E50'
MENU_SELECTED = '#454B74'
TOOLTIP_BG = '#2B3052'
TOOLTIP_BORDER = '#6E76A0'
SCROLL_BG = BG

# Corner radii: one consistent set, rounder for the companion feel.
RADIUS_SURFACE = 26
RADIUS_CARD = 20
RADIUS_BADGE = 12
RADIUS_BUTTON = 10
RADIUS_BAR = 3

# Font stacks. Hierarchy comes from size/weight/spacing/contrast.
FONT_UI = '"Segoe UI","Microsoft YaHei UI"'
FONT_CJK = '"Microsoft YaHei UI"'
FONT_NUM = '"Cascadia Mono","Consolas"'
