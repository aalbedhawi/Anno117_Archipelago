"""Fallback channel: types data into the game through the bridge's keybinds (Windows only).

Each message is sent as bits: Shift+F6 = 0, Shift+F7 = 1, Shift+F8 = end of message, Shift+F9 = reset.
The bridge rebuilds the text, checks the checksum and confirms in the log.
"""
from __future__ import annotations

import sys
import time

# Set-1 scan codes
SCAN_SHIFT = 0x2A
SCAN_KEYS = {"F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42, "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58}
BIT0, BIT1, END, RESET = "F6", "F7", "F8", "F9"
WINDOW_TITLE = "Anno 117"
# virtual-key codes the client presses itself: Shift, Left/Right Shift, F5 to F9
OWN_KEYS = frozenset({0x10, 0xA0, 0xA1, 0x74, 0x75, 0x76, 0x77, 0x78})
DEFAULT_PRESS_MS = 50  # longer than a frame even at low fps, so the game sees every tap


def checksum(text: str) -> int:
    return sum(text.encode("ascii")) % 251


def frame(body: str) -> str:
    return f"{body}*{checksum(body)}"


def to_bits(text: str) -> list[int]:
    bits = []
    for byte in text.encode("ascii"):
        bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    return bits


class KeySender:
    available = sys.platform == "win32"

    def __init__(self, press_ms: int = DEFAULT_PRESS_MS) -> None:
        self.press_seconds = max(5, int(press_ms)) / 1000
        self.last_input = time.monotonic()
        self._user32 = None
        if self.available:
            import ctypes

            self._ctypes = ctypes
            self._user32 = ctypes.windll.user32
            self._setup_types()

    def _setup_types(self) -> None:
        ctypes = self._ctypes
        from ctypes import wintypes

        ulong_ptr = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]

        self._KEYBDINPUT, self._INPUT, self._INPUTUNION = KEYBDINPUT, INPUT, _INPUTUNION

    def game_focused(self) -> bool:
        if not self._user32:
            return False
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return False
        buf = self._ctypes.create_unicode_buffer(512)
        self._user32.GetWindowTextW(hwnd, buf, 512)
        return WINDOW_TITLE.lower() in buf.value.lower()

    def mouse_busy(self) -> bool:
        if not self._user32:
            return True
        return any(self._user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))

    def user_input(self) -> bool:
        """True if the player clicked or pressed a key since the last check. Moving the mouse doesn't count, and
        neither do the keys the client presses itself (Shift, F5 to F9)."""
        if not self._user32:
            return False
        pressed = False
        for vk in range(1, 255):
            if vk not in OWN_KEYS and self._user32.GetAsyncKeyState(vk) & 0x8001:  # down now, or since last check
                pressed = True
        if pressed:
            self.last_input = time.monotonic()
        return pressed

    def idle_seconds(self) -> float:
        """Seconds since the player last clicked or pressed a key."""
        if not self._user32:
            return 0.0
        self.user_input()
        return time.monotonic() - self.last_input

    def _scan(self, code: int, up: bool) -> None:
        flags = 0x0008 | (0x0002 if up else 0)  # KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        event = self._INPUT(type=1, union=self._INPUTUNION(ki=self._KEYBDINPUT(0, code, flags, 0, 0)))
        self._user32.SendInput(1, self._ctypes.byref(event), self._ctypes.sizeof(event))

    def _tap(self, key: str) -> None:
        code = SCAN_KEYS[key]
        self._scan(code, False)
        time.sleep(self.press_seconds)
        self._scan(code, True)
        time.sleep(self.press_seconds)

    def send(self, body: str) -> bool:
        """Types one framed message. Blocking; run it in a worker thread. False if the game lost focus or the
        player clicked or typed meanwhile (the caller sends it again later)."""
        if not self._user32 or not self.game_focused():
            return False
        self.user_input()  # clear anything pressed before we start
        self._scan(SCAN_SHIFT, False)
        try:
            self._tap(RESET)
            for bit in to_bits(frame(body)):
                # stop as soon as the player clicks or types, so we never hold Shift through their input;
                # the message is sent again once they pause
                if not self.game_focused() or self.user_input():
                    return False
                self._tap(BIT1 if bit else BIT0)
            self._tap(END)
        finally:
            self._scan(SCAN_SHIFT, True)
        return True
