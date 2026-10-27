from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, Region

from . import gamedata as gd
from .items import Anno117Item

if TYPE_CHECKING:
    from .world import Anno117World


class Anno117Location(Location):
    game = gd.GAME_NAME


LOCATION_NAME_TO_ID: dict[str, int] = {}
for _tier in gd.TIERS.values():
    for _index, _value in enumerate(gd.THRESHOLDS):
        LOCATION_NAME_TO_ID[_tier.milestone_name(_value)] = _tier.milestone_id(_index)
for _b in gd.BUILDINGS.values():
    LOCATION_NAME_TO_ID[_b.location_name] = _b.location_id

LOCATION_GROUPS: dict[str, set[str]] = {
    "Population": {_tier.milestone_name(v) for _tier in gd.TIERS.values() for v in gd.THRESHOLDS},
    "Construction": {b.location_name for b in gd.BUILDINGS.values()},
    "Latium": {n for t in gd.TIERS.values() if t.region == gd.REGION_LATIUM
               for n in (t.milestone_name(v) for v in gd.THRESHOLDS)}
              | {b.location_name for b in gd.BUILDINGS.values() if b.region == gd.REGION_LATIUM},
    "Albion": {n for t in gd.TIERS.values() if t.region == gd.REGION_ALBION
               for n in (t.milestone_name(v) for v in gd.THRESHOLDS)}
              | {b.location_name for b in gd.BUILDINGS.values() if b.region == gd.REGION_ALBION},
}
for _tier in gd.TIERS.values():
    LOCATION_GROUPS[_tier.name] = {_tier.milestone_name(v) for v in gd.THRESHOLDS}

LOCATION_DESCRIPTIONS: dict[str, str] = {
    "Population": "Reach this many residents of the tier at once, across all your islands.",
    "Construction": "Construct your first copy of this building (checked while your camera is in its province).",
}


def create_all_locations(world: Anno117World) -> None:
    plan = world.plan
    for m in plan.milestones:
        region = world.get_region(gd.PROVINCE_NAMES[m.tier.region])
        region.locations.append(Anno117Location(world.player, m.name, m.location_id, region))
    for b in plan.build_checks:
        region = world.get_region(b.province)
        region.locations.append(Anno117Location(world.player, b.location_name, b.location_id, region))

    start = world.get_region(gd.PROVINCE_NAMES[plan.start_region])
    goal = Anno117Location(world.player, gd.GOAL_LOCATION_NAME, None, start)
    goal.place_locked_item(Anno117Item(gd.VICTORY_ITEM_NAME, ItemClassification.progression, None, world.player))
    start.locations.append(goal)


def create_regions(world: Anno117World) -> None:
    menu = Region(world.origin_region_name, world.player, world.multiworld)
    world.multiworld.regions.append(menu)
    for region_code in world.plan.regions:
        province = Region(gd.PROVINCE_NAMES[region_code], world.player, world.multiworld)
        world.multiworld.regions.append(province)
        menu.connect(province, f"Sail to {province.name}")
