from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from . import gamedata as gd

if TYPE_CHECKING:
    from .world import Anno117World


class Anno117Item(Item):
    game = gd.GAME_NAME


MAX_PROGRESSION_SHARE = 0.75


ITEM_NAME_TO_ID: dict[str, int] = {}
for _tier in gd.TIERS.values():
    if _tier.parent is not None:
        ITEM_NAME_TO_ID[_tier.upgrade_item_name] = _tier.upgrade_item_id
for _b in gd.BUILDINGS.values():
    ITEM_NAME_TO_ID[_b.name] = _b.item_id
ITEM_NAME_TO_ID[gd.FILLER_ITEM_NAME] = gd.FILLER_ITEM_ID

ITEM_GROUPS: dict[str, set[str]] = {
    "Residence Upgrades": {t.upgrade_item_name for t in gd.TIERS.values() if t.parent is not None},
    "Latium Buildings": {b.name for b in gd.BUILDINGS.values() if b.region == gd.REGION_LATIUM},
    "Albion Buildings": {b.name for b in gd.BUILDINGS.values() if b.region == gd.REGION_ALBION},
    "Military Buildings": {b.name for b in gd.BUILDINGS.values() if b.military},
    "Construction Material Buildings": {
        b.name for b in gd.BUILDINGS.values() if b.outputs & gd.CONSTRUCTION_PRODUCTS and not b.military
    },
}

ITEM_DESCRIPTIONS: dict[str, str] = {
    gd.FILLER_ITEM_NAME: "Adds denarii to your treasury (amount set by the Denarii per Cache option).",
    "Residence Upgrades": "Lets residences upgrade to this tier.",
}
for _tier in gd.TIERS.values():
    if _tier.parent is not None:
        ITEM_DESCRIPTIONS[_tier.upgrade_item_name] = (
            f"Lets {gd.TIERS[_tier.parent].name} residences in {_tier.province} upgrade to {_tier.name}."
        )
for _b in gd.BUILDINGS.values():
    _made = ", ".join(sorted(gd.PRODUCT_NAMES.get(p, str(p)) for p in _b.outputs))
    ITEM_DESCRIPTIONS[_b.name] = f"Unlocks the {_b.base_name} in {_b.province} (produces {_made})."


def create_item(world: Anno117World, name: str) -> Anno117Item:
    # item link groups call this on a world that never ran generate_early, so it has no plan
    progression = getattr(world, "progression_names", None)
    if name == gd.FILLER_ITEM_NAME:
        classification = ItemClassification.filler
    elif progression is None or name in progression:
        classification = ItemClassification.progression
    else:
        classification = ItemClassification.useful
    return Anno117Item(name, classification, ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: Anno117World, exclude: set[str] = frozenset()) -> None:
    plan = world.plan
    pool = [world.create_item(name) for name in plan.item_names if name not in exclude]
    open_locations = len(world.multiworld.get_unfilled_locations(world.player))
    # Keep at least a quarter of the locations for filler, so placement always has room to move.
    surplus = len(pool) - int(open_locations * MAX_PROGRESSION_SHARE)
    if surplus > 0:
        # Too few checks for every unlock (e.g. building checks off): hand the extras out at the start,
        # lowest tiers first, so what stays shuffled are late unlocks that early checks can hold.
        rank = {t.upgrade_item_name: t.index for t in plan.upgrade_tiers}
        rank.update({b.name: gd.TIERS[b.tier].index for b in plan.item_buildings})
        pool.sort(key=lambda item: (rank[item.name], world.random.random()))
        for item in pool[:surplus]:
            world.push_precollected(item)
        pool = pool[surplus:]
    pool += [world.create_filler() for _ in range(open_locations - len(pool))]
    world.multiworld.itempool += pool
