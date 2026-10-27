"""Anno 117 Client: connects the Archipelago server to the AP-Anno117 bridge mod in the game."""
from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from pathlib import Path
from typing import Any

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from .. import gamedata as gd
from . import bridge_files, mod_install, paths
from .keys import KeySender, frame

STORE_CATEGORY = "anno117_client"
LIVE_TIMEOUT = 20.0      # seconds to wait for the game to confirm a state file written while it runs
KEY_ACK_TIMEOUT = 8.0
PING_RETRY = 45.0  # startup mode: how often to retest the keybind channel
RESIDENCE_NAMES = {t.residence: t.residence_name for t in gd.TIERS.values() if t.parent is not None}
RESIDENCE_TIER_NAMES = {t.name for t in gd.TIERS.values() if t.parent is not None}
RESIDENCE_BY_NAME = {**{t.name.lower(): t.residence for t in gd.TIERS.values() if t.parent is not None},
                     **{t.residence_name.lower(): t.residence for t in gd.TIERS.values() if t.parent is not None}}
IDLE_SECONDS = 1.5  # idle delivery: how long since the player last clicked or pressed a key
KEY_RETRIES = 3
WRITE_INTERVAL = 1.0
STEP_SECONDS = 0.5


def _settings() -> Any:
    try:
        from ..world import Anno117World

        return Anno117World.settings
    except Exception:  # noqa: BLE001 - settings are optional for the client
        return None


class Anno117CommandProcessor(ClientCommandProcessor):
    ctx: "Anno117Context"

    def _cmd_anno(self) -> bool:
        """Show the game bridge status."""
        for line in self.ctx.status_lines():
            self.output(line)
        return True

    def _cmd_install_mod(self) -> bool:
        """Install or update the AP-Anno117 mod in your Anno 117 mods folder."""
        if not self.ctx.user_folder:
            self.output("Anno 117 user folder not found. Set it with /anno_folder <path>.")
            return False
        target = mod_install.install_mod(self.ctx.user_folder)
        self.ctx.bridge_dir = None
        self.output(f"Installed the mod to {target}. Restart Anno 117 if it is running.")
        return True

    def _cmd_anno_folder(self, folder: str = "") -> bool:
        """Set your Anno 117 user folder (the one containing 'mods' and 'log')."""
        if not folder:
            self.output(f"Current folder: {self.ctx.user_folder}")
            return True
        path = Path(folder).expanduser()
        if not path.is_dir():
            self.output(f"{path} is not a folder.")
            return False
        self.ctx.user_folder_override = str(path)
        Utils.persistent_store(STORE_CATEGORY, "user_folder", str(path))
        self.ctx.user_folder = None
        self.ctx.bridge_dir = None
        self.output(f"Using {path}.")
        return True

    def _cmd_unlock_residence(self, tier: str = "") -> bool:
        """Unlock a residence upgrade the game is holding back (only ones this seed does not shuffle).
        Example: /unlock_residence Equites. It takes effect right away through the keybinds when the game is in
        front, and in any case the next time you load a save."""
        guid = RESIDENCE_BY_NAME.get(tier.strip().lower())
        if guid is None:
            self.output("Usage: /unlock_residence <tier>, one of: " + ", ".join(sorted(RESIDENCE_TIER_NAMES)))
            return False
        if self.ctx.slot_data is None:
            self.output("Connect to the room first.")
            return False
        if guid in set(self.ctx.slot_data.get("locked", [])):
            self.output(f"{RESIDENCE_NAMES[guid]} is shuffled in this seed: it unlocks when someone finds it.")
            return False
        self.ctx.force_unlocks.add(guid)
        if guid not in self.ctx.unlock_queue:
            self.ctx.unlock_queue.append(guid)
        self.ctx.next_unlock_at = 0.0
        self.ctx.state_dirty = True
        self.ctx.save_progress()
        how = "Switch to Anno 117 and leave the mouse alone for a moment; " if KeySender.available else ""
        self.output(f"Unlocking {RESIDENCE_NAMES[guid]}. {how}it is also applied every time you load a save.")
        return True

    def _cmd_resync(self) -> bool:
        """Rewrite the session file for the game and redo the bridge handshake."""
        self.ctx.state_dirty = True
        self.ctx.channel = "waiting"
        self.ctx.handshake_started = None
        self.output("Session file will be rewritten.")
        return True

    def _cmd_deliver(self) -> bool:
        """Keys mode: type waiting items into the game now (focus the game window within 3 seconds)."""
        if not KeySender.available:
            self.output("Typing items in through keys only works on Windows.")
            return False
        self.ctx.key_request_at = time.monotonic() + 3.0
        self.ctx.next_ping_at = 0.0
        self.output("Switch to Anno 117 now; delivery starts in 3 seconds.")
        return True


