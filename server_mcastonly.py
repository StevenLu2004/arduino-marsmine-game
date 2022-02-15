#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discovery
import pprint
import socket


MCAST_GROUP = "224.0.3.141"
MCAST_PORT = 817
MCAST_KEY1 = b"q\xfe\xce\x92"
MCAST_KEY2 = b"\x1f|\xde\xe9"


def main() -> None:
    mirror = discovery.Mirror(MCAST_GROUP, [MCAST_PORT], MCAST_KEY1, MCAST_KEY2)
    mirror.start()

    print(f"Server listening on multicast {MCAST_GROUP}:{MCAST_PORT}")
    print("Server IP suggestions:")
    pprint.pprint(socket.gethostbyname_ex(socket.gethostname()))
    if mirror.thread is not None:
        try: mirror.thread.join()  # hangs forever until ^C
        except KeyboardInterrupt: pass

    print("\rServer stopped")


if __name__ == '__main__':
    main()
