# Anno 117: Pax Romana

## What does randomization do to this game?

Production buildings no longer unlock through normal progression (residence upgrades too, if you turn on
Shuffle Residences). Each one is an item
that you (or another player) have to find in the multiworld. Until it arrives, the AP-Anno117 mod keeps it locked
in your build menu, even if the game would normally unlock it.

You still start with a small kit for your first tier, so you can found a city right away:

- **Latium**: Fishing Hut, Oat Farm, Porridge Stand, Woodcutter, Sawmill, Hemp Farm, Spinner, Sheep Farm and Pileus Felter.
- **Albion**: Cockle Picker, Eel Grabber, Woodcutter, Sawmill, Mud Drier, Tiler, Charcoal Burner, Reed Gatherer, Shoe Weaver, Hemp Farm and Spinner.

Public buildings, warehouses, roads, ships, and anything else that is not a production building keep their normal unlocks.

## What items can I find?

- **Residence upgrades** (only with Shuffle Residences on) let your residences upgrade to the next tier: Plebeian, Eques and Patrician Residence in
  Latium, and Smith, Alderman, Mercator and Noble Residence in Albion.
- **Production buildings**, for example *Bakery (Latium)* or *Brewery (Albion)*. Optionally this includes the
  military and shipyard supply chains, and the Prophecies of Ash DLC buildings.
- **Denarii Cache**: filler that adds denarii to your treasury.

## What counts as a check?

- **Population milestones**: reaching a number of residents of a tier, for example *Population: 150 Plebeians*.
  Counts are across all your islands. You set how many milestones each tier has, and how large they get.
- **First constructions**: building your first copy of each production building, including the ones you start with
  (this can be turned off). The game only reports buildings in the province your camera is in, so a check fires once
  you look at the province where you built it.

## What is the goal?

Have a set number of residents of your goal tier at the same time. By default that is 500 Patricians in Latium, or
500 Aldermen in Albion. With both provinces, *All Top Tiers* asks for Patricians, Aldermen and Nobles together.

## How does the logic work?

Residences in Anno 117 upgrade once every needs category (food, fashion, household, ...) is at least minimally
supplied. The randomizer uses that, on the safe side, with three levels per tier:

| Level | What you need | What it allows |
| --- | --- | --- |
| **Unlocked** | the previous tier sustained (with Shuffle Residences: its residence upgrade and the previous tier established) | milestones of 25 residents or fewer |
| **Established** | one of the tier's *new* goods in every needs category, plus its building materials | milestones up to half of the tier's cap, and the next tier's residents |
| **Fully supplied** | every good that adds residents to this tier | the biggest milestones, and the goal |

Some examples of established tiers:

- **Plebeians**: bread or garum, sandals or soap, and amphorae or olive oil, plus tiles.
- **Equites**: wine, togas, and fine glass or writing tablets, plus concrete and marble.

Other rules:

- **First constructions** need the building, workers of its tier, and access to its province. Building materials you
  cannot make yet can be bought from traders.
- **The second province** (with both provinces) opens once your third tier in the first province (Equites, or Aldermen/Nobles) is established, like in the game.
- **Coal.** Kilns, bakeries, smelters and other fuel-burning buildings need coal. Logic only counts Charcoal
  Burners for it: Prophecies of Ash Coal Mines need deposits you may not have, so they are useful items but never
  required, and building one is not a check.
- **Optional needs** don't count: ones that need a special item, come from the other province, or are DLC-only. So
  do public services, which come from public buildings with their normal unlocks.

## Which provinces and tiers are included?

- **Latium**: Liberti, then Plebeians, Equites and Patricians.
- **Albion**: Waders, then either Smiths and Aldermen, or Mercators and Nobles.

## Known limitations

- **New single-player sandbox games only.** Multiplayer, co-op and the campaign are not supported.
- **"Building unlocked" notifications.** When the game itself unlocks a shuffled building, you may see its
  notification right before the mod locks it again.
- **Reloading older saves.** Denarii Caches applied in a later save are not handed out again.
- **Delivery depends on what your game build allows.** The client finds out by itself when you connect:
  - Usually items arrive while you play.
  - If the game only reads the session when it starts, you get new items by saving and restarting Anno 117.
  - On Windows, the client can type items in through the mod's keybinds instead (automatically when you pause for a moment, or on `/deliver`).

## When buildings come into logic

Logic never expects a building before the game would normally offer it. Each building waits for the earliest
tier that uses what it makes, so an Oyster Bed only counts once you have Patricians, even though Liberti work it.

## Where your items can be

With **Tiered Placement** (on by default) the game is split into three phases, and your own items only sit in
checks of their phase or an earlier one:

| Phase | Tiers | Building materials |
| --- | --- | --- |
| **Early** | Liberti, Plebeians, Waders, Smiths, Mercators | tiles, wattle & daub, coal |
| **Middle** | Equites, Aldermen, Nobles | concrete, granite, marble |
| **Late** | Patricians | tessera (mosaics) |

So a Wheat Farm (early) is found in early checks, never behind your Nobles. Your second province opens at your
third tier, so its checks and its items count as middle at the earliest. If there aren't enough early checks for
every early item, the extras move to the middle phase. Tiered Placement needs Building Checks: with milestones
alone there is too little room to keep items in their phase safely, so it is skipped.
Phases follow your Starting Province: start in Albion, and Latium is the second province.

With **Early Building Materials** (on by default), your starting province's tile and coal buildings (Latium) or
wattle & daub (Albion) are placed in the first checks of the whole multiworld, so a slow start in someone else's
game can't hold up your second tier.

Logic also never counts on shipping goods between provinces: each province has to make what its residents need.
