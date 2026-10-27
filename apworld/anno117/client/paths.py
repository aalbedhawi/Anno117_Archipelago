"""Finding the Anno 117 user folder (mods, logs) on this computer."""
from __future__ import annotations

import sys
from pathlib import Path

USER_FOLDER_NAMES = ("Anno 117", "Anno 117 - Pax Romana", "Anno 117 – Pax Romana", "Anno 117 Pax Romana")
MOD_FOLDER_NAME = "AP-Anno117"
BRIDGE_SUBFOLDER = "ap_anno117"
LOG_FOLDER_NAMES = ("log", "logs")


def documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5: follows OneDrive/redirected Documents folders
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:  # noqa: BLE001 - fall back to the default location
            pass
    return Path.home() / "Documents"


def find_user_folder(configured: str = "") -> Path | None:
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_dir() else None
    docs = documents_dir()
    for name in USER_FOLDER_NAMES:
        candidate = docs / name
        if candidate.is_dir():
            return candidate
    if docs.is_dir():
        for child in sorted(docs.glob("Anno 117*")):
            if child.is_dir() and ((child / "mods").is_dir() or (child / "log").is_dir()):
                return child
    return None


def find_bridge_dir(user_folder: Path) -> Path | None:
    """The installed mod's ap_anno117 folder (where ap_state.lua lives), wherever the mod sits in mods/."""
    mods = user_folder / "mods"
    default = mods / MOD_FOLDER_NAME / BRIDGE_SUBFOLDER
    if (default / "ap_bridge.lua").is_file():
        return default
    if mods.is_dir():
        for bridge in mods.glob(f"**/{BRIDGE_SUBFOLDER}/ap_bridge.lua"):
            return bridge.parent
    return None


def log_files(user_folder: Path, newest: int = 8, max_age_days: float = 3.0) -> list[Path]:
    """The most recently written game log files (the game starts a new log on every launch)."""
    import time

    cutoff = time.time() - max_age_days * 86400
    found: list[tuple[float, Path]] = []
    for name in LOG_FOLDER_NAMES:
        folder = user_folder / name
        if not folder.is_dir():
            continue
        for p in folder.iterdir():
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if p.is_file() and mtime >= cutoff:
                found.append((mtime, p))
    found.sort(reverse=True)
    # oldest first, so the newest file's messages are handled last
    return [p for _, p in reversed(found[:newest])]
