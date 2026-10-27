"""End-to-end test of the keybind fallback: the game never sees live file updates, so the client has to type
items in. Runs the client in-process and replaces Windows SendInput with a fake keyboard that presses the
bridge's keybind commands directly.

    python tests/e2e/run_e2e_keys.py <Archipelago source dir> <scratch dir>
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_game import FakeAnno  # noqa: E402

PORT = 38299
YAML = """name: Livia
game: Anno 117
Anno 117:
  provinces: latium
  goal_population: 100
  milestones_per_tier: 4
  milestone_cap: 300
"""


class FakeKeyboard:
    """Stands in for KeySender: 'typing' a message calls the bridge's keybind commands."""
    available = True

    def __init__(self, game: FakeAnno, lock: threading.Lock, drop_first: int = 0) -> None:
        self.game, self.lock = game, lock
        self.drop_first = drop_first  # messages the "game" misses (still loading)
        self.messages: list[str] = []
        self.started = time.time()

    def game_focused(self) -> bool:
        return True

    def mouse_busy(self) -> bool:
        return False

    def idle_seconds(self) -> float:
        # the "player" is busy for the first few seconds, then leaves the game alone
        return 0.0 if time.time() - self.started < 6 else 10.0

    def send(self, body: str) -> bool:
        from worlds.anno117.client.keys import frame, to_bits

        self.messages.append(body)
        if self.drop_first > 0:
            self.drop_first -= 1
            time.sleep(0.6)
            return True
        with self.lock:
            ap = self.game.ap
            ap.KeyReset()
            for bit in to_bits(frame(body)):
                ap.KeyBit(bit)
            ap.KeyEnd()
        time.sleep(0.6)  # typing takes longer than the ack window: the timer must start after it
        return True


