# Anno 117: Pax Romana for Archipelago

An unofficial [Archipelago](https://archipelago.gg) multiworld randomizer for **Anno 117: Pax Romana**.

Your production buildings are shuffled into a multiworld with other games. A Bakery or a Vineyard stays locked until
someone, possibly in a completely different game, finds it for you. Growing your cities and building things for the
first time sends items to the other players.

> **Status: alpha.** Generation, logic, the client and the bridge are tested outside the game, and the integration
> is being playtested in Anno 117. Expect rough edges, and please [report what you find](#feedback).

**Contents:** [What you get](#what-you-get) · [Install](#install) · [Your first game](#your-first-game) ·
[Options](#options) · [Client commands](#client-commands) · [Tips](#tips) · [Troubleshooting](#troubleshooting) ·
[How it works](#how-it-works) · [Development](#development) · [Feedback](#feedback) · [Credits](#credits-and-licence)

## What you get

- **Items:** every production building (optionally military chains, residence upgrades and Prophecies of Ash
  buildings), plus Denarii Caches as filler.
- **Checks:** population milestones per tier ("Population: 150 Plebeians") and the first construction of each
  production building.
- **Goal:** a number of residents of your top tier, or of every top tier with both provinces.
- **Provinces:** Latium, Albion or both. With both, you pick where you start, and the other province opens at your
  third tier, like in the game.
- **Logic built from the game's data:** production chains, coal fuel, every tier's needs, the tier at which the game
  normally offers each building, and goods made in each province. Nothing in your world is expected before the game
  lets you do it.
- **Three phases** (early, middle, late) keep your items in checks of their own phase or earlier, so a Plebeian
  building is never stuck behind your Nobles.
- **No manual delivery.** Items are typed into the game while you play, residences unlock themselves, and the game
  mod keeps itself up to date.

The [game page](apworld/anno117/docs/en_Anno%20117.md) has the full rules and known limits.

## Install

You need:

- **Anno 117: Pax Romana** on PC (mods are built into the game).
- **[Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.8 or newer.**
- **`anno117.apworld`** from the [releases](../../releases). It contains the randomizer, the Anno 117 Client and
  the game mod.

Then:

1. **Install the apworld.** Double-click `anno117.apworld`, or use *Install APWorld* in the Archipelago Launcher,
   and restart the Launcher.
2. **Open *Anno 117 Client*** from the Launcher once. It finds your Anno 117 user folder (usually
   `Documents/Anno 117`) and installs the `AP-Anno117` mod into its `mods` folder.
   - If it can't find the folder, type `/anno_folder <path>` (the folder that contains `mods` and `log`).
   - Prefer doing it by hand? Unzip `AP-Anno117.zip` into that `mods` folder.

Everyone generating or playing an Anno 117 slot needs the apworld installed.

## Your first game

1. **Make your options file.** Start from one of the [examples](#example-options), or use *Generate Template
   Options* in the Launcher. Set `name` to your slot name (16 characters max).
2. **Generate.** The archipelago.gg website can't generate games with custom worlds, so one person generates locally:
   put everyone's YAML in Archipelago's `Players` folder and run *Generate* from the Launcher. The result is an
   `AP_<number>.zip` in the `output` folder.
3. **Host.** Upload that zip at [archipelago.gg/uploads](https://archipelago.gg/uploads) and create a room.
4. **Connect the client first.** Open *Anno 117 Client* and connect to the room (for example
   `archipelago.gg:38281`) with your slot name. The client writes your session into the mod folder, which the game
   reads when it starts.
5. **Start Anno 117** and begin a **new single-player sandbox (endless) game** in your starting province. Use a new
   game for every seed.
6. **Check the client.** After loading, it says `Game bridge connected`, then how items reach your game:
   - *"The game picks up updates while it runs"*: items arrive by themselves.
   - *"Items will be typed into the game through the bridge keybinds"*: the client presses Shift+F6 to Shift+F9
     for you while Anno 117 is the active window. It waits until you haven't clicked or pressed a key for
     1.5 seconds (moving the mouse is fine), stops the moment you click, and carries on when you pause.
   - *"The game did not answer the keybind test yet"*: it keeps retrying in the background. Saving, restarting
     Anno 117 and loading your save also delivers everything.
7. **Play.** Shuffled buildings are locked in your build menu until you receive them. Grow your tiers and build
   new things to send checks. `/anno` in the client shows the bridge status at any time.

### Example options

| File | What it is |
| --- | --- |
| [`Anno117_Grand_Tour.yaml`](examples/Anno117_Grand_Tour.yaml) | Both provinces, every top tier, 230 checks: a long multiworld, about 25 hours of Anno. |
| [`Anno117_Quick_Latium.yaml`](examples/Anno117_Quick_Latium.yaml) | Latium only, small Patrician goal: a few hours. |

## Options

All population numbers are **residents, not workforce**.

| Option | Default | What it does |
| --- | --- | --- |
| `provinces` | `latium` | `latium`, `albion` or `both`. |
| `starting_province` | `latium` | With `both`: where you start. The other province opens at your third tier. |
| `goal` | `auto` | `auto` (your start province's top tier), `patricians`, `aldermen`, `nobles` or `all_top_tiers`. |
| `goal_population` | `500` | Residents of each goal tier you need at the same time. |
| `milestones_per_tier` | `6` | Population checks per tier (0–23). |
| `milestone_cap` | `1000` | The biggest milestone of the first tiers; higher tiers scale down. |
| `building_checks` | on | The first construction of each production building is a check. |
| `military_buildings` | on | Shuffle weapons, armour, rope and sails too. |
| `prophecies_of_ash` | off | Include the DLC's buildings. Only if you own it. |
| `tiered_placement` | on | Keep your items in checks of their own phase or earlier (needs building checks). |
| `early_materials` | on | Your starting province's tile/coal (Latium) or wattle & daub (Albion) buildings go in the first checks of the whole multiworld. |
| `shuffle_residences` | off | Make residence upgrades items too. Off: residents upgrade as usual. |
| `early_upgrade` | `early` | With shuffled residences: put your second-tier upgrade in your first checks (`off`, `early`, `start`). |
| `denarii_per_cache` | `10000` | Denarii per filler item. |

**The three phases** used by `tiered_placement`:

| Phase | Tiers | Building materials |
| --- | --- | --- |
| Early | Liberti, Plebeians, Waders, Smiths, Mercators | tiles, wattle & daub, coal |
| Middle | Equites, Aldermen, Nobles | concrete, granite, marble |
| Late | Patricians | tessera |

Your second province's checks and items count as middle at the earliest, whichever province you start in.

### Client settings (`host.yaml`)

In the `anno117_options` section of `host.yaml` in your Archipelago folder:

| Setting | Default | What it does |
| --- | --- | --- |
| `user_folder` | empty | Your Anno 117 user folder; empty means detect it. |
| `bridge_mode` | `auto` | `auto` tries files, then keys; `files` never types; `keys` always types (Windows). |
| `item_typing` | `idle` | `idle` types when you pause clicking; `request` waits for Shift+F5 or `/deliver`; `auto` types whenever the game is in front. |
| `key_press_ms` | `50` | How long each typed key is held. Raise it (80–100) if the client says the game missed key presses. |

## Client commands

| Command | What it does |
| --- | --- |
| `/anno` | Bridge status: connection, delivery method, items confirmed by the game. |
| `/deliver` | Type waiting items in right now (switch to Anno 117 within 3 seconds). Normally not needed. |
| `/unlock_residence <tier>` | Unlock a residence upgrade the game is holding back, for example `/unlock_residence Equites`. Only for residences your seed doesn't shuffle; normally the mod does this by itself. |
| `/anno_folder <path>` | Set your Anno 117 user folder if it wasn't found. |
| `/install_mod` | Reinstall the game mod. The client already updates it by itself. |
| `/resync` | Rewrite the session file and redo the bridge handshake. |

Archipelago's usual commands work too: `!hint <item>`, `/received`, `/missing`, `!release`, `!collect`.

## Tips

- **Pick a big map with lots of islands.** Logic doesn't see island fertility. Olives, flax, oysters and the like need
  the right island, so more islands means fewer surprises.
- **Trade.** Traders sell goods and building materials. Logic never counts on them, but they bridge a gap while you
  wait for an item.
- **Look at the province you built in.** The game only reports buildings in the province your camera is in, so a
  build check in your other province fires once you look there.
- **Milestones count your record.** They use the highest number of residents a tier ever had, so a fire or riot
  can't undo a check. The goal counts the residents you have right now.
- **Base-tier milestones and upgrades pull in different directions.** Big Liberti or Waders milestones need many
  houses kept at that tier: reach them before you upgrade most of your houses.
- **Don't fight the typing.** When the client says it's typing an item, a short pause lets it finish; clicking just
  makes it start that item again.
- **Hints are your friend.** `!hint <building>` tells you who has the item you need, so you can ask them to go get
  it. A short list of what you're waiting for helps slower-paced friends prioritise.
- **New seed, new game.** Start a fresh sandbox game for every seed. An old save keeps the previous seed's locks.
- **Long games:** host with `release_mode: goal`, so anyone who finishes hands out their remaining items. Anno is
  slower than most games, and your friends will thank you.

## Troubleshooting

- **The client never says "Game bridge connected".** Open `mods/mod-loader.log` in your Anno 117 user folder and
  check that `ap-anno117-bridge` loaded. Make sure you loaded a game, and give it a few seconds.
- **"The game reports seed …, but you are connected to …".** The game still has another session loaded: restart
  Anno 117 after connecting the client.
- **Items waiting but nothing happens.** Keep Anno 117 as the active window and stop clicking for a moment, or type
  `/deliver`. If the client says the game *missed key presses*, raise `key_press_ms` in `host.yaml`.
- **A tier won't unlock although its needs are met.** The mod unlocks residence upgrades once the tier below has
  residents. If one stays locked, use `/unlock_residence <tier>`.
- **A building says it needs research.** Do the research, but the building also has to be found in the multiworld
  first (`!hint` it). Research isn't part of the logic yet.
- **"Item appears to not exist in this multiworld" for a residence.** Residences aren't shuffled in your seed
  (`shuffle_residences: false`), so there is nothing to hint; they upgrade the normal way.
- **The mod was updated.** The client installs the new version itself; restart Anno 117 to load it.
- **Something is impossible.** If an item you need is behind a check you can't do, open a
  [logic issue](../../issues/new?template=logic_issue.yml). Meanwhile, the host can `/send` you the item.

## How it works

```
Archipelago server <-websocket-> Anno 117 Client <-files / keys-> AP-Anno117 mod (Lua, inside Anno 117)
```

| Part | Where it runs | What it does |
| --- | --- | --- |
| apworld (`apworld/anno117`) | Archipelago | Items, checks, logic and options for generating seeds. |
| Anno 117 Client (`apworld/anno117/client`) | Archipelago Launcher | Talks to the server and to the game mod. |
| AP-Anno117 mod (`mod/AP-Anno117`) | Anno 117 `mods` folder | Locks and unlocks buildings, reports checks, detects the goal. |

- **Game → client.** The mod prints lines like `AP117|<seed>|CHECK|118149608` to the game log (and to
  `ap_outbox.txt` when the game's Lua can write files). The client tails both.
- **Client → game.** The client writes the session to `mods/AP-Anno117/ap_anno117/ap_state.lua`. The mod reads it
  at game start, while the game runs if the game build allows it, and otherwise the client types data in through
  the mod's keybinds (Windows): Shift+F6/F7 for bits, Shift+F8 to end, Shift+F9 to reset, with a checksum and a
  confirmation for every item.
- **ID scheme**, decoded arithmetically by the mod, so it needs no data table:
  - `117000000 + GUID`: unlock that building or residence asset.
  - `117900001`: Denarii Cache.
  - `118000000 + tier GUID * 100 + threshold index`: population milestone.
  - `119000000 + building GUID`: first construction.

## Development

You need an Archipelago source checkout
([running from source](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/running%20from%20source.md))
with its requirements installed, on 0.6.8 or newer.

```
python tools/build.py path/to/Archipelago   # dist/: anno117.apworld, AP-Anno117.zip, Anno 117.yaml, release zip
python tools/set_author.py "your-name"      # put your name on the licence, credits, manifest and mod
```

`build.py` copies `mod/` into the apworld (`apworld/anno117/mod/`, not tracked by git) and links the world into the
checkout as `worlds/anno117`. Edit the mod in `mod/`, never in the copy.

**Game data.** `apworld/anno117/data/game_data.json` is generated from `js/params.js` of the community
[anno-117-calculator](https://github.com/anno-mods/anno-117-calculator) (MIT), which is exported from the game's
assets. After a game update: `python tools/gen_data.py tools/params.js apworld/anno117/data/game_data.json`.
Everything else is derived in `gamedata.py` (starter kit, needs per tier, unlock tiers, coal fuel, phases) and
`logic.py` (an incremental bitmask fixed point cached on the collection state, with three levels per tier:
unlocked, established, sustained).

**Tests:**

```
python tools/build.py --bundle-only
cd path/to/Archipelago
AP_TEST_WORLDS=anno117 python -m pytest test/general worlds/anno117/test    # AP's world tests + ours
```

The bridge tests need the [Luau CLI](https://github.com/luau-lang/luau/releases) and `pip install lupa`; the
end-to-end tests also need the built `anno117.apworld` in the checkout's `custom_worlds/`:

```
python tests/lua/run_bridge_tests.py path/to/luau                      # bridge unit tests in real Luau
python tests/e2e/run_e2e.py path/to/Archipelago scratch/ dofile        # server + client + simulated game
python tests/e2e/run_e2e.py path/to/Archipelago scratch/ io
python tests/e2e/run_e2e.py path/to/Archipelago scratch/ stale         # game that only reads state at startup
python tests/e2e/run_e2e_keys.py path/to/Archipelago scratch/          # keybind channel
python tests/e2e/run_e2e_keys.py path/to/Archipelago scratch/ flaky    # first keybind test lost, recovers
```

The end-to-end tests run the real `ap_bridge.lua` inside Lua 5.1 with the Anno APIs mocked
(`tests/e2e/fake_game.py`). What only the real game can confirm: the delivery channel a game build allows and the
keybind syntax. Every game call is wrapped in `pcall`. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a
pull request.

## Feedback

Playtest reports are the most useful thing you can send:

- **[Bug report](../../issues/new?template=bug_report.yml)**: something broke (client, mod, generation).
- **[Logic issue](../../issues/new?template=logic_issue.yml)**: an item you need is behind a check you can't do, or
  the logic expects something the game doesn't allow. Include the item, the check and your spoiler log.
- **[Feedback](../../issues/new?template=feedback.yml)**: balance, options, pacing, how a run felt.

## Credits and licence

Made by aalbedhawi. MIT licence, see [LICENSE](LICENSE). Game data from the anno-117-calculator by Nico Höllerich
(MIT); full credits in [CREDITS.md](CREDITS.md). Built with the help of Claude (Anthropic).

Anno 117: Pax Romana is © Ubisoft Entertainment. This is an unofficial fan project, not affiliated with, endorsed by
or sponsored by Ubisoft. You need your own copy of the game.
