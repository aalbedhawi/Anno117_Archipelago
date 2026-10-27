from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .items import ITEM_DESCRIPTIONS
from .locations import LOCATION_DESCRIPTIONS
from .options import option_groups, option_presets


class Anno117WebWorld(WebWorld):
    game = "Anno 117"
    theme = "ocean"
    rich_text_options_doc = True

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Anno 117: Pax Romana for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["aalbedhawi"],
    )
    tutorials = [setup_en]

    option_groups = option_groups
    options_presets = option_presets
    item_descriptions = ITEM_DESCRIPTIONS
    location_descriptions = LOCATION_DESCRIPTIONS
