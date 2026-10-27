"""Runs the bridge unit tests in the Luau CLI.

Usage: python tests/lua/run_bridge_tests.py <path to luau binary>
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "mod" / "AP-Anno117" / "ap_anno117" / "ap_bridge.lua"
TEST = Path(__file__).with_name("test_bridge.luau")


def main() -> int:
    luau = sys.argv[1] if len(sys.argv) > 1 else "luau"
    combined = TEST.read_text(encoding="utf-8").replace("--@@BRIDGE@@", BRIDGE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "combined_test.luau"
        target.write_text(combined, encoding="utf-8")
        result = subprocess.run([luau, str(target)], capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
