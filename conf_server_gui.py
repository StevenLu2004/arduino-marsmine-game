from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing_extensions import Final

# ============
# UID Matching
# ============
# Match only 1st byte of UID (legacy mode)
FIRST_BYTE_MODE: Final = True
# Match 4 head bytes of UID
FOUR_BYTE_MODE: Final = False
# Require exact match for UID
FULL_MATCH_MODE: Final = False
# Team list
TEAM_LIST: Final = [
    ("Team1", b"1UID"),
    ("Team2", b"2UID"),
    ("Team3", b"3UID"),
    ("Team4", b"4UID"),
    ("Team5", b"5UID"),
    ("Team6", b"6UID"),
]

# ======
# Server
# ======
# Main socket port
PORT: Final = 88
# Multicast group
MCAST_GROUP: Final = "224.0.3.141"
# Multicast port
MCAST_PORT: Final = 817
# Key for authenticating client (mine)
MCAST_KEY1: Final = b"q\xfe\xce\x92"
# Key for authenticating server (discovery.Mirror)
MCAST_KEY2: Final = b"\x1f|\xde\xe9"

# ===============
# UI, Text & Font
# ===============
# Screen size
W: Final = 1920
H: Final = 1080
# Team name text font
FONT1_FILENAME: Final = 'Ubuntu-Regular.ttf'
# Score text font
FONT2_FILENAME: Final = 'Ubuntu-Regular.ttf'

# ======
# Colors
# ======
# rgb(14,16,46) Alternating bg color 1
COLOR_BG1: Final = (14, 16, 46, 255)
# rgb(44,48,94) Alternating bg color 2
COLOR_BG2: Final = (44, 48, 94, 255)
# rgb(255,221,0) First place
COLOR_GOLD: Final = (255, 221, 0, 255)
# rgb(212,212,212) Second place
COLOR_SILVER: Final = (212, 212, 212, 255)
# rgb(224,166,85) Third place
COLOR_BRONZE: Final = (224, 166, 85, 255)
# rgb(92,184,162) >3 place
COLOR_TEXT: Final = (92, 184, 162, 255)
# Color map for first few places; others will be COLOR_TEXT
COLORMAP_FG: Final = {0: COLOR_GOLD, 1: COLOR_SILVER, 2: COLOR_BRONZE}
