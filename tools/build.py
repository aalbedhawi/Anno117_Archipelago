"""Builds the release files into dist/:

    anno117.apworld   the world, client and bundled game mod (install into Archipelago)
    AP-Anno117.zip    the game mod on its own, for installing by hand
    Anno 117.yaml     options template
    anno117-archipelago-<version>.zip   everything a player needs, for a GitHub release

Usage: python tools/build.py <path to an Archipelago source checkout>
       python tools/build.py --bundle-only     copy mod/ into the apworld folder only (needed before running tests)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "apworld" / "anno117"
MOD = ROOT / "mod" / "AP-Anno117"
DIST = ROOT / "dist"


def bundle_mod() -> None:
    target = WORLD / "mod" / "AP-Anno117"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(MOD, target)


def link_world(ap: Path) -> None:
    link = ap / "worlds" / "anno117"
    if link.is_symlink() or link.exists():
        if link.resolve() == WORLD.resolve():
            return
        raise SystemExit(f"{link} exists and is not this world; remove it first")
    try:
        link.symlink_to(WORLD, target_is_directory=True)
    except OSError:  # no symlink rights (Windows without developer mode)
        shutil.copytree(WORLD, link, ignore=shutil.ignore_patterns("__pycache__"))


def build_apworld(ap: Path) -> Path:
    subprocess.run([sys.executable, "Launcher.py", "Build APWorlds", "--", "Anno 117", "--skip_open_folder"],
                   cwd=ap, check=True, stdin=subprocess.DEVNULL)
    built = ap / "build" / "apworlds" / "anno117.apworld"
    out = DIST / "anno117.apworld"
    shutil.copy2(built, out)
    return out


def zip_mod() -> Path:
    out = DIST / "AP-Anno117.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(MOD.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(MOD.parent))
    return out


def template(ap: Path) -> Path:
    import json
    import re

    minimum = json.loads((WORLD / "archipelago.json").read_text(encoding="utf-8"))["minimum_ap_version"]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", f"import Options; Options.generate_yaml_templates({tmp!r})"],
                       cwd=ap, check=True, stdin=subprocess.DEVNULL, capture_output=True)
        text = (Path(tmp) / "Anno 117.yaml").read_text(encoding="utf-8-sig")
    # the template asks for the generating checkout's version; ask for the world's minimum instead
    text = re.sub(r"(requires:\s*\n\s*version: )\S+", rf"\g<1>{minimum}", text, count=1)
    out = DIST / "Anno 117.yaml"
    out.write_text(text, encoding="utf-8")
    return out


def release_zip(files: list[Path]) -> Path:
    import json

    version = json.loads((WORLD / "archipelago.json").read_text(encoding="utf-8"))["world_version"]
    out = DIST / f"anno117-archipelago-{version}.zip"
    extra = [ROOT / "README.md", ROOT / "LICENSE", ROOT / "CREDITS.md", ROOT / "CHANGELOG.md",
             WORLD / "docs" / "setup_en.md"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files + extra:
            z.write(f, f.name)
        for f in sorted((ROOT / "examples").glob("*.yaml")):
            z.write(f, f"examples/{f.name}")
        z.writestr("README.txt", (
            f"Anno 117: Pax Romana for Archipelago, world {version}\n\n"
            "anno117.apworld    double-click it (or Install APWorld in the Archipelago Launcher), then open the\n"
            "                   Anno 117 Client: it installs the game mod by itself\n"
            "AP-Anno117.zip     the game mod, only if you want to install it by hand into Documents/Anno 117/mods\n"
            "Anno 117.yaml      options template with every option explained\n"
            "examples/          ready-made options files\n"
            "setup_en.md        the full setup guide\n\n"
            "Unofficial fan project, not affiliated with Ubisoft. MIT licence, see LICENSE and CREDITS.md.\n"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archipelago", nargs="?", help="Archipelago source checkout (with requirements installed)")
    parser.add_argument("--bundle-only", action="store_true", help="only copy mod/ into apworld/anno117/mod/")
    args = parser.parse_args()
    bundle_mod()
    if args.bundle_only:
        print(f"bundled {MOD.relative_to(ROOT)} into {(WORLD / 'mod').relative_to(ROOT)}")
        return
    if not args.archipelago:
        parser.error("give the path to an Archipelago source checkout, or use --bundle-only")
    ap = Path(args.archipelago).resolve()
    DIST.mkdir(exist_ok=True)
    link_world(ap)
    built = [build_apworld(ap), zip_mod(), template(ap)]
    built.append(release_zip(built))
    for path in built:
        print(f"built {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
