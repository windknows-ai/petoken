"""Central visual tokens for the petoken desktop companion.

Muted paper, dusty lavender and blue pencil accents give the native companion
the feel of a small desktop toy. Outlined controls and notebook tabs share these
tokens across the workbench, usage cards, settings and activity bubbles.
"""
from __future__ import annotations

# Core roles.
INK = '#40374A'
MUTED = '#514959'
ICE = '#36546C'
VIOLET = '#58436C'
BG = '#C9C5CF'

# Surfaces: dusk paper and a warm desk, without large white fields.
SURFACE_TOP = '#D8CFDF'
SURFACE_BOTTOM = '#CFCFDC'
CARD = '#D9D2C7'
TABLE_BG = '#E2DDD5'
TABLE_ALT = '#DAD3DF'
TABLE_HEADER = '#C8BDD1'
BADGE_BG = '#CBBAD8'
CONTROL_BG = '#E2DDD5'
PRIMARY_BG = '#C5B2D5'
CHECK_BG = '#B9C7D4'

# Borders and separators.
BORDER = '#918498'
BORDER_SOFT = '#A69BAA'
BORDER_CONTROL = '#918498'
TRACK = '#B4A8BD'
DIVIDER = '#B5ABBD'
GRID = '#BCB2C3'

# Interaction.
TAB_PANE_BORDER = '#918498'
TAB_SELECTED_BG = '#B9C7D4'
HOVER_BG = '#D1C4DC'
HOVER_BORDER = '#70617F'
CHECKED_BG = '#C5B2D5'
MENU_BG = '#DED8CE'
MENU_SELECTED = '#B9C7D4'
TOOLTIP_BG = '#E2DDD5'
TOOLTIP_BORDER = '#918498'
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
