"""Seed plan (what is shuffled) and the production logic used by access rules.

Anno's progression is a web, not a tree: a tier needs goods, goods need buildings, and buildings need
workers from a tier. Each tier has three levels:
    unlocked     the previous tier is established and its residence upgrade is owned; when residences are not
                 shuffled the game unlocks the tier itself, so logic waits until the previous tier is sustained
    established  one good of every needs category plus the tier's building materials (enough to upgrade)
    sustained    every good that adds residents (the biggest milestones and the goal)
Access rules evaluate a fixed point ("which tiers are at which level, which goods can I make") that is kept
on the collection state. Collecting items only ever adds to it, so it is
extended incrementally; removing an item drops it and it is rebuilt on the next rule check.
Products, tiers and provinces are bit positions so every test is an integer operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from BaseClasses import CollectionState, MultiWorld
from Options import OptionError
from worlds.AutoWorld import LogicMixin

from . import gamedata as gd
from .options import Goal, Provinces, StartingProvince

if TYPE_CHECKING:
    from .world import Anno117World


UNLOCKED, ESTABLISHED, SUSTAINED = 1, 2, 3


@dataclass(frozen=True)
class Milestone:
    tier: gd.Tier
    threshold_index: int
    value: int
    level: int

    @property
    def name(self) -> str:
        return self.tier.milestone_name(self.value)

    @property
    def location_id(self) -> int:
        return self.tier.milestone_id(self.threshold_index)


@dataclass
class Plan:
    regions: tuple[str, ...]
    start_region: str
    other_region: str | None
    other_access_tiers: tuple[int, ...]
    tiers: tuple[gd.Tier, ...]
    buildings: tuple[gd.Building, ...]  # every building in play (starters included)
    starters: frozenset[int]
    item_buildings: tuple[gd.Building, ...]
    upgrade_tiers: tuple[gd.Tier, ...]
    goal_tiers: tuple[gd.Tier, ...]
    milestones: tuple[Milestone, ...]
    build_checks: tuple[gd.Building, ...]

    @property
    def item_names(self) -> list[str]:
        return [t.upgrade_item_name for t in self.upgrade_tiers] + [b.name for b in self.item_buildings]

    @property
    def progression_names(self) -> frozenset[str]:
        return frozenset(self.item_names) - {b.name for b in self.item_buildings if b.guid in gd.UNRELIABLE_BUILDINGS}

    @property
    def locked_guids(self) -> list[int]:
        return sorted([t.residence for t in self.upgrade_tiers] + [b.guid for b in self.item_buildings])


_TOP_TIER_BY_GOAL = {Goal.option_patricians: 1498, Goal.option_aldermen: 1502, Goal.option_nobles: 1504}


def make_plan(world: Anno117World) -> Plan:
    opts = world.options
    if opts.provinces == Provinces.option_latium:
        start, other = gd.REGION_LATIUM, None
    elif opts.provinces == Provinces.option_albion:
        start, other = gd.REGION_ALBION, None
    else:
        start = gd.REGION_LATIUM if opts.starting_province == StartingProvince.option_latium else gd.REGION_ALBION
        other = gd.REGION_ALBION if start == gd.REGION_LATIUM else gd.REGION_LATIUM
    regions = (start,) if other is None else (start, other)

    tiers = tuple(t for r in regions for t in gd.tiers_in(r))
    # residence upgrades are items only when shuffled; otherwise the game unlocks tiers the normal way
    upgrade_tiers = tuple(t for t in tiers if t.parent is not None) if opts.shuffle_residences else ()
    # the game opens the second province once the first has third-tier residents (Equites, Aldermen or Nobles)
    other_access = tuple(t.guid for t in gd.tiers_in(start) if t.index == gd.PROVINCE_ACCESS_TIER)

    buildings = []
    for b in gd.BUILDINGS.values():
        if b.region not in regions:
            continue
        if b.dlc and not (opts.prophecies_of_ash and set(b.dlc) <= {gd.DLC_PROPHECIES_OF_ASH}):
            continue
        buildings.append(b)
    starters = frozenset(g for r in regions for g in gd.STARTER_BUILDINGS[r])
    item_buildings = tuple(
        b for b in buildings if b.guid not in starters and (opts.military_buildings or not b.military)
    )

    auto_goal = [1498] if start == gd.REGION_LATIUM else [1502]
    if opts.goal == Goal.option_auto:
        goal_guids = auto_goal
    elif opts.goal == Goal.option_all_top_tiers:
        goal_guids = [g for r in regions for g in ([1498] if r == gd.REGION_LATIUM else [1502, 1504])]
    else:
        goal_guids = [_TOP_TIER_BY_GOAL[opts.goal.value]]
        if gd.TIERS[goal_guids[0]].region not in regions:
            import logging

            logging.warning(f"Anno 117 ({world.player_name}): goal {gd.TIERS[goal_guids[0]].name} is not in the "
                            f"chosen provinces; using {gd.TIERS[auto_goal[0]].name} instead.")
            goal_guids = auto_goal
    goal_tiers = tuple(gd.TIERS[g] for g in goal_guids)

    def level(tier: gd.Tier, value: int) -> int:
        if value <= gd.SMALL_MILESTONE:
            return UNLOCKED
        if value <= gd.tier_cap(tier, opts.milestone_cap.value) * gd.ESTABLISHED_SHARE:
            return ESTABLISHED
        return SUSTAINED

    milestones = tuple(
        Milestone(t, i, v, level(t, v))
        for t in tiers
        for i, v in gd.milestone_thresholds(t, opts.milestones_per_tier.value, opts.milestone_cap.value)
    )
    # every building in play is a check, starters included: they give each world free early locations
    build_checks = tuple(b for b in buildings if (b in item_buildings or b.guid in starters)
                         and b.guid not in gd.UNRELIABLE_BUILDINGS) if opts.building_checks else ()

    plan = Plan(regions, start, other, other_access, tiers, tuple(buildings), starters, item_buildings,
                upgrade_tiers, goal_tiers, milestones, build_checks)

    # Drop checks that cannot be done even with every item (for example a tier whose goods only come from
    # the other province), and refuse goals that cannot be reached.
    logic = Anno117Logic(world.player, plan)
    everything = logic.evaluate(lambda _name: True)
    plan.milestones = tuple(m for m in plan.milestones if logic.at_level(everything, m.tier.guid, m.level))
    plan.build_checks = tuple(b for b in plan.build_checks if logic.can_build(everything, b))
    for t in goal_tiers:
        if not logic.sustained(everything, t.guid):
            raise OptionError(f"Anno 117 ({world.player_name}): goal tier {t.name} cannot be supplied "
                              f"with the selected options.")
    return plan


class Work:
    """The fixed point for one player on one collection state."""
    __slots__ = ("owned", "regions", "unlocked", "established", "sustained", "products", "pending", "open_tiers",
                 "new_items")

    def __init__(self) -> None:
        self.owned: set[str] = set()
        self.regions = 0
        self.unlocked = 0
        self.established = 0
        self.sustained = 0
        self.products = 0
        self.pending: list[int] = []      # building indices not producing yet
        self.open_tiers: list[int] = []   # tier indices not sustained yet
        self.new_items: list[str] = []    # collected since the last propagation

    def copy(self) -> Work:
        w = Work.__new__(Work)
        w.owned = set(self.owned)
        w.regions, w.unlocked, w.established = self.regions, self.unlocked, self.established
        w.sustained, w.products = self.sustained, self.products
        w.pending = list(self.pending)
        w.open_tiers = list(self.open_tiers)
        w.new_items = list(self.new_items)
        return w


class Anno117Logic:
    def __init__(self, player: int, plan: Plan) -> None:
        self.player = player
        self.plan = plan
        self.item_names = frozenset(plan.item_names)

        region_bits = {r: 1 << i for i, r in enumerate(gd.PROVINCE_NAMES)}
        self.region_bit = region_bits
        self.start_bit = region_bits[plan.start_region]
        self.other_bit = region_bits[plan.other_region] if plan.other_region else 0

        self.tier_bit = {t.guid: 1 << i for i, t in enumerate(plan.tiers)}
        # Goods are tracked per province: logic never counts on shipping a good from the other province.
        products = sorted({(b.region, p) for b in plan.buildings for p in b.inputs | b.outputs}
                          | {(t.region, p) for t in plan.tiers
                             for p in gd.CORE_PRODUCTS[t.guid] | gd.TIER_CONSTRUCTION[t.guid]}
                          | {(t.region, p) for t in plan.tiers
                             for goods in gd.CATEGORY_PRODUCTS[t.guid].values() for p in goods})
        self.product_bit = {key: 1 << i for i, key in enumerate(products)}

        def mask(items, region: str) -> int:
            m = 0
            for p in items:
                m |= self.product_bit[(region, p)]
            return m

        self.access_mask = sum(self.tier_bit[g] for g in plan.other_access_tiers) if plan.other_region else 0
        # tiers: (bit, region bit, parent bit or 0, upgrade item or None,
        #         one-of masks per needs category, building material mask, core goods mask)
        self.tiers = [
            (self.tier_bit[t.guid], region_bits[t.region], self.tier_bit.get(t.parent, 0) if t.parent else 0,
             t.upgrade_item_name if t in plan.upgrade_tiers else None,
             tuple(mask(goods, t.region) for goods in gd.CATEGORY_PRODUCTS[t.guid].values()),
             mask(gd.TIER_CONSTRUCTION[t.guid], t.region), mask(gd.CORE_PRODUCTS[t.guid], t.region))
            for t in sorted(plan.tiers, key=lambda t: t.index)
        ]
        item_building_names = {b.guid: b.name for b in plan.item_buildings}
        in_play = [b for b in plan.buildings if b.guid in plan.starters or b.guid in item_building_names]
        # the tiers at which the game would normally offer a building (0 = no gate beyond its workers)
        self.gate_bit = {b.guid: sum(self.tier_bit[g] for g in gd.UNLOCK_GATES.get(b.guid, ()))
                         for b in plan.buildings}
        # buildings: (region bit, tier bit, input mask, output mask, item name or None, gate mask)
        # unreliable ones (gd.UNRELIABLE_BUILDINGS) produce nothing as far as logic is concerned
        self.buildings = [
            (region_bits[b.region], self.tier_bit[b.tier], mask(b.inputs, b.region),
             0 if b.guid in gd.UNRELIABLE_BUILDINGS else mask(b.outputs, b.region),
             item_building_names.get(b.guid), self.gate_bit[b.guid])
            for b in in_play
        ]
        self.always_available = [i for i, b in enumerate(self.buildings) if b[4] is None]
        self.buildings_by_item = {b[4]: i for i, b in enumerate(self.buildings) if b[4] is not None}

    # ---- evaluation
    def _new_work(self, has: Callable[[str], bool]) -> Work:
        w = Work()
        w.owned = {name for name in self.item_names if has(name)}
        w.regions = self.start_bit
        w.pending = list(self.always_available) + [self.buildings_by_item[n] for n in w.owned
                                                    if n in self.buildings_by_item]
        w.open_tiers = list(range(len(self.tiers)))
        self._propagate(w)
        return w

    def _propagate(self, w: Work) -> None:
        if w.new_items:
            for name in w.new_items:
                if name not in w.owned:
                    w.owned.add(name)
                    index = self.buildings_by_item.get(name)
                    if index is not None:
                        w.pending.append(index)
            w.new_items = []
        tiers, buildings, owned = self.tiers, self.buildings, w.owned
        changed = True
        while changed:
            changed = False
            if self.other_bit and not w.regions & self.other_bit and w.established & self.access_mask:
                w.regions |= self.other_bit
                changed = True
            still_open = []
            for t in w.open_tiers:
                bit, region, parent, upgrade, categories, materials, core = tiers[t]
                if w.regions & region:
                    if not w.unlocked & bit and (not parent or (
                            (w.established & parent and upgrade in owned) if upgrade else w.sustained & parent)):
                        w.unlocked |= bit
                        changed = True
                    if w.unlocked & bit and not w.established & bit and not materials & ~w.products \
                            and all(goods & w.products for goods in categories):
                        w.established |= bit
                        changed = True
                    if w.established & bit and not core & ~w.products:
                        w.sustained |= bit
                        changed = True
                        continue
                still_open.append(t)
            w.open_tiers = still_open
            still_pending = []
            for i in w.pending:
                region, tier, inputs, outputs, _, gate = buildings[i]
                if w.regions & region and w.unlocked & tier and (not gate or w.unlocked & gate) \
                        and not inputs & ~w.products:
                    if outputs & ~w.products:
                        w.products |= outputs
                        changed = True
                else:
                    still_pending.append(i)
            w.pending = still_pending

    def evaluate(self, has: Callable[[str], bool]) -> Work:
        return self._new_work(has)

    def status(self, state: CollectionState) -> Work:
        cache = state.anno117_work
        w = cache.get(self.player)
        if w is None:
            w = self._new_work(lambda name: state.has(name, self.player))
            cache[self.player] = w
        elif w.new_items:
            self._propagate(w)
        return w

    # ---- queries on a Work
    def unlocked(self, w: Work, tier_guid: int) -> bool:
        return bool(w.unlocked & self.tier_bit[tier_guid])

    def established(self, w: Work, tier_guid: int) -> bool:
        return bool(w.established & self.tier_bit[tier_guid])

    def sustained(self, w: Work, tier_guid: int) -> bool:
        return bool(w.sustained & self.tier_bit[tier_guid])

    def at_level(self, w: Work, tier_guid: int, level: int) -> bool:
        bits = w.unlocked if level == UNLOCKED else w.established if level == ESTABLISHED else w.sustained
        return bool(bits & self.tier_bit[tier_guid])

    def region_open(self, w: Work, region: str) -> bool:
        return bool(w.regions & self.region_bit[region])

    def can_build(self, w: Work, building: gd.Building) -> bool:
        """Province reachable, its workers exist and the game would offer it by now (see gd.UNLOCK_GATES).
        Building materials are not required: traders sell them."""
        gate = self.gate_bit.get(building.guid, 0)
        return bool(w.regions & self.region_bit[building.region] and w.unlocked & self.tier_bit[building.tier]
                    and (not gate or w.unlocked & gate))

    # ---- hooks from World.collect / World.remove
    def on_collect(self, state: CollectionState, name: str) -> None:
        if name in self.item_names:
            w = state.anno117_work.get(self.player)
            if w is not None:
                w.new_items.append(name)

    def on_remove(self, state: CollectionState, name: str) -> None:
        if name in self.item_names:
            state.anno117_work.pop(self.player, None)


class Anno117State(LogicMixin):
    anno117_work: dict[int, Work]

    def init_mixin(self, multiworld: MultiWorld) -> None:
        self.anno117_work = {}

    def copy_mixin(self, new_state: CollectionState) -> CollectionState:
        new_state.anno117_work = {player: w.copy() for player, w in self.anno117_work.items()}
        return new_state
