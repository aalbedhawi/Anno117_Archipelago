from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import settings
from BaseClasses import CollectionState, Item
from worlds.AutoWorld import World

from . import gamedata as gd
from . import items, locations
from .logic import Anno117Logic, Plan, make_plan
from .options import Anno117Options, EarlyUpgrade
from .web_world import Anno117WebWorld


class Anno117Settings(settings.Group):
    class UserFolder(str):
        """
        Your Anno 117 user folder: the one that contains the "mods" and "log" folders, usually
        Documents/Anno 117. Leave empty to detect it automatically.
        """

    class BridgeMode(str):
        """
        How the client gets received items into the game: "auto" (try files, then keys), "files" (never use keys)
        or "keys" (always type items in through keybinds; Windows only).
        """

    class KeyDelivery(str):
        """
        Keys mode only. How waiting items get typed into the game.
        "idle": whenever Anno 117 is the active window and you haven't clicked or pressed a key for a moment
        (moving the mouse is fine). Typing stops the moment you click and resumes when you pause.
        "request": only when you press Shift+F5 in game or type /deliver in the client.
        "auto": whenever Anno 117 is the active window and no mouse button is held, even while you play.
        """

    user_folder: UserFolder = UserFolder("")
    bridge_mode: BridgeMode = BridgeMode("auto")
    class KeyPressMs(int):
        """
        Keys mode only: how long each typed key is held, in milliseconds. Raise it (e.g. 80) if the client reports
        items "not confirmed by the game"; lower it to type faster.
        """

    item_typing: KeyDelivery = KeyDelivery("idle")
    key_press_ms: KeyPressMs = KeyPressMs(50)


PHASE_FILL_SHARE = 0.6  # at most this share of a phase's checks (and earlier ones) is reserved for its items


