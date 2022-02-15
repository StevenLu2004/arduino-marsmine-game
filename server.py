#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discovery
import pprint
import socket


PORT = 88
MCAST_GROUP = "224.0.3.141"
MCAST_PORT = 817
MCAST_KEY1 = b"q\xfe\xce\x92"
MCAST_KEY2 = b"\x1f|\xde\xe9"


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    mirror = discovery.Mirror(MCAST_GROUP, [MCAST_PORT], MCAST_KEY1, MCAST_KEY2)
    mirror.start()

    print(f"Server listening on *:{PORT} (multicast {MCAST_GROUP}:{MCAST_PORT})")
    print("Server IP suggestions:")
    pprint.pprint(socket.gethostbyname_ex(socket.gethostname()))
    while True:
        try:
            msg, peer = sock.recvfrom(64)
            print(peer, ':', msg)
        except KeyboardInterrupt:
            break

    print("\rServer stopped")
    sock.close()


if __name__ == '__main__':
    main()
