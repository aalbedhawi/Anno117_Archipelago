from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, PerGameCommonOptions, Range, StartInventoryPool, Toggle


class Provinces(Choice):
    """
    Which provinces are part of the randomizer.

    - **Latium**: the Roman province (Liberti, Plebeians, Equites, Patricians).
    - **Albion**: the Celtic province (Waders, then Smiths and Aldermen or Mercators and Nobles).
    - **Both**: both provinces. You start in the one picked by Starting Province, and logic expects the
      other one only once your third tier there (Equites, or Aldermen/Nobles) is established,
      as the game only opens the second province then.
    """

    display_name = "Provinces"
    option_latium = 0
    option_albion = 1
    option_both = 2
    default = option_latium


class StartingProvince(Choice):
    """
    The province you start in when Provinces is set to Both. Ignored otherwise.
    """

    display_name = "Starting Province"
    option_latium = 0
    option_albion = 1
    default = option_latium


class Goal(Choice):
    """
    Which residents you need to win. If the chosen tier is not in your provinces, Auto is used instead.

    - **Auto**: the top tier of your starting province (Patricians in Latium, Aldermen in Albion).
    - **Patricians**, **Aldermen**, **Nobles**: that tier specifically (its province must be included).
    - **All Top Tiers**: every top tier of every included province.
    """

    display_name = "Goal"
    option_auto = 0
    option_patricians = 1
    option_aldermen = 2
    option_nobles = 3
    option_all_top_tiers = 4
    default = option_auto


class GoalPopulation(Range):
    """
    How many residents of each goal tier you need at the same time to win.
    """

    display_name = "Goal Population"
    range_start = 10
    range_end = 10000
    default = 500


class MilestonesPerTier(Range):
    """
    How many population milestones each tier has. Each milestone is a check
    (for example "Population: 150 Plebeians"). If there end up being fewer checks than unlocks, the earliest
    unlocks are given to you at the start instead.
    """

    display_name = "Milestones per Tier"
    range_start = 0
    range_end = 23
    default = 6


class MilestoneCap(Range):
    """
    The largest population milestone for the first two tiers of a province.
    The third tier uses 60% of this and the fourth tier 40%, since those tiers have fewer residents.
    """

    display_name = "Milestone Cap"
    range_start = 50
    range_end = 10000
    default = 1000


class BuildingChecks(DefaultOnToggle):
    """
    Constructing your first copy of each production building is a check, including the buildings you start with.
    Note: the game can only see buildings in the province your camera is in, so a check fires when you look
    at the province where you built it.
    """

    display_name = "Building Checks"


class MilitaryBuildings(DefaultOnToggle):
    """
    Shuffle the military and shipyard supply chains (weapons, armour, rope and sails) too.
    When off, those buildings keep their normal unlocks.
    """

    display_name = "Military Buildings"


class PropheciesOfAsh(Toggle):
    """
    Include buildings from the Prophecies of Ash DLC (Caelator, Latrunculi Workshop and the Coal Mines).
    Only turn this on if you own the DLC.
    """

    display_name = "Prophecies of Ash DLC"


class TieredPlacement(DefaultOnToggle):
    """
    Keep your items in the phase of the game they belong to, so nothing you need early sits behind late checks.

    - **Early**: Liberti, Plebeians, Waders, Smiths and Mercators, plus tiles, wattle & daub and coal.
    - **Middle**: Equites, Aldermen and Nobles, plus concrete, granite and marble.
    - **Late**: Patricians, plus tessera (mosaics).

    An item is only placed in checks of its own phase or an earlier one: a Wheat Farm (early) is found in
    early checks, never behind your Nobles. Your second province opens at your third tier, so its checks count as
    middle at the earliest, and so do its items. Needs Building Checks on: with milestones alone there are
    too few checks to hold items to phases safely, so it is skipped. Only applies to your own progression items in your own world. Turn it off for a
    wilder shuffle.
    """

    display_name = "Tiered Placement"


class EarlyMaterials(DefaultOnToggle):
    """
    Place the early building-material chain of your starting province among the first checks of the whole
    multiworld, in whichever game they land: in Latium the Tiler, Clay Pit and Charcoal Burner, in Albion the
    Labourer's Yard (wattle & daub). Without tiles or wattle & daub your second tier can't build, so this keeps a
    slow sphere in someone else's game from stalling your start. Follows Starting Province.
    """

    display_name = "Early Building Materials"


class ShuffleResidences(Toggle):
    """
    Shuffle the residence upgrades (Plebeian Residence, Smith Residence, ...) into the multiworld.

    Off (the default): your residents upgrade the normal way and every tier unlocks as in the base game.
    Only buildings are shuffled, and logic waits for each tier the way the game does.
    On: each tier is locked until you receive its residence upgrade.
    """

    display_name = "Shuffle Residences"


class EarlyUpgrade(Choice):
    """
    Only with Shuffle Residences on. How soon you get the upgrade to your second tier (Plebeians in Latium;
    Smiths and Mercators in Albion). Without it your first residents cannot upgrade, so a late one can leave
    you waiting on other players.

    - **Off**: shuffled like any other item.
    - **Early**: placed in one of your own first checks (early Liberti or Wader milestones, starter buildings).
    - **Start**: you have it from the start.
    """

    display_name = "Early Second Tier"
    option_off = 0
    option_early = 1
    option_start = 2
    default = option_early


class DenariiPerCache(Range):
    """
    How many denarii each Denarii Cache filler item gives.
    """

    display_name = "Denarii per Cache"
    range_start = 1000
    range_end = 250000
    default = 10000


@dataclass
class Anno117Options(PerGameCommonOptions):
    provinces: Provinces
    starting_province: StartingProvince
    goal: Goal
    goal_population: GoalPopulation
    milestones_per_tier: MilestonesPerTier
    milestone_cap: MilestoneCap
    building_checks: BuildingChecks
    military_buildings: MilitaryBuildings
    prophecies_of_ash: PropheciesOfAsh
    tiered_placement: TieredPlacement
    early_materials: EarlyMaterials
    shuffle_residences: ShuffleResidences
    early_upgrade: EarlyUpgrade
    denarii_per_cache: DenariiPerCache
    start_inventory_from_pool: StartInventoryPool


option_groups = [
    OptionGroup("World", [Provinces, StartingProvince, Goal, GoalPopulation]),
    OptionGroup("Checks", [MilestonesPerTier, MilestoneCap, BuildingChecks]),
    OptionGroup("Items", [TieredPlacement, EarlyMaterials, ShuffleResidences, EarlyUpgrade, MilitaryBuildings, PropheciesOfAsh, DenariiPerCache]),
]

option_presets = {
    "Quick Latium": {
        "provinces": Provinces.option_latium,
        "goal": Goal.option_auto,
        "goal_population": 150,
        "milestones_per_tier": 4,
        "milestone_cap": 400,
    },
    "Grand Tour": {
        "provinces": Provinces.option_both,
        "starting_province": StartingProvince.option_latium,
        "goal": Goal.option_all_top_tiers,
        "goal_population": 500,
        "milestones_per_tier": 8,
        "milestone_cap": 1500,
    },
}