class Anno117World(World):
    """
    Anno 117: Pax Romana is a city builder set in the Roman Empire. In this randomizer, production buildings
    (and optionally residence upgrades) are shuffled into the multiworld. Population milestones and first constructions
    send items to other players.
    """

    game = gd.GAME_NAME
    web = Anno117WebWorld()
    options_dataclass = Anno117Options
    options: Anno117Options
    settings: ClassVar[Anno117Settings]
    settings_key = "anno117_options"
    topology_present = False

    item_name_to_id = items.ITEM_NAME_TO_ID
    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_groups = items.ITEM_GROUPS
    location_name_groups = locations.LOCATION_GROUPS

    plan: Plan
    logic: Anno117Logic
    progression_names: frozenset[str]

    def generate_early(self) -> None:
        self.plan = make_plan(self)
        self.logic = Anno117Logic(self.player, self.plan)
        self.progression_names = self.plan.progression_names

    def create_regions(self) -> None:
        locations.create_regions(self)
        locations.create_all_locations(self)

    def create_items(self) -> None:
        early = self.place_early_upgrade()
        items.create_all_items(self, exclude=early)
        if self.options.early_materials:
            for name in self.early_material_names():
                self.multiworld.early_items[self.player][name] = 1

    def early_material_names(self) -> list[str]:
        """The starting province's early building-material buildings that are shuffled and in the pool."""
        pool = {i.name for i in self.multiworld.itempool if i.player == self.player}
        return [b.name for b in self.plan.item_buildings
                if b.region == self.plan.start_region and gd.PHASE_BY_BUILDING_NAME.get(b.base_name) == gd.EARLY
                and b.name in pool]

    def place_early_upgrade(self) -> set[str]:
        """Brings the start province's tier-2 upgrade(s) forward, so the first residents can upgrade soon.
        Returns the item names already placed or given, which then stay out of the pool."""
        mode = self.options.early_upgrade.value
        if mode == EarlyUpgrade.option_off:
            return set()
        base = gd.base_tier(self.plan.start_region)
        names = [t.upgrade_item_name for t in self.plan.upgrade_tiers if t.parent == base.guid]
        if mode == EarlyUpgrade.option_start:
            for name in names:
                self.push_precollected(self.create_item(name))
            return set(names)
        # Truly early spots: buildings you have from the start, then the first two milestones of the base tier.
        starters = [self.get_location(b.location_name) for b in self.plan.build_checks
                    if b.guid in self.plan.starters and b.region == self.plan.start_region]
        first = sorted((m for m in self.plan.milestones if m.tier.guid == base.guid), key=lambda m: m.value)[:2]
        spots = [loc for loc in starters + [self.get_location(m.name) for m in first] if loc.item is None]
        self.random.shuffle(spots)
        placed = set()
        for name in names:
            if spots:
                spots.pop().place_locked_item(self.create_item(name))
                placed.add(name)
            else:
                self.multiworld.local_early_items[self.player][name] = 1
        return placed

    def phase_in(self, region: str, phase: int) -> int:
        # the second province only opens with the home province's third tier: nothing there is early
        return phase if region == self.plan.start_region else max(phase, gd.MIDDLE)

    def location_phases(self) -> dict[str, int]:
        plan = self.plan
        phases = {m.name: self.phase_in(m.tier.region, gd.tier_phase(m.tier)) for m in plan.milestones}
        phases.update({b.location_name: self.phase_in(b.region, gd.building_phase(b)) for b in plan.build_checks})
        return phases

    def item_phases(self) -> dict[str, int]:
        plan = self.plan
        # second-province items can't be used before it opens, so like its checks they are middle at the earliest
        phases = {b.name: self.phase_in(b.region, gd.building_phase(b)) for b in plan.item_buildings}
        for t in plan.upgrade_tiers:  # an upgrade is needed by the tier below it
            phases[t.upgrade_item_name] = self.phase_in(t.region, gd.tier_phase(gd.TIERS[t.parent]))
        return phases

    def apply_tiered_placement(self) -> None:
        """Own progression items only go into checks of their phase or earlier (see TieredPlacement)."""
        plan, player = self.plan, self.player
        loc_rank = self.location_phases()
        item_rank = self.item_phases()

        open_locs = [loc for loc in self.multiworld.get_locations(player) if loc.address is not None
                     and loc.item is None and loc.name in loc_rank]
        pool = [i for i in self.multiworld.itempool if i.player == player and i.name in item_rank and i.advancement]
        # Make sure every phase keeps room to spare: where early checks are scarce (few milestones, no building
        # checks, everything from both provinces), the overflow is allowed one phase later. Second-province items
        # move first, since you can only use them later anyway.
        ranks = {k: item_rank[item.name] for k, item in enumerate(pool)}
        for r in range(gd.EARLY, gd.LATE):
            # 60%: a phase's own items also have to leave room for the later items that logic needs earlier
            room = int(sum(1 for loc in open_locs if loc_rank[loc.name] <= r) * PHASE_FILL_SHARE)
            low = [k for k, v in ranks.items() if v <= r]
            if len(low) > room:
                self.random.shuffle(low)
                movable = [k for k in low if ranks[k] == r] or low
                home = {b.name for b in plan.item_buildings if b.region == plan.start_region}
                movable.sort(key=lambda k: pool[k].name in home)
                for k in movable[:len(low) - room]:
                    ranks[k] = r + 1
        self.item_rank = {}
        for k, rank in ranks.items():
            name = pool[k].name
            self.item_rank[name] = max(self.item_rank.get(name, 0), rank)

        for loc in open_locs:
            r = loc_rank[loc.name]
            # only progression is held to its phase: the few useful-only items (coal mines) may go anywhere,
            # which keeps the last, least flexible fill step from running out of spots
            loc.item_rule = lambda item, r=r, old=loc.item_rule: \
                (item.player != player or not item.advancement or self.item_rank.get(item.name, 99) >= r) \
                and old(item)

    def create_item(self, name: str) -> items.Anno117Item:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return gd.FILLER_ITEM_NAME

    def set_rules(self) -> None:
        logic, player = self.logic, self.player

        if self.plan.other_region:
            other = gd.PROVINCE_NAMES[self.plan.other_region]
            region_code = self.plan.other_region
            self.get_entrance(f"Sail to {other}").access_rule = \
                lambda state: logic.region_open(logic.status(state), region_code)

        for m in self.plan.milestones:
            self.get_location(m.name).access_rule = \
                lambda state, g=m.tier.guid, lvl=m.level: logic.at_level(logic.status(state), g, lvl)

        for b in self.plan.build_checks:
            loc = self.get_location(b.location_name)
            if b.guid in self.plan.starters:
                loc.access_rule = lambda state, b=b: logic.can_build(logic.status(state), b)
            else:
                loc.access_rule = lambda state, b=b: state.has(b.name, player) and logic.can_build(logic.status(state), b)

        # With milestones as the only checks there is too little room to hold items to phases without risking
        # an unfillable seed, so Tiered Placement needs building checks.
        if self.options.tiered_placement and self.plan.build_checks:
            self.apply_tiered_placement()

        goal_guids = tuple(t.guid for t in self.plan.goal_tiers)

        def goal_rule(state: CollectionState) -> bool:
            w = logic.status(state)
            return all(logic.sustained(w, g) for g in goal_guids)

        self.get_location(gd.GOAL_LOCATION_NAME).access_rule = goal_rule
        self.multiworld.completion_condition[player] = lambda state: state.has(gd.VICTORY_ITEM_NAME, player)

    def collect(self, state: CollectionState, item: Item) -> bool:
        changed = super().collect(state, item)
        if changed and hasattr(self, "logic"):
            self.logic.on_collect(state, item.name)
        return changed

    def remove(self, state: CollectionState, item: Item) -> bool:
        changed = super().remove(state, item)
        if changed and hasattr(self, "logic"):
            self.logic.on_remove(state, item.name)
        return changed

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            "protocol": gd.BRIDGE_PROTOCOL,
            "world_version": gd.WORLD_VERSION,
            "locked": self.plan.locked_guids,
            "goal_tiers": [t.guid for t in self.plan.goal_tiers],
            "goal_count": self.options.goal_population.value,
            "denarii": self.options.denarii_per_cache.value,
            "provinces": self.options.provinces.current_key,
            "start_province": gd.PROVINCE_NAMES[self.plan.start_region],
        }
