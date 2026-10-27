"""A stand-in for Anno 117 that runs the real ap_bridge.lua (from the installed mod) in Lua 5.1 via lupa.

It mocks the handful of game APIs the bridge uses, writes the bridge's print output to a log file the way
the game does, and plays along: tiers grow once their residence is unlocked, received buildings get built.
"""
from __future__ import annotations

import importlib
from pathlib import Path

LOCKABLE_RESIDENCES = {3141: 1496, 3142: 1497, 3145: 1498, 6471: 1501, 6472: 1502, 6475: 1503, 6514: 1504}
BASE_TIERS = (1499, 1500)


class FakeAnno:
    def __init__(self, user_folder: Path, lua_module: str = "lupa.lua51", with_io: bool = False,
                 stale_dofile: bool = False, vanilla_unlocked: set[int] | None = None, growth: int = 25,
                 lockable: set[int] | None = None) -> None:
        self.user_folder = user_folder
        self.mod_dir = user_folder / "mods" / "AP-Anno117" / "ap_anno117"
        self.log_path = user_folder / "log" / "game_session.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.unlocked: set[int] = set(vanilla_unlocked or ())
        # buildings the randomizer does not lock (the starter kit) are available, and get built, from the start
        self.lockable: set[int] | None = set(lockable) if lockable is not None else None
        self.relock_calls: list[int] = []
        self.unlock_calls: list[int] = []
        self.bridge_unlocked: set[int] = set()
        self.denarii = 0
        self.pop: dict[int, int] = {}
        self.unlocked_since: dict[int, int] = {}
        self.cycle = 0
        self.growth = growth
        self.stale_dofile = stale_dofile
        self._dofile_cache: dict[str, str] = {}
        self.lines: list[str] = []

        lupa = importlib.import_module(lua_module)
        self.lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.py = self
        if not with_io:
            g.io = None
        # wrap Python callables in real Lua functions, so type(dofile) == "function" like in the game
        g._py_print, g._py_dofile, g._py_require = self._print, self._dofile, self._require
        self.lua.execute("""
            print = function(...) _py_print(...) end
            dofile = function(path) return _py_dofile(path) end
            require = function(name) return _py_require(name) end
        """)
        self.lua.execute("""
            Unlock = {
                IsUnlocked = function(self, guid) return py.is_unlocked(guid) end,
                UnlockNet = function(self, guid) py.unlock(guid) end,
                RelockNet = function(self, guid) py.relock(guid) end,
            }
            Population = {
                GetMaxReachedGlobalPopulationCount = function(self, level) return py.population(level) end,
                GetGlobalPopulationCount = function(self, level) return py.population(level) end,
            }
            Participants = { GetCurrentParticipantGUID = 41 }
            Scripts = {
                GetObjectGroupByGUID = function(self, guid, owner)
                    local t = {}
                    for i = 1, py.built(guid) do t[i] = i end
                    return t
                end,
            }
            Economy = { MetaStorage = { AddAmount = function(self, guid, amount) py.add_amount(guid, amount) end } }
        """)

    # ---- Python side of the mocks (called with the Lua table as first argument)
    def is_unlocked(self, guid) -> bool:
        return int(guid) in self.unlocked

    def unlock(self, guid) -> None:
        self.unlock_calls.append(int(guid))
        self.bridge_unlocked.add(int(guid))
        if int(guid) not in self.unlocked:
            self.unlocked.add(int(guid))
            self.unlocked_since[int(guid)] = self.cycle

    def relock(self, guid) -> None:
        self.relock_calls.append(int(guid))
        self.unlocked.discard(int(guid))
        self.unlocked_since.pop(int(guid), None)

    def population(self, level) -> int:
        return self.pop.get(int(level), 0)

    def built(self, guid) -> int:
        guid = int(guid)
        if self.lockable is not None and guid not in self.lockable:
            return 1 if self.cycle >= 2 else 0
        since = self.unlocked_since.get(guid)
        return 1 if since is not None and self.cycle - since >= 2 else 0

    def add_amount(self, guid, amount) -> None:
        assert int(guid) == 1010017
        self.denarii += int(amount)

    # ---- Lua globals
    def _print(self, *args) -> None:
        line = " ".join(str(a) for a in args)
        self.lines.append(line)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"[Lua] {line}\n")

    def _run_file(self, path: str, text: str):
        loader = self.lua.globals().loadstring or self.lua.globals().load
        fn = loader(text, "@" + path)
        if isinstance(fn, tuple):  # (nil, error message)
            raise RuntimeError(f"cannot compile {path}: {fn[1]}")
        if fn is None:
            raise RuntimeError(f"cannot compile {path}")
        return fn()

    def _dofile(self, path):
        path = str(path)
        file = Path(path)
        if not file.is_absolute():
            file = self.mod_dir.parent / path
        if self.stale_dofile and path in self._dofile_cache:
            text = self._dofile_cache[path]
        else:
            text = file.read_text(encoding="utf-8")
            self._dofile_cache[path] = text
        return self._run_file(str(file), text)

    def _require(self, name):
        if str(name) != "ap_state":
            raise RuntimeError(f"module {name} not found")
        file = self.mod_dir / "ap_state.lua"
        return self._run_file(str(file), file.read_text(encoding="utf-8"))

    # ---- game lifecycle
    def init_mod(self) -> None:
        bridge = self.mod_dir / "ap_bridge.lua"
        self.lua.globals().AP117 = self._run_file(str(bridge), bridge.read_text(encoding="utf-8"))

    @property
    def ap(self):
        return self.lua.globals().AP117

    def load_save(self) -> None:
        self.ap.OnLoad()

    def play_cycle(self) -> None:
        """One bridge cycle (10 ticks) of play: unlocked tiers grow."""
        self.cycle += 1
        for level in BASE_TIERS:
            self.pop[level] = self.pop.get(level, 0) + self.growth
        for residence, level in LOCKABLE_RESIDENCES.items():
            # only residences the bridge handed over count, not ones the game had unlocked on its own
            vanilla = self.lockable is not None and residence not in self.lockable  # not shuffled: grows normally
            if vanilla or (residence in self.unlocked and residence in self.bridge_unlocked):
                self.pop[level] = self.pop.get(level, 0) + self.growth
        for _ in range(10):
            self.ap.OnTick()
