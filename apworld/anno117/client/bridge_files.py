"""File side of the game bridge: the state file the client writes and the log lines the game prints."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MESSAGE_PREFIX = "AP117|"
STATE_FILE = "ap_state.lua"
OUTBOX_FILE = "ap_outbox.txt"
_UNSAFE = re.compile(r"[^A-Za-z0-9 _.\-]")


@dataclass(frozen=True)
class GameMessage:
    seed: str
    kind: str
    payload: str


def parse_message(line: str) -> GameMessage | None:
    start = line.find(MESSAGE_PREFIX)
    if start < 0:
        return None
    parts = line[start + len(MESSAGE_PREFIX):].rstrip("\r\n").split("|", 2)
    if len(parts) < 2:
        return None
    seed, kind = parts[0].strip(), parts[1].strip()
    payload = parts[2].strip() if len(parts) > 2 else ""
    if not kind.isalpha():
        return None
    return GameMessage(seed, kind, payload)


def lua_string(value: str) -> str:
    return '"' + _UNSAFE.sub("_", value) + '"'


def lua_path(path: Path) -> str:
    text = str(path).replace("\\", "/")
    if not text.endswith("/"):
        text += "/"
    return '"' + text.replace('"', "") + '"'


def lua_list(values: Iterable[int]) -> str:
    return "{" + ",".join(str(int(v)) for v in values) + "}"


def render_state(*, nonce: int, seed: str, slot: str, denarii: int, consumed: int, goal_count: int,
                 goal: Iterable[int], locked: Iterable[int], locations: Iterable[int], items: Iterable[int],
                 bridge_dir: Path, protocol: int = 1, unlock: Iterable[int] = (),
                 auto_unlock: Iterable[int] = ()) -> str:
    """The state file is valid Lua and also one `S.key = value` per line, so the bridge can parse it as text."""
    lines = [
        "-- AP-Anno117 session state, written by the Anno 117 Client. Do not edit.",
        "AP117_STATE = {}",
        "local S = AP117_STATE",
        f"S.protocol = {int(protocol)}",
        f"S.nonce = {int(nonce)}",
        f"S.seed = {lua_string(seed)}",
        f"S.slot = {lua_string(slot)}",
        f"S.denarii = {int(denarii)}",
        f"S.consumed = {int(consumed)}",
        f"S.goal_count = {int(goal_count)}",
        f"S.goal = {lua_list(goal)}",
        f"S.locked = {lua_list(locked)}",
        f"S.locations = {lua_list(sorted(locations))}",
        f"S.items = {lua_list(items)}",
        f"S.unlock = {lua_list(sorted(unlock))}",
        f"S.auto_unlock = {lua_list(auto_unlock)}",
        f"S.mod_dir = {lua_path(bridge_dir)}",
        "return AP117_STATE",
        "",
    ]
    return "\n".join(lines)


def write_atomic(path: Path, text: str) -> None:
    """Write to a temp file and swap it in, so the game never reads half a file.
    Raises OSError if the game happens to have the file open; the caller retries later."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


class LogTailer:
    """Follows a changing set of text files (game logs, outbox) and returns complete new lines."""

    def __init__(self, initial_bytes: int = 4 * 1024 * 1024) -> None:
        self.initial_bytes = initial_bytes
        self._files: dict[Path, dict] = {}

    def _encoding(self, path: Path) -> tuple[str, int]:
        with path.open("rb") as f:
            head = f.read(4)
        if head.startswith(b"\xef\xbb\xbf"):
            return "utf-8", 3
        if head.startswith(b"\xff\xfe"):
            return "utf-16-le", 2
        if head.startswith(b"\xfe\xff"):
            return "utf-16-be", 2
        return "utf-8", 0

    def poll(self, paths: Iterable[Path]) -> list[str]:
        lines: list[str] = []
        for path in paths:
            try:
                size = path.stat().st_size
            except OSError:
                continue
            info = self._files.get(path)
            if info is None or size < info["offset"]:
                try:
                    encoding, bom = self._encoding(path)
                except OSError:
                    continue
                start = max(bom, size - self.initial_bytes)
                if encoding.startswith("utf-16") and (start - bom) % 2:
                    start += 1
                info = {"offset": start, "encoding": encoding, "partial": b""}
                self._files[path] = info
            if size == info["offset"]:
                continue
            try:
                with path.open("rb") as f:
                    f.seek(info["offset"])
                    data = f.read(size - info["offset"])
            except OSError:
                continue
            info["offset"] += len(data)
            data = info["partial"] + data
            if info["encoding"].startswith("utf-16"):
                newline = "\n".encode(info["encoding"])
                cut = data.rfind(newline)
                cut = -1 if cut < 0 else cut + len(newline)
            else:
                cut = data.rfind(b"\n")
                cut = -1 if cut < 0 else cut + 1
            if cut < 0:
                info["partial"] = data
                continue
            info["partial"] = data[cut:]
            text = data[:cut].decode(info["encoding"], errors="replace")
            lines.extend(text.splitlines())
        return lines
