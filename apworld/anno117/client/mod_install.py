"""Installs the bundled AP-Anno117 game mod into the user's Anno 117 mods folder."""
from __future__ import annotations

import pkgutil
from pathlib import Path

from .paths import MOD_FOLDER_NAME

PACKAGE = __name__.rsplit(".", 2)[0]  # worlds.anno117
MOD_FILES = (
    "modinfo.json",
    "README.md",
    "LICENSE",
    "ap_anno117/ap_bridge.lua",
    "ap_anno117/ap_state.lua",
    "data/base/config/export/assets.xml",
)
KEEP_IF_PRESENT = {"ap_anno117/ap_state.lua"}


def bundled_file(relative: str) -> bytes:
    data = pkgutil.get_data(PACKAGE, f"mod/{MOD_FOLDER_NAME}/{relative}")
    if data is None:
        raise FileNotFoundError(relative)
    return data


def install_mod(user_folder: Path) -> Path:
    target = user_folder / "mods" / MOD_FOLDER_NAME
    for relative in MOD_FILES:
        dest = target / relative
        if relative in KEEP_IF_PRESENT and dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bundled_file(relative))
    return target


def installed_version(user_folder: Path) -> str | None:
    import json

    info = user_folder / "mods" / MOD_FOLDER_NAME / "modinfo.json"
    try:
        return json.loads(info.read_text(encoding="utf-8")).get("Version")
    except (OSError, ValueError):
        return None


def bundled_version() -> str | None:
    import json

    try:
        return json.loads(bundled_file("modinfo.json").decode("utf-8")).get("Version")
    except (OSError, ValueError):
        return None