class Anno117Context(CommonContext):
    game = gd.GAME_NAME
    items_handling = 0b111  # the game cannot place items by itself, so the server sends all of them
    command_processor = Anno117CommandProcessor
    want_slot_data = True

    def __init__(self, server_address: str | None, password: str | None) -> None:
        super().__init__(server_address, password)
        settings = _settings()
        stored = Utils.persistent_load().get(STORE_CATEGORY, {})
        self.user_folder_override: str = stored.get("user_folder") or str(getattr(settings, "user_folder", "") or "")
        self.mode_setting: str = str(getattr(settings, "bridge_mode", "auto") or "auto").lower()
        self.key_delivery: str = str(getattr(settings, "item_typing", "idle") or "idle").lower()
        if self.key_delivery not in ("idle", "request", "auto"):
            self.key_delivery = "idle"

        self.user_folder: Path | None = None
        self.bridge_dir: Path | None = None
        self.next_path_check = 0.0
        self.warned: set[str] = set()
        self.tailer = bridge_files.LogTailer()
        self.keys = KeySender(int(getattr(settings, "key_press_ms", 50) or 50))

        self.slot_data: dict[str, Any] | None = None
        self.nonce = random.randint(1, 1_000_000)
        self.nonce_items: dict[int, int] = {}
        self.state_dirty = False
        self.last_write = 0.0
        self.consumed = 0

        self.channel = "waiting"  # waiting -> live | keys | startup
        self.game_hello: dict[str, str] | None = None
        self.game_seed: str | None = None
        self.game_items: int | None = None  # items the game is known to have
        self.handshake_started: float | None = None
        self.handshake_nonce: int | None = None
        self.key_ping_sent = False
        self.key_ping_busy = False
        self.key_unlock_busy = False
        self.next_unlock_at = 0.0
        self.next_ping_at = 0.0
        self.key_inflight: tuple[int, float, int] | None = None  # (item index, sent at, tries)
        self.key_expected_bits = 0
        self.force_unlocks: set[int] = set()    # residences the game holds back that this seed does not shuffle
        self.unlock_queue: list[int] = []       # of those, still to type in
        self.key_request_at: float | None = None
        self.key_delivered: set[int] = set()
        self.key_pause_until = 0.0
        self.last_restart_hint = 0.0
        self.early_messages: deque[bridge_files.GameMessage] = deque(maxlen=5000)  # before we were connected

    # ------------------------------------------------------------------ server side
    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Anno 117 Client"
        return ui

    @property
    def room_seed(self) -> str | None:
        """Seed of the room we are connected to (server_seed_name since AP 0.6.9, seed_name before)."""
        return getattr(self, "server_seed_name", None) or self.seed_name

    @property
    def store_key(self) -> str:
        return f"{self.room_seed}:{self.auth}"

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data") or {}
            protocol = self.slot_data.get("protocol")
            if protocol != gd.BRIDGE_PROTOCOL:
                logger.warning(f"This seed was made with bridge protocol {protocol}, the client speaks "
                               f"{gd.BRIDGE_PROTOCOL}. Use the apworld version the seed was generated with.")
            saved = Utils.persistent_load().get(STORE_CATEGORY, {}).get(self.store_key, {})
            self.consumed = int(saved.get("consumed", 0))
            self.nonce_items = {int(k): int(v) for k, v in saved.get("nonces", {}).items()}
            self.force_unlocks = {int(g) for g in saved.get("unlock", [])}
            self.channel = "waiting" if self.channel != "keys" else "keys"
            self.handshake_started = None
            self.handshake_nonce = None
            self.state_dirty = True
        elif cmd in ("ReceivedItems", "RoomUpdate"):
            self.state_dirty = True

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.slot_data = None
        await super().disconnect(allow_autoreconnect)

    def save_progress(self) -> None:
        if not self.room_seed or not self.auth:
            return
        recent = dict(sorted(self.nonce_items.items())[-30:])
        Utils.persistent_store(STORE_CATEGORY, self.store_key,
                               {"consumed": self.consumed, "nonces": {str(k): v for k, v in recent.items()},
                                "unlock": sorted(self.force_unlocks)})

    async def send_checks(self, ids: set[int]) -> None:
        new = await self.check_locations(ids)
        if new:
            names = ", ".join(sorted(self.location_names.lookup_in_game(i) for i in new))
            logger.info(f"Checked: {names}")

    # ------------------------------------------------------------------ game side
    def status_lines(self) -> list[str]:
        lines = [
            f"User folder: {self.user_folder or 'not found'}",
            f"Bridge folder: {self.bridge_dir or 'mod not installed'}",
            f"Channel: {self.channel} (setting: {self.mode_setting})",
        ]
        if self.game_hello:
            lines.append(f"Game bridge: version {self.game_hello.get('version')}, reads state via "
                         f"{self.game_hello.get('source')}, {self.game_hello.get('caps')}, seed {self.game_seed}")
        else:
            lines.append("Game bridge: no message from the game yet (load a save with the mod active).")
        if self.slot_data is not None:
            known = self.game_items if self.game_items is not None else "?"
            lines.append(f"Items received: {len(self.items_received)}, known to game: {known}, "
                         f"denarii caches applied: {self.consumed}")
        return lines

    def warn_once(self, key: str, message: str) -> None:
        if key not in self.warned:
            self.warned.add(key)
            logger.warning(message)

    def refresh_paths(self) -> None:
        now = time.monotonic()
        if now < self.next_path_check and self.user_folder and self.bridge_dir:
            return
        self.next_path_check = now + 5.0
        if not self.user_folder:
            self.user_folder = paths.find_user_folder(self.user_folder_override)
            if not self.user_folder:
                self.warn_once("folder", "Could not find your Anno 117 user folder (Documents/Anno 117). "
                                         "Start the game once, or set it with /anno_folder <path>.")
                return
            logger.info(f"Anno 117 user folder: {self.user_folder}")
        if not self.bridge_dir:
            self.bridge_dir = paths.find_bridge_dir(self.user_folder)
            if not self.bridge_dir:
                target = mod_install.install_mod(self.user_folder)
                logger.info(f"Installed the AP-Anno117 mod to {target}. If Anno 117 is running, restart it.")
                self.bridge_dir = paths.find_bridge_dir(self.user_folder)
            else:
                have, bundled = mod_install.installed_version(self.user_folder), mod_install.bundled_version()
                if have and bundled and have != bundled:
                    try:
                        mod_install.install_mod(self.user_folder)
                        logger.warning(f"Updated the AP-Anno117 game mod from {have} to {bundled}. If Anno 117 is "
                                       f"running, save and restart it to load the new version.")
                    except OSError as err:
                        self.warn_once("modversion", f"Installed mod is {have}, this client ships {bundled}, and "
                                                     f"updating it failed ({err}). Close Anno 117 and type "
                                                     f"/install_mod.")

    def write_state(self) -> None:
        if not (self.slot_data is not None and self.bridge_dir and self.room_seed):
            return
        now = time.monotonic()
        if now - self.last_write < WRITE_INTERVAL:
            return
        self.nonce += 1
        items = [item.item for item in self.items_received]
        text = bridge_files.render_state(
            nonce=self.nonce, seed=self.room_seed, slot=self.auth or "", denarii=self.slot_data.get("denarii", 10000),
            consumed=self.consumed, goal_count=self.slot_data.get("goal_count", 0),
            goal=self.slot_data.get("goal_tiers", []), locked=self.slot_data.get("locked", []),
            locations=self.missing_locations, items=items, bridge_dir=self.bridge_dir,
            protocol=gd.BRIDGE_PROTOCOL, unlock=self.force_unlocks, auto_unlock=self.auto_unlock_pairs(),
        )
        try:
            bridge_files.write_atomic(self.bridge_dir / bridge_files.STATE_FILE, text)
        except OSError as err:
            logger.debug(f"State file busy, retrying: {err}")
            self.nonce -= 1
            return
        self.nonce_items[self.nonce] = len(items)
        self.last_write = now
        self.state_dirty = False
        self.save_progress()

    async def handle_message(self, msg: bridge_files.GameMessage) -> None:
        if msg.seed not in ("-", "") and self.room_seed and msg.seed != self.room_seed:
            self.warn_once(f"seed:{msg.seed}", f"The game reports seed {msg.seed}, but you are connected to "
                                               f"{self.room_seed}. Restart Anno 117 to load this session.")
            return
        kind, payload = msg.kind, msg.payload
        if kind == "HELLO":
            fields = payload.split(",")
            self.game_hello = dict(zip(("protocol", "version", "caps", "source", "nonce"), fields))
            self.game_seed = msg.seed
            nonce = self.game_hello.get("nonce", "-")
            self.game_items = self.nonce_items.get(int(nonce)) if nonce.isdigit() else 0
            logger.info(f"Game bridge connected (reads state via {self.game_hello.get('source')}, "
                        f"{self.game_hello.get('caps')}).")
            if self.channel != "keys":
                self.channel = "waiting"
            self.handshake_started = None
            self.state_dirty = True
        elif kind == "ACK":
            if payload.isdigit():
                acked = int(payload)
                if acked in self.nonce_items:
                    self.game_items = max(self.game_items or 0, self.nonce_items[acked])
                if self.handshake_nonce is not None and acked >= self.handshake_nonce \
                        and self.channel not in ("live", "keys") and self.mode_setting != "keys":
                    self.channel = "live"
                    logger.info("The game picks up updates while it runs. Items arrive automatically.")
        elif kind == "CHECK":
            if payload.isdigit():
                await self.send_checks({int(payload)})
        elif kind == "SYNC":
            ids = {int(x) for x in payload.split(",") if x.isdigit()}
            if ids:
                await self.send_checks(ids)
        elif kind == "APPLIED":
            if payload.isdigit() and int(payload) > self.consumed:
                self.consumed = int(payload)
                self.save_progress()
        elif kind == "GOAL":
            if not self.finished_game and self.slot_data is not None:
                await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                self.finished_game = True
                logger.info("Goal reached. Ave!")
        elif kind == "KEYACK":
            if self.channel != "keys":
                self.channel = "keys"
                logger.info("Items will be typed into the game through the bridge keybinds.")
        elif kind == "UNLOCKED":
            if payload.isdigit():
                guid = int(payload)
                if guid in self.unlock_queue:
                    self.unlock_queue.remove(guid)
                logger.info(f"The game unlocked {RESIDENCE_NAMES.get(guid, guid)}.")
        elif kind == "KEYGOT" and payload.startswith("U"):
            if payload[1:].isdigit() and int(payload[1:]) in self.unlock_queue:
                self.unlock_queue.remove(int(payload[1:]))
        elif kind == "KEYGOT":
            if payload.isdigit():
                index = int(payload)
                self.key_delivered.add(index)
                if self.key_inflight and self.key_inflight[0] == index:
                    self.key_inflight = None
                known = self.game_items or 0
                while known + 1 in self.key_delivered:
                    known += 1
                self.game_items = known
        elif kind == "REQ":
            self.key_request_at = time.monotonic()
            self.key_pause_until = 0.0
        elif kind == "ERR":
            self.warn_once(f"err:{payload}", f"Game bridge error: {payload}")
        elif kind == "KEYERR":
            reason, _, got = payload.partition(",")
            expected = self.key_expected_bits
            if got.isdigit() and expected:
                if int(got) < expected:
                    detail = f"it only registered {got} of {expected} key presses, so the game is missing some"
                elif int(got) > expected:
                    detail = f"it registered {got} key presses but {expected} were sent (extra presses or key repeat)"
                else:
                    detail = "every key press arrived but some came through as the wrong key"
                logger.info(f"The game rejected a typed message ({reason}): {detail}. "
                            f"Raise key_press_ms in host.yaml (anno117_options) if this keeps happening.")
            else:
                self.warn_once(f"keyerr:{payload}", f"The game rejected a typed message ({payload}). If this keeps "
                                                    f"happening, raise key_press_ms in host.yaml (anno117_options).")
            if self.key_inflight:
                index, _, tries = self.key_inflight
                self.key_inflight = (index, 0.0, tries)  # retry right away, keeping the try count

    def handshake(self) -> None:
        """Works out how items can reach the game once it has said hello."""
        if self.game_hello is None or self.slot_data is None or self.channel in ("live", "keys"):
            return
        now = time.monotonic()
        if self.handshake_started is None:
            if self.last_write and not self.state_dirty:
                self.handshake_started = now
                self.handshake_nonce = self.nonce
            return
        waited = now - self.handshake_started
        if self.channel == "startup":
            self.retry_key_ping(now)
            return
        if waited < LIVE_TIMEOUT and self.mode_setting != "keys":
            return
        if self.mode_setting in ("auto", "keys") and self.keys.available:
            if not self.key_ping_sent and self.keys.game_focused() and not self.keys.mouse_busy() \
                    and self.keys.idle_seconds() >= IDLE_SECONDS:
                self.key_ping_sent = True
                self.handshake_started = now + 3600.0  # paused while typing; the ack window starts afterwards
                Utils.async_start(self._type_ping(f"P{self.nonce}"))
                return
            if not self.key_ping_sent:
                self.warn_once("focus", "Testing the keybind channel: switch to the Anno 117 window for a moment.")
                return  # wait until the game window is focused
        self.channel = "startup"
        self.next_ping_at = now + PING_RETRY
        if self.keys.available and self.mode_setting in ("auto", "keys"):
            logger.warning("The game did not answer the keybind test yet (it may still have been loading). The "
                           "client keeps retrying while Anno 117 is in front; until then, new items arrive when "
                           "you restart the game.")
        else:
            logger.warning("The game only reads the session when it starts. New items reach it the next time you "
                           "load a save after restarting Anno 117.")

    def retry_key_ping(self, now: float) -> None:
        """In startup mode, keep testing the keybind channel: one answer switches item delivery to keys."""
        if not (self.keys.available and self.mode_setting in ("auto", "keys")) or self.key_ping_busy:
            return
        requested = self.key_request_at is not None and now >= self.key_request_at
        if now < self.next_ping_at and not requested:
            return
        if not self.keys.game_focused() or self.keys.mouse_busy():
            return
        if not requested and self.keys.idle_seconds() < IDLE_SECONDS:
            return
        self.next_ping_at = now + PING_RETRY
        Utils.async_start(self._type_ping(f"P{self.nonce}", first=False))

    def auto_unlock_pairs(self) -> list[int]:
        """Flat {tier below, residence} pairs for every residence this seed does not shuffle."""
        slot = self.slot_data or {}
        locked = set(slot.get("locked", []))
        provinces = {"latium": {gd.REGION_LATIUM}, "albion": {gd.REGION_ALBION}}.get(
            slot.get("provinces", "both"), {gd.REGION_LATIUM, gd.REGION_ALBION})
        pairs: list[int] = []
        for t in sorted(gd.TIERS.values(), key=lambda t: (t.region, t.index, t.guid)):
            if t.parent is not None and t.region in provinces and t.residence not in locked:
                pairs += [t.parent, t.residence]
        return pairs

    def type_unlocks(self) -> None:
        """Types queued residence unlocks (/unlock_residence) in, one at a time, when the game is in front."""
        if not self.unlock_queue or not self.keys.available or self.key_ping_busy or self.key_unlock_busy:
            return
        if self.key_inflight or not self.keys.game_focused() or self.keys.mouse_busy():
            return
        now = time.monotonic()
        if now < self.next_unlock_at:
            return
        self.next_unlock_at = now + 20.0
        guid = self.unlock_queue[0]
        logger.info(f"Typing the unlock for {RESIDENCE_NAMES.get(guid, guid)} into Anno 117. Don't click for a moment.")
        Utils.async_start(self._type_unlock(guid))

    async def _type_unlock(self, guid: int) -> None:
        self.key_unlock_busy = True
        try:
            await asyncio.to_thread(self.keys.send, f"U{guid}")
        finally:
            self.key_unlock_busy = False

    def deliver_keys(self) -> None:
        if self.channel != "keys" or self.slot_data is None:
            return
        now = time.monotonic()
        if self.key_inflight:
            index, sent_at, tries = self.key_inflight
            if now - sent_at < KEY_ACK_TIMEOUT:
                return
            if tries >= KEY_RETRIES:
                logger.warning(f"Item #{index} was not confirmed by the game after {tries} tries; "
                               f"retrying in a minute (or press Shift+F5 in game). If this repeats, raise key_press_ms in host.yaml, "
                               f"or save and restart Anno 117 to receive everything at once.")
                self.key_inflight = None
                self.key_request_at = None
                self.key_pause_until = now + 60.0
                return
        known = self.game_items or 0
        pending = [i for i in range(known + 1, len(self.items_received) + 1) if i not in self.key_delivered]
        if not pending:
            self.key_request_at = None
            return
        requested = self.key_request_at is not None and now >= self.key_request_at
        if self.key_request_at is not None and not requested:
            return  # /deliver countdown running
        if not requested:
            if self.key_delivery == "request":
                self.waiting_hint(now, len(pending), "Press Shift+F5 in Anno 117 (on a laptop you may need "
                                                     "Fn+Shift+F5) or type /deliver here to receive them.")
                return
            if now < self.key_pause_until:
                return
        if not self.keys.game_focused() or self.keys.mouse_busy():
            if not requested:
                self.waiting_hint(now, len(pending), "They are typed in while Anno 117 is the active window.")
            return
        if self.key_delivery == "idle" and not requested and self.keys.idle_seconds() < IDLE_SECONDS:
            self.waiting_hint(now, len(pending), "They are typed in as soon as you stop clicking for a moment.")
            return
        index = self.key_inflight[0] if self.key_inflight else pending[0]
        tries = self.key_inflight[2] + 1 if self.key_inflight else 1
        item_id = self.items_received[index - 1].item
        self.key_inflight = (index, now + 3600.0, tries)  # the ack timer starts once typing has finished
        body = f"I{index},{item_id - gd.ITEM_BASE}"
        self.key_expected_bits = len(frame(body)) * 8
        seconds = (self.key_expected_bits + 2) * 2 * getattr(self.keys, "press_seconds", 0.05)
        logger.info(f"Typing item #{index} into Anno 117 (try {tries}, about {seconds:.0f} s). "
                    f"Keep the game in front and don't click until it's done.")
        Utils.async_start(self._type_item(index, tries, body))

    async def _type_ping(self, body: str, first: bool = True) -> None:
        self.key_ping_busy = True
        try:
            ok = await asyncio.to_thread(self.keys.send, body)
        finally:
            self.key_ping_busy = False
        if not first:
            return  # retries just wait for a KEYACK, which switches the channel whenever it comes
        if not ok:
            self.key_ping_sent = False  # lost focus: try again when the game is in front
        # give the game 10 s after the last key to answer
        self.handshake_started = time.monotonic() - LIVE_TIMEOUT + 10.0

    async def _type_item(self, index: int, tries: int, body: str) -> None:
        ok = await asyncio.to_thread(self.keys.send, body)
        if not self.key_inflight or self.key_inflight[0] != index:
            return  # already confirmed (or given up) meanwhile
        if ok:
            self.key_inflight = (index, time.monotonic(), tries)
        else:
            # focus was lost mid-message: this attempt does not count
            self.key_inflight = (index, 0.0, tries - 1) if tries > 1 else None

    def waiting_hint(self, now: float, count: int, how: str) -> None:
        if now - self.last_restart_hint > 120:
            self.last_restart_hint = now
            logger.info(f"{count} item(s) waiting. {how}")

    def restart_hint(self) -> None:
        if self.channel != "startup" or self.game_items is None:
            return
        waiting = len(self.items_received) - self.game_items
        now = time.monotonic()
        if waiting > 0 and now - self.last_restart_hint > 300:
            self.last_restart_hint = now
            if self.keys.available and self.mode_setting in ("auto", "keys"):
                logger.info(f"{waiting} item(s) waiting for the game. The client keeps trying to type them in: "
                            f"keep Anno 117 in front and stop clicking for a moment, or type /deliver. Restarting "
                            f"Anno 117 and loading your save also delivers them.")
            else:
                logger.info(f"{waiting} item(s) waiting for the game. Save, restart Anno 117 and load your save "
                            f"to receive them.")

    async def bridge_step(self) -> None:
        self.refresh_paths()
        if not self.user_folder:
            return
        files = paths.log_files(self.user_folder)
        if self.bridge_dir:
            files.append(self.bridge_dir / bridge_files.OUTBOX_FILE)
        connected = self.slot_data is not None and self.room_seed is not None
        if connected and self.early_messages:
            early = list(self.early_messages)
            self.early_messages.clear()
            for msg in early:
                await self.handle_message(msg)
        for line in self.tailer.poll(files):
            msg = bridge_files.parse_message(line)
            if not msg:
                continue
            if connected:
                await self.handle_message(msg)
            else:
                # we cannot tell yet whether these belong to our seed; replay them once connected
                self.early_messages.append(msg)
        if self.state_dirty:
            self.write_state()
        self.handshake()
        self.deliver_keys()
        self.type_unlocks()
        self.restart_hint()


async def game_loop(ctx: Anno117Context) -> None:
    last_error = ""
    while not ctx.exit_event.is_set():
        try:
            await ctx.bridge_step()
        except Exception as err:  # noqa: BLE001 - keep the client alive, report once per distinct error
            if str(err) != last_error:
                last_error = str(err)
                logger.exception(f"Anno 117 bridge error: {err}")
        await asyncio.sleep(STEP_SECONDS)


async def main(args) -> None:
    ctx = Anno117Context(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    bridge_task = asyncio.create_task(game_loop(ctx), name="Anno117 bridge")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    await ctx.exit_event.wait()
    bridge_task.cancel()
    await ctx.shutdown()


def launch_client(*args: str) -> None:
    import colorama

    parser = get_base_parser(description="Anno 117 Client, connects Anno 117 to Archipelago.")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    parsed = parser.parse_args(args)
    try:
        from CommonClient import handle_url_arg

        parsed = handle_url_arg(parsed, parser=parser)
    except ImportError:
        pass
    Utils.init_logging("Anno117Client", exception_logger="Client")
    colorama.just_fix_windows_console()
    asyncio.run(main(parsed))
    colorama.deinit()
