#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import conf_server_gui as conf
import discovery
import functools
import pprint
import pygame
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple
if TYPE_CHECKING:
    from typing_extensions import Final


_I2 = Tuple[int, int]
_I4 = Tuple[int, int, int, int]
_F2 = Tuple[float, float]

IS_OSX: Final = (sys.platform.lower() == "darwin")

TEAM_CNT: Final = len(conf.TEAM_LIST)
LINE_H: Final = conf.H // TEAM_CNT
FONT_SIZE: Final = min(150, int(LINE_H // 1.5))

pygame.init()
DIR: Final = Path(__file__).resolve().parent
FONTDIR: Final = DIR/"resources/fonts"
FONT1: Final = pygame.font.Font(FONTDIR/conf.FONT1_FILENAME, FONT_SIZE)
FONT2: Final = pygame.font.Font(FONTDIR/conf.FONT2_FILENAME, FONT_SIZE)


@functools.lru_cache(maxsize=1024)
def _team_redraw_inner(name: str, score: int, fg: _I4) -> Tuple[pygame.surface.Surface, pygame.surface.Surface]:
    n_tag = FONT1.render(name, False, fg)
    s_tag = FONT2.render(str(score), False, fg)
    return n_tag, s_tag


def major_mod_pressed(e: pygame.event.Event) -> bool:
    if IS_OSX:
        return not not (e.mod & pygame.KMOD_GUI)
    else:
        return not not (e.mod & pygame.KMOD_CTRL)


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
        self.mirror = discovery.Mirror(conf.MCAST_GROUP, [conf.MCAST_PORT], conf.MCAST_KEY1, conf.MCAST_KEY2)
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
        self.sock.bind(("0.0.0.0", conf.PORT))
        self.sock.settimeout(0)
        self.mirror.start()

        print(f"[Ready ip=*:{conf.PORT}, mcast={conf.MCAST_GROUP}:{conf.MCAST_PORT}]")
        print("Server IP suggestions:")
        pprint.pprint(socket.gethostbyname_ex(socket.gethostname()))

    def exec_run(self) -> None:
        self.redraw_each_team()
        while self.is_running:
            events = pygame.event.get()
            f_update = False
            for e in events:
                if e.type == pygame.QUIT:
                    self.shutdown_from("pygame.QUIT (GUI)")
                elif e.type == pygame.KEYDOWN:
                    if major_mod_pressed(e) and e.key == pygame.K_r:
                        f_update = True
                        self.reset_team_scores()

            while True:
                c: bytes
                try:
                    c, _ = self.sock.recvfrom(1024)
                except socket.error:
                    break
                for t in self.teams:
                    if (
                            (conf.FIRST_BYTE_MODE and c[0] == t.uid[0])
                            or (conf.FOUR_BYTE_MODE and c[:4] == t.uid[:4])
                            or (conf.FULL_MATCH_MODE and c == t.uid)):
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
                t.draw(self.window, self.xmargin, i * self.h, self.h, conf.COLOR_BG1 if i & 1 else conf.COLOR_BG2)
            pygame.display.flip()

    def exec_end(self) -> None:
        self.sock.close()
        self.mirror.stop()

    def redraw_each_team(self) -> None:
        for i, t in enumerate(self.teams):
            t.redraw_inner(conf.COLORMAP_FG.get(i, conf.COLOR_TEXT))

    def reset_team_scores(self) -> None:
        for t in self.teams:
            t.score = 0


def main() -> None:
    app = App((conf.W, conf.H), LINE_H, int(conf.W * .15), conf.TEAM_LIST)
    app.exec_()


if __name__ == '__main__':
    main()
