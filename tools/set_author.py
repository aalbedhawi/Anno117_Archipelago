"""Puts your name or GitHub ID everywhere the project credits its author.

    python tools/set_author.py "Your Name or github-id"

Replaces the YOUR_NAME placeholder in the licence, credits, README files, the apworld manifest, the setup guide
credit and the mod's modinfo.json. Run tools/build.py afterwards so the release files pick it up.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "YOUR_NAME"
FILES = [
    "LICENSE", "CREDITS.md", "README.md", "CONTRIBUTING.md",
    "apworld/anno117/LICENSE", "apworld/anno117/archipelago.json", "apworld/anno117/web_world.py",
    "mod/AP-Anno117/LICENSE", "mod/AP-Anno117/README.md", "mod/AP-Anno117/modinfo.json",
]


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        raise SystemExit(__doc__)
    name = sys.argv[1].strip()
    if any(c in name for c in '"\\\n'):
        raise SystemExit("Please use a name without quotes, backslashes or line breaks.")
    changed = 0
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER in text:
            path.write_text(text.replace(PLACEHOLDER, name), encoding="utf-8")
            changed += 1
            print(f"updated {rel}")
    left = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts
            and "dist" not in p.parts and p.suffix in {".md", ".json", ".py", ".txt", ""}
            and PLACEHOLDER in p.read_text(encoding="utf-8", errors="ignore") and p.name != "set_author.py"]
    print(f"{changed} files updated." + (f" Still containing {PLACEHOLDER}: {', '.join(left)}" if left else ""))


if __name__ == "__main__":
    main()
