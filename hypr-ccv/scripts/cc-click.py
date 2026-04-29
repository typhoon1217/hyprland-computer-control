#!/usr/bin/env python3
"""Send pointer events to the sandbox via wayvnc (localhost:5999) using RFB.

Why this exists
---------------
ydotool writes to /dev/uinput, which is system-wide — clicks land on the
user's active seat, not necessarily on the sandbox. wayvnc, on the other
hand, drives the sandbox compositor through wlroots' virtual-pointer
protocol; it cannot leak to the user's main session.

This script speaks just enough of the RFB / VNC protocol to send
PointerEvent messages. No external libraries — just stdlib.

Usage
-----
    cc-click.py click 555 333                 # left click at (555, 333)
    cc-click.py click 555 333 --button right  # right click
    cc-click.py click 555 333 --button middle # middle click
    cc-click.py move 100 200                  # move only, no click
    cc-click.py double 555 333                # double click
    cc-click.py scroll 555 333 -3             # scroll down 3 ticks
    cc-click.py scroll 555 333 5              # scroll up 5 ticks
    cc-click.py drag 100 200 400 500          # drag from src to dst

Coordinates are in the sandbox's virtual screen (1920x1080 at origin).

Caveats
-------
- wayvnc must be running (started by start.sh when CC_VNC=1).
- Each invocation opens a fresh RFB session and tears it down. Slow if
  scripted in a tight loop; cache by editing this script if needed.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import time

VNC_HOST = "127.0.0.1"
VNC_PORT = 5999

# RFB PointerEvent button-mask bits
BTN_LEFT = 1 << 0
BTN_MIDDLE = 1 << 1
BTN_RIGHT = 1 << 2
BTN_SCROLL_UP = 1 << 3
BTN_SCROLL_DOWN = 1 << 4

BUTTON_MAP = {"left": BTN_LEFT, "middle": BTN_MIDDLE, "right": BTN_RIGHT}


class RFBClient:
    """Minimal RFB 3.8 client — handshake + PointerEvent only."""

    def __init__(self, host: str = VNC_HOST, port: int = VNC_PORT) -> None:
        self.sock = socket.create_connection((host, port), timeout=5.0)
        self.sock.settimeout(5.0)
        self._handshake()

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError(f"RFB peer closed after {len(buf)}/{n} bytes")
            buf.extend(chunk)
        return bytes(buf)

    def _handshake(self) -> None:
        # 1. ProtocolVersion
        version = self._recv_exact(12)
        if not version.startswith(b"RFB "):
            raise ConnectionError(f"Not an RFB server: {version!r}")
        self.sock.sendall(b"RFB 003.008\n")

        # 2. Security types
        n_types = self._recv_exact(1)[0]
        if n_types == 0:
            reason_len = struct.unpack(">I", self._recv_exact(4))[0]
            reason = self._recv_exact(reason_len).decode("utf-8", "replace")
            raise ConnectionError(f"Server refused: {reason}")
        types = self._recv_exact(n_types)
        if 1 not in types:  # 1 = None
            raise ConnectionError(
                f"Server requires auth (types={list(types)}); wayvnc with auth not supported"
            )
        self.sock.sendall(bytes([1]))

        # 3. SecurityResult
        result = struct.unpack(">I", self._recv_exact(4))[0]
        if result != 0:
            raise ConnectionError(f"Auth failed (code {result})")

        # 4. ClientInit (shared=1)
        self.sock.sendall(bytes([1]))

        # 5. ServerInit: width(2) height(2) pixelfmt(16) namelen(4) name(*)
        header = self._recv_exact(2 + 2 + 16 + 4)
        name_len = struct.unpack(">I", header[-4:])[0]
        self._recv_exact(name_len)
        # Drain anything else the server might have queued (framebuffer
        # updates, etc.) without blocking on more reads.
        self.sock.setblocking(False)
        try:
            self.sock.recv(65536)
        except (BlockingIOError, OSError):
            pass
        self.sock.setblocking(True)
        self.sock.settimeout(5.0)

    def pointer(self, button_mask: int, x: int, y: int) -> None:
        # PointerEvent: type=5, buttonMask(1), x(u16), y(u16)
        msg = struct.pack(">BBHH", 5, button_mask & 0xFF, x & 0xFFFF, y & 0xFFFF)
        self.sock.sendall(msg)

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def _click(rfb: RFBClient, x: int, y: int, btn: int, hold_ms: int = 30) -> None:
    rfb.pointer(0, x, y)
    time.sleep(0.01)
    rfb.pointer(btn, x, y)
    time.sleep(hold_ms / 1000.0)
    rfb.pointer(0, x, y)


def cmd_click(rfb: RFBClient, args: argparse.Namespace) -> None:
    btn = BUTTON_MAP[args.button]
    _click(rfb, args.x, args.y, btn)


def cmd_double(rfb: RFBClient, args: argparse.Namespace) -> None:
    btn = BUTTON_MAP[args.button]
    _click(rfb, args.x, args.y, btn)
    time.sleep(0.05)
    _click(rfb, args.x, args.y, btn)


def cmd_move(rfb: RFBClient, args: argparse.Namespace) -> None:
    rfb.pointer(0, args.x, args.y)


def cmd_scroll(rfb: RFBClient, args: argparse.Namespace) -> None:
    btn = BTN_SCROLL_UP if args.ticks > 0 else BTN_SCROLL_DOWN
    rfb.pointer(0, args.x, args.y)
    for _ in range(abs(args.ticks)):
        rfb.pointer(btn, args.x, args.y)
        time.sleep(0.01)
        rfb.pointer(0, args.x, args.y)
        time.sleep(0.01)


def cmd_drag(rfb: RFBClient, args: argparse.Namespace) -> None:
    btn = BUTTON_MAP[args.button]
    rfb.pointer(0, args.sx, args.sy)
    time.sleep(0.02)
    rfb.pointer(btn, args.sx, args.sy)
    time.sleep(0.05)
    # Interpolate a few intermediate points so the compositor sees motion.
    steps = 10
    for i in range(1, steps + 1):
        ix = args.sx + (args.dx - args.sx) * i // steps
        iy = args.sy + (args.dy - args.sy) * i // steps
        rfb.pointer(btn, ix, iy)
        time.sleep(0.01)
    rfb.pointer(0, args.dx, args.dy)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--host", default=VNC_HOST)
    p.add_argument("--port", type=int, default=VNC_PORT)
    sub = p.add_subparsers(dest="cmd", required=True)

    s_click = sub.add_parser("click", help="single click at (x, y)")
    s_click.add_argument("x", type=int)
    s_click.add_argument("y", type=int)
    s_click.add_argument("--button", choices=BUTTON_MAP, default="left")

    s_double = sub.add_parser("double", help="double click at (x, y)")
    s_double.add_argument("x", type=int)
    s_double.add_argument("y", type=int)
    s_double.add_argument("--button", choices=BUTTON_MAP, default="left")

    s_move = sub.add_parser("move", help="move pointer without clicking")
    s_move.add_argument("x", type=int)
    s_move.add_argument("y", type=int)

    s_scroll = sub.add_parser("scroll", help="scroll at (x, y); +up / -down")
    s_scroll.add_argument("x", type=int)
    s_scroll.add_argument("y", type=int)
    s_scroll.add_argument("ticks", type=int)

    s_drag = sub.add_parser("drag", help="press at src, drag to dst, release")
    s_drag.add_argument("sx", type=int)
    s_drag.add_argument("sy", type=int)
    s_drag.add_argument("dx", type=int)
    s_drag.add_argument("dy", type=int)
    s_drag.add_argument("--button", choices=BUTTON_MAP, default="left")

    args = p.parse_args()

    try:
        rfb = RFBClient(args.host, args.port)
    except (ConnectionRefusedError, ConnectionError) as e:
        print(f"ERROR: cannot connect to wayvnc at {args.host}:{args.port}: {e}", file=sys.stderr)
        print("       Start the sandbox with CC_VNC=1 (default).", file=sys.stderr)
        return 2

    handlers = {
        "click": cmd_click,
        "double": cmd_double,
        "move": cmd_move,
        "scroll": cmd_scroll,
        "drag": cmd_drag,
    }
    try:
        handlers[args.cmd](rfb, args)
    finally:
        rfb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
