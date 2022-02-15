# -*- coding: utf-8 -*-
# This file originally dedicated to developing multiplayer games on LAN.
# Author: Tongyu (Steven) Lu

from __future__ import annotations
import logging
import socket
import threading
import time
from typing import Any, Callable, Dict, Sequence, Tuple


class Mirror:
    def __init__(self, mgroup: str, port: Sequence[int], key: bytes, info: bytes, *, timeout=1.0, exc=(3, 2.0), autostart=False) -> None:
        """
        :param mgroup: Multicast group ip (receive all messages sent to this ip)
        :param port: A list of available ports that will be used
        :param key: Identify the application
        :param info: Information sent to the client after connection is established
        :param timeout: Timeout in seconds for receiving
        :param exc: Number of retries until slow-down, and duration of delay
        :param autostart: Whether the server will automatically start listening for requests
        """
        self.mgroup = mgroup
        self.port = port
        self.key = key
        self.info = info
        self.timeout = timeout
        self.exc = exc

        self.sock: socket.socket | None = None
        self.status = 0

        self.thread: threading.Thread | None = None
        self.running = False
        self.stopping = False
        self.reflecting = False

        if autostart:
            self.start()

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.mgroup}, {self.port})"

    def bind_sock(self) -> None:
        assert self.sock is not None
        for p in self.port:
            try: self.sock.bind(('', p)); return
            except Exception: pass
        raise RuntimeError('No available port')

    def reconnect(self) -> int:
        membership = socket.inet_aton(self.mgroup) + socket.inet_aton('0.0.0.0')
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.settimeout(self.timeout)
            self.bind_sock()
        except Exception as e:
            self.sock = None
            logging.warning(f"{self}.reconnect(): unexpected exception", exc_info=e)
            return 1

        return 0

    def disconnect(self) -> int:
        if self.sock is not None:
            try: self.sock.close()
            except: pass
        self.sock = None
        return 0

    def threadfunc(self) -> None:
        self.reflecting = True
        self.status = 0
        if self.reconnect():
            self.status = 1
            self.reflecting = False
            return

        assert self.sock is not None

        em_cnt = self.exc[0]
        while self.running:
            try:
                msg, peer = self.sock.recvfrom(len(self.key))
                if msg == self.key:
                    self.sock.sendto(self.info, peer)
                em_cnt = self.exc[0]
            except socket.timeout:
                continue
            except Exception as e:
                logging.warning(f"Mirror @ {(self.mgroup, self.port)} threadfunc met unexpected exception", exc_info=e)
                em_cnt -= 1
                if em_cnt == 0:
                    em_cnt = 1
                    time.sleep(self.exc[1])

        self.reflecting = False

    def start(self) -> int:
        if self.running or self.stopping:
            return 1
        self.running = True
        self.thread = threading.Thread(target=self.threadfunc, daemon=True)
        self.thread.start()
        return 0

    def _cleanstop(self, cb: Callable[[int, Mirror], Any] | None=None) -> None:
        self.running = False
        if self.thread is not None: self.thread.join()
        self.thread = None
        self.disconnect()
        if cb is not None:
            cb(0, self)
        self.stopping = False

    def stop(self, cb: Callable[[int, Mirror], Any] | None=None) -> int:
        if self.stopping or not self.running:
            return 1
        self.stopping = True
        cleanstop_thread = threading.Thread(target=self._cleanstop, args=(cb,))
        cleanstop_thread.start()
        return 0

    def __del__(self):
        self.stop()


class Beacon:
    def __init__(self, mgroup: str, port: Sequence[int], key: bytes, *, timeout=1.0, exc=(3, 2.0), autostart=False) -> None:
        """
        :param mgroup: Multicast group ip (receive all messages sent to this ip)
        :param port: A list of available ports that will be used
        :param key: Identify the application
        :param timeout: Timeout in seconds for receiving
        :param exc: Number of retries until slow-down, and duration of delay
        :param autostart: Whether the client will automatically start sending requests
        """
        self.mgroup = mgroup
        self.port = port
        self.key = key
        self.timeout = timeout
        self.exc = exc

        self.sock: socket.socket | None = None
        self.status = 0
        self.responses: Dict[Tuple[str, int], bytes] = {}

        self.thread: threading.Thread | None = None
        self.running = False
        self.stopping = False
        self.waiting = False

        if autostart:
            self.start()

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.mgroup}, {self.port})"

    def _ping(self) -> None:
        assert self.sock is not None
        for p in self.port:
            self.sock.sendto(self.key, (self.mgroup, p))

    def ping(self, clear=False) -> int:
        assert self.sock is not None
        if clear:
            self.responses = {}
        fail = 0
        for p in self.port:
            try:
                self.sock.sendto(self.key, (self.mgroup, p))
            except:
                fail += 1
        return fail

    def reconnect(self, ping=True) -> int:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(self.timeout)
            if ping:
                self._ping()
        except Exception as e:
            self.sock = None
            logging.warning(f"{self}.reconnect(): unexpected exception", exc_info=e)
            return 1
        return 0

    def disconnect(self) -> int:
        if self.sock is not None:
            try: self.sock.close()
            except: pass
        self.sock = None
        return 0

    def threadfunc(self) -> None:
        self.waiting = True
        self.status = 0
        if self.reconnect():
            self.status = 1
            self.waiting = False
            return

        assert self.sock is not None

        em_cnt = self.exc[0]
        while self.running:
            try:
                msg, peer = self.sock.recvfrom(4096)
                self.responses[peer] = msg
                em_cnt = self.exc[0]
            except socket.timeout:
                continue
            except Exception as e:
                logging.warning(f"{self}.threadfunc(): unexpected exception", exc_info=e)
                em_cnt -= 1
                if em_cnt == 0:
                    em_cnt = 1
                    time.sleep(self.exc[1])

        self.waiting = False

    def start(self, clear=True) -> int:
        if self.running or self.stopping:
            return 1
        self.running = True
        if clear:
            self.responses = {}
        self.thread = threading.Thread(target=self.threadfunc, daemon=True)
        self.thread.start()
        return 0

    def _cleanstop(self, clear=False, cb: Callable[[int, Beacon], Any] | None=None) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join()
        self.thread = None
        self.disconnect()
        if clear:
            self.responses = {}
        if cb is not None:
            cb(0, self)
        self.stopping = False

    def stop(self, clear=False, cb: Callable[[int, Beacon], Any] | None=None) -> int:
        if self.stopping or not self.running:
            return 1
        self.stopping = True
        cleanstop_thread = threading.Thread(target=self._cleanstop, args=(clear, cb))
        cleanstop_thread.start()
        return 0

    def __del__(self) -> None:
        self.stop(clear=True)