async def run(ap_dir: Path, scratch: Path, flaky: bool = False) -> int:
    import Utils
    from CommonClient import server_loop

    from worlds.anno117.client import context as client_ctx

    client_ctx.LIVE_TIMEOUT = 3.0
    client_ctx.STEP_SECONDS = 0.1
    client_ctx.KEY_ACK_TIMEOUT = 0.4
    client_ctx.PING_RETRY = 2.0
    user = scratch / "AnnoUser"
    Utils.persistent_store("anno117_client", "user_folder", str(user))
    ctx = client_ctx.Anno117Context(f"localhost:{PORT}", None)
    ctx.auth = "Livia"
    ctx.key_delivery = "idle"
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    bridge_task = asyncio.create_task(client_ctx.game_loop(ctx), name="bridge")

    state_file = user / "mods" / "AP-Anno117" / "ap_anno117" / "ap_state.lua"
    for _ in range(300):
        if state_file.exists() and "S.protocol = 1" in state_file.read_text():
            break
        await asyncio.sleep(0.1)
    else:
        print("[keys] client never wrote the session")
        return 1

    lock = threading.Lock()
    locked_line = next(line for line in state_file.read_text().splitlines() if line.startswith("S.locked = {"))
    lockable = {int(x) for x in locked_line.split("{", 1)[1].rstrip("}").split(",") if x}
    game = FakeAnno(user, stale_dofile=True, lockable=lockable)
    keyboard = FakeKeyboard(game, lock, drop_first=1 if flaky else 0)
    ctx.keys = keyboard
    with lock:
        game.init_mod()
        game.load_save()

    deadline = time.time() + 400
    quiet = 0
    while time.time() < deadline:
        with lock:
            game.play_cycle()
        await asyncio.sleep(0.1)
        settled = ctx.finished_game and (ctx.game_items or 0) >= len(ctx.items_received)
        # the server releases the rest after the goal, so wait until nothing new has arrived for a while
        quiet = quiet + 1 if settled else 0
        if quiet >= 30:
            break

    # /unlock_residence: the seed does not shuffle residences, so the Eques Residence can be unlocked by hand
    processor = client_ctx.Anno117CommandProcessor(ctx)
    processor._cmd_unlock_residence("Equites")
    for _ in range(100):
        with lock:
            game.play_cycle()
        await asyncio.sleep(0.1)
        if 3142 in game.unlock_calls:
            break

    problems = []
    if 3142 not in game.unlock_calls:
        problems.append("/unlock_residence Equites did not reach the game")
    if 3145 not in game.unlock_calls:
        problems.append("Patrician Residence was not unlocked automatically once Equites lived there")
    if "S.unlock = {3142}" not in state_file.read_text():
        problems.append("forced unlock not in the session file")
    if ctx.channel != "keys":
        problems.append(f"channel is {ctx.channel}, expected keys")
    if not ctx.finished_game:
        problems.append("goal not reached")
    if (ctx.game_items or 0) < len(ctx.items_received):
        problems.append(f"game knows {ctx.game_items} of {len(ctx.items_received)} items")
    expected_unlocks = {item.item - 117_000_000 for item in ctx.items_received if item.item < 117_900_000} \
        | {3141, 3142, 3145}
    if set(game.unlock_calls) != expected_unlocks:
        problems.append(f"unlocks differ: {len(set(game.unlock_calls))} vs {len(expected_unlocks)}")
    caches = sum(1 for item in ctx.items_received if item.item == 117_900_001)
    if game.denarii != caches * 10000:
        problems.append(f"denarii {game.denarii} for {caches} caches")
    print(f"[keys] {len(keyboard.messages)} key messages, {len(ctx.items_received)} items, "
          f"{len(set(game.unlock_calls))} unlocks, {game.denarii} denarii, channel={ctx.channel}")
    ctx.exit_event.set()
    bridge_task.cancel()
    await ctx.shutdown()
    if problems:
        print("[keys] FAILED:\n  " + "\n  ".join(problems))
        names = ctx.location_names
        received = sorted(ctx.item_names.lookup_in_game(i.item) for i in ctx.items_received)
        print("[keys] received:", received)
        print("[keys] still missing:", sorted(names.lookup_in_game(i) for i in ctx.missing_locations)[:80])
        print("[keys] game population:", game.pop, "unlocked:", sorted(game.unlocked))
        print("\n".join(game.lines[-10:]))
        return 1
    print("[keys] PASSED" + (" (first ping lost, recovered)" if flaky else ""))
    return 0


def main() -> int:
    ap_dir = Path(sys.argv[1]).resolve()
    scratch = Path(sys.argv[2]).resolve()
    flaky = len(sys.argv) > 3 and sys.argv[3] == "flaky"
    scratch.mkdir(parents=True, exist_ok=True)
    players, out = scratch / "players", scratch / "out"
    for d in (players, out, scratch / "AnnoUser" / "log", scratch / "AnnoUser" / "mods"):
        d.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.zip"):
        old.unlink()
    (players / "p1.yaml").write_text(YAML, encoding="utf-8")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    gen = subprocess.run([sys.executable, "Generate.py", "--player_files_path", str(players), "--outputpath",
                          str(out)], cwd=ap_dir, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env)
    if gen.returncode != 0:
        print(gen.stdout[-2000:], gen.stderr[-2000:])
        return 1
    multidata = next(out.glob("AP_*.zip"))
    log = (scratch / "server.log").open("w")
    server = subprocess.Popen([sys.executable, "MultiServer.py", "--port", str(PORT), str(multidata)], cwd=ap_dir,
                              stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        time.sleep(3)
        os.chdir(ap_dir)
        sys.path.insert(0, str(ap_dir))
        sys.argv = ["Anno117Client", "--nogui"]
        import worlds  # noqa: F401 - loads the apworld
        return asyncio.run(run(ap_dir, scratch, flaky=flaky))
    finally:
        server.terminate()
        server.wait(10)
        log.close()


if __name__ == "__main__":
    sys.exit(main())
