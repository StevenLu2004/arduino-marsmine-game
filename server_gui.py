#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import discovery
import functools
import pprint
import pygame
import socket
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple
if TYPE_CHECKING:
    from typing_extensions import Final


_I2 = Tuple[int, int]
_I4 = Tuple[int, int, int, int]
_F2 = Tuple[float, float]

COLOR_BG1: Final = (14,16,46,255)  # rgb(14,16,46) Alternating bg color 1
COLOR_BG2: Final = (44,48,94,255)  # rgb(44,48,94) Alternating bg color 2
COLOR_GOLD: Final = (255,221,0,255)  # rgb(255,221,0) First place
COLOR_SILVER: Final = (212,212,212,255)  # rgb(212,212,212) Second place
COLOR_BRONZE: Final = (224,166,85,255)  # rgb(224,166,85) Third place
COLOR_TEXT: Final = (92,184,162,255)  # rgb(92,184,162) >3 place
COLORMAP_FG: Final = {0: COLOR_GOLD, 1: COLOR_SILVER, 2: COLOR_BRONZE}  # For convenience
FONT1_FILENAME = 'Ubuntu-Regular.ttf'  # Team name text font
FONT2_FILENAME = 'Ubuntu-Regular.ttf'  # Score text font
FIRST_BYTE_MODE: Final = True  # Match only 1st byte of UID (legacy mode)
FOUR_BYTE_MODE: Final = False  # Match 4 head bytes of UID
FULL_MATCH_MODE: Final = False  # Require exact match for UID
PORT: Final = 88  # Main socket port
MCAST_GROUP: Final = "224.0.3.141"  # Multicast group
MCAST_PORT: Final = 817  # Multicast port
MCAST_KEY1: Final = b"q\xfe\xce\x92"
MCAST_KEY2: Final = b"\x1f|\xde\xe9"


DIR: Final = Path(__file__).resolve().parent
FONTDIR: Final = DIR/'resources/fonts'
FONT1: Final = pygame.font.Font(FONTDIR/'Ubuntu-Regular.ttf', 120)
FONT2: Final = pygame.font.Font(FONTDIR/'Ubuntu-Regular.ttf', 120)

pygame.init()


@functools.lru_cache(maxsize=1024)
def _team_redraw_inner(name: str, score: int, fg: _I4) -> Tuple[pygame.surface.Surface, pygame.surface.Surface]:
    n_tag = FONT1.render(name, False, fg)
    s_tag = FONT2.render(str(score), False, fg)
    return n_tag, s_tag


class Team:

    def __init__(self, name: str, uid: bytes) -> None:
        self.name = name
        self.uid = uid
        self.score: int = 0
        self.prev_score: int = 0
        self.n_tag: pygame.surface.Surface
        self.s_tag: pygame.surface.Surface

    def redraw_inner(self, fg: _I4) -> None:
        self.n_tag, self.s_tag = _team_redraw_inner(self.name, self.score, fg)

    def draw(self, window: pygame.surface.Surface, xmargin: int, y: int, h: int, bg: _I4) -> None:
        W, H = window.get_size()
        window.fill(bg, (0, y, W, h))
        nw, nh = self.n_tag.get_size()
        nx = xmargin
        ny = y + (h - nh + 1) // 2
        window.blit(self.n_tag, (nx, ny))
        sw, sh = self.s_tag.get_size()
        sx = W - xmargin - sw
        sy = y + (h - sh + 1) // 2
        window.blit(self.s_tag, (sx, sy))

    def key_for_sort(self) -> Tuple[int, int]:
        return self.score, self.prev_score


class App:
    def __init__(self, dims: _I2, h: int, xmargin: int, teams: List[Tuple[str, bytes]]) -> None:
        self.dims: Final = dims
        self.h: Final = h
        self.xmargin = xmargin
        self.window: pygame.surface.Surface
        self.sock: socket.socket
        self.mirror = discovery.Mirror(
            MCAST_GROUP, [MCAST_PORT], MCAST_KEY1, MCAST_KEY2)
        self.teams = [Team(name, uid) for name, uid in teams]
        self.is_running = False

    def shutdown_from(self, src: str) -> None:
        self.is_running = False
        print(f"\r[Shutdown from {src}]")

    def exec_(self) -> None:
        self.exec_init()
        self.is_running = True
        self.exec_run()
        self.exec_end()

    def exec_init(self) -> None:
        self.window = pygame.display.set_mode(self.dims, flags=pygame.FULLSCREEN, vsync=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.settimeout(0)
        self.mirror.start()

        print(f"[Ready ip=*:{PORT}, mcast={MCAST_GROUP}:{MCAST_PORT}]")
        print("Server IP suggestions:")
        pprint.pprint(socket.gethostbyname_ex(socket.gethostname()))

    def exec_run(self) -> None:
        self.redraw_each_team()
        while self.is_running:
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.shutdown_from("pygame.QUIT (GUI)")

            f_update = False
            while True:
                c: bytes
                try:
                    c, _ = self.sock.recvfrom(1024)
                except socket.error:
                    break
                for t in self.teams:
                    if (
                            (FIRST_BYTE_MODE and c[0] == t.uid[0])
                            or (FOUR_BYTE_MODE and c[:4] == t.uid[:4])
                            or (FULL_MATCH_MODE and c == t.uid)):
                        t.score += 1
                        f_update = True
                        break

            if f_update:
                self.teams.sort(key=Team.key_for_sort, reverse=True)
                for t in self.teams:
                    t.prev_score = t.score
                self.redraw_each_team()

            self.window.fill((0,0,0,0))
            for i, t in enumerate(self.teams):
                t.draw(self.window, self.xmargin, i * self.h, self.h, COLOR_BG1 if i & 1 else COLOR_BG2)
            pygame.display.flip()

    def exec_end(self) -> None:
        self.sock.close()
        self.mirror.stop()

    def redraw_each_team(self) -> None:
        for i, t in enumerate(self.teams):
            t.redraw_inner(COLORMAP_FG.get(i, COLOR_TEXT))


def main() -> None:
    team_list = [
        ("Team1", b"aaaa"),
        ("Team2", b"bbbb"),
        ("Team3", b"cccc"),
        ("Team4", b"dddd"),
        ("Team5", b"eeee"),
        ("Team6", b"ffff"),
        ("Team7", b"gggg"),
        ("Team8", b"hhhh"),
        ("Team9", b"iiii"),
        ("TeamA", b"jjjj"),
        ("TeamB", b"kkkk"),
        ("TeamC", b"llll"),
    ]
    W, H = 3360, 2100
    app = App((W, H), H // len(team_list), int(W * .2), team_list)
    app.exec_()


if __name__ == '__main__':
    main()
