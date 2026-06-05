from __future__ import annotations

ESC = b"\x1b"
GS = b"\x1d"


def init() -> bytes:
    return ESC + b"@"


def align(mode: str) -> bytes:
    values = {"left": 0, "center": 1, "right": 2}
    return ESC + b"a" + bytes([values.get(mode, 0)])


def bold(on: bool = True) -> bytes:
    return ESC + b"E" + bytes([1 if on else 0])


def double_size(on: bool = True) -> bytes:
    return GS + b"!" + bytes([0x11 if on else 0x00])


def cut() -> bytes:
    return GS + b"V" + b"\x00"


def feed(lines: int = 1) -> bytes:
    return b"\x1b\x64" + bytes([lines])


def text(value: str) -> bytes:
    # CP858 handles common Western European chars and the euro sign on many ESC/POS printers.
    return value.encode("cp858", errors="replace")


def line(value: str = "") -> bytes:
    return text(value) + b"\n"


def separator(width: int = 32) -> bytes:
    return line("-" * width)
