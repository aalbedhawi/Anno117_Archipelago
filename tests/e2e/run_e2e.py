"""End-to-end test: Archipelago server + Anno 117 Client + the real bridge mod inside a simulated game.

    python tests/e2e/run_e2e.py <Archipelago source dir> <scratch dir> [dofile|io|stale]

Generates a solo seed, hosts it, starts the client headless, lets the "game" play until the goal, then
checks what reached the server and what the game was told to unlock.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_game import FakeAnno  # noqa: E402

PORT = 38297
SLOT = "Marcus"
YAML = """name: Marcus
game: Anno 117
Anno 117:
  provinces: latium
  goal: auto
  goal_population: 100
  milestones_per_tier: 4
  milestone_cap: 300
  building_checks: true
"""


def wait_for(cond, timeout: float, what: str, step: float = 0.2):
    end = time.time() + timeout
    while time.time() < end:
        result = cond()
        if result:
            return result
        time.sleep(step)
    raise TimeoutError(f"timed out waiting for {what}")


def main() -> int:
    ap_dir = Path(sys.argv[1]).resolve()
    scratch = Path(sys.argv[2]).resolve()
    mode = sys.argv[3] if len(sys.argv) > 3 else "dofile"
    scratch.mkdir(parents=True, exist_ok=True)
    players, out, user = scratch / "players", scratch / "out", scratch / "AnnoUser"
    for d in (players, out, user / "log", user / "mods"):
        d.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.zip"):
        old.unlink()
    (players / "p1.yaml").write_text(YAML, encoding="utf-8")

    env = dict(os.environ, PYTHONUNBUFFERED="1")
    gen = subprocess.run([sys.executable, "Generate.py", "--player_files_path", str(players), "--outputpath",
                          str(out)], cwd=ap_dir, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env)
    if gen.returncode != 0:
        print(gen.stdout[-3000:], gen.stderr[-3000:])
        return 1
    multidata = next(out.glob("AP_*.zip"))
    seed = multidata.stem[3:]
    with zipfile.ZipFile(multidata) as z:
        spoiler_name = next((n for n in z.namelist() if n.endswith("_Spoiler.txt")), None)

    server_log = (scratch / "server.log").open("w")
    server = subprocess.Popen([sys.executable, "MultiServer.py", "--port", str(PORT), str(multidata)], cwd=ap_dir,
                              stdin=subprocess.PIPE, stdout=server_log, stderr=subprocess.STDOUT, env=env)
    client_log_path = scratch / "client.log"
    client_log = client_log_path.open("w")
    # The user folder is handed to the client through its persistent store, as /anno_folder would do.
    boot = (
        "import sys; sys.argv=['Anno117Client','--nogui']\n"
        "import Utils\n"
        f"Utils.persistent_store('anno117_client', 'user_folder', {str(user)!r})\n"
        "import worlds\n"
        "from worlds.anno117.client.context import launch_client\n"
        f"launch_client('--connect', 'localhost:{PORT}', '--name', '{SLOT}', '--nogui')\n"
    )
    client = None
    game = None
    try:
        time.sleep(3)
        client = subprocess.Popen([sys.executable, "-c", boot], cwd=ap_dir, stdin=subprocess.PIPE,
                                  stdout=client_log, stderr=subprocess.STDOUT, env=env)
        state_file = user / "mods" / "AP-Anno117" / "ap_anno117" / "ap_state.lua"
        wait_for(lambda: state_file.exists() and "S.protocol = 1" in state_file.read_text(), 60,
                 "client to install the mod and write the session")
        print(f"[e2e] mod installed and session written ({mode} mode)")

        everything_lockable = set(json.loads(
            json.dumps(_locked_from_state(state_file.read_text()))))
        # stale: nothing unlocked up front, so tiers only grow from items that really reached the game
        game = FakeAnno(user, with_io=(mode == "io"), stale_dofile=(mode == "stale"),
                        vanilla_unlocked=set() if mode == "stale" else everything_lockable,
                        lockable=everything_lockable)
        game.init_mod()
        game.load_save()

        def client_says(text: str) -> bool:
            return text in client_log_path.read_text(errors="replace")

        goal_seen = False
        after_goal = 0
        deadline = time.time() + (90 if mode == "stale" else 240)
        while time.time() < deadline:
            game.play_cycle()
            time.sleep(0.15)
            if not goal_seen and any("|GOAL|" in line for line in game.lines) and client_says("Goal reached"):
                goal_seen = True
            if goal_seen and mode != "stale":
                # the server auto-releases the rest on goal: keep playing so every item has to arrive
                after_goal += 1
                if after_goal > 40:
                    break
            if mode == "stale" and client_says("waiting for the game"):
                break
        time.sleep(2)

        server_text = (scratch / "server.log").read_text(errors="replace")
        client_text = client_log_path.read_text(errors="replace")
        residences = {3141, 3142, 3145, 6471, 6472, 6475, 6514}
        auto_residences = set(game.unlock_calls) & residences  # unshuffled residences the mod unlocked by itself
        received_unlocks = set(game.unlock_calls) - residences
        problems = []
        if mode == "stale":
            if not client_says("only reads the session when it starts"):
                problems.append("client did not detect a game that only reads the session at startup")
            if not client_says("waiting for the game"):
                problems.append("client did not tell the player about items waiting for a restart")
            if received_unlocks:
                problems.append("stale game should not have received anything before restarting")
            # restart the game: Init reads the newest file, so everything received so far arrives
            game2 = FakeAnno(user, stale_dofile=True, vanilla_unlocked=set(), lockable=everything_lockable)
            game2.init_mod()
            game2.load_save()
            for _ in range(5):
                game2.play_cycle()
            if not set(game2.unlock_calls) >= received_unlocks:
                problems.append("restarted game did not get the earlier unlocks")
            if len(game2.unlock_calls) <= len(received_unlocks):
                problems.append("restarted game did not get any new unlocks")
        else:
            if not goal_seen:
                problems.append("goal was not reached")
            if "has completed their goal" not in server_text:
                problems.append("server did not record the goal")
            if "picks up updates while it runs" not in client_text:
                problems.append("client did not confirm the live channel")
            still_unlocked_but_not_received = (game.unlocked & everything_lockable) - received_unlocks
            if still_unlocked_but_not_received:
                problems.append(f"locked buildings left unlocked: {sorted(still_unlocked_but_not_received)[:5]}")
            if not set(game.relock_calls):
                problems.append("bridge never relocked anything")
            if received_unlocks != everything_lockable:
                missing = sorted(everything_lockable - received_unlocks)
                problems.append(f"{len(missing)} shuffled unlocks never reached the game: {missing[:6]}")
            with zipfile.ZipFile(multidata) as z:
                spoiler = z.read(spoiler_name).decode("utf-8") if spoiler_name else ""
            caches = sum(1 for line in spoiler.splitlines() if line.rstrip().endswith(": Denarii Cache"))
            applied_now = sum(1 for line in game.lines if "|APPLIED|" in line)
            if applied_now != caches or game.denarii != caches * 10000:
                problems.append(f"denarii caches: {applied_now} applied ({game.denarii}), {caches} in the seed")
        checks = sum(1 for line in game.lines if "|CHECK|" in line)
        applied = sum(1 for line in game.lines if "|APPLIED|" in line)
        if mode != "stale" and not {3141, 3142} <= auto_residences:
            problems.append(f"residences not unlocked automatically: {sorted(auto_residences)}")
        print(f"[e2e] seed {seed}: {checks} checks sent, {len(received_unlocks)} unlocks, {applied} denarii caches "
              f"({game.denarii} denarii), {len(set(game.relock_calls))} buildings relocked, spoiler={spoiler_name}")
        if problems:
            print("[e2e] FAILED:\n  " + "\n  ".join(problems))
            print("---- client log tail\n" + client_text[-4000:])
            print("---- server log tail\n" + server_text[-2000:])
            print("---- game lines tail\n" + "\n".join(game.lines[-30:]))
            return 1
        print(f"[e2e] PASSED ({mode})")
        return 0
    finally:
        for proc in (client, server):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        server_log.close()
        client_log.close()


def _locked_from_state(text: str) -> list[int]:
    for line in text.splitlines():
        if line.startswith("S.locked = {"):
            return [int(x) for x in line.split("{", 1)[1].rstrip("}").split(",") if x]
    return []


if __name__ == "__main__":
    sys.exit(main())
