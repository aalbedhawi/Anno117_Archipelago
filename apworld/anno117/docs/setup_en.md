# Anno 117: Pax Romana Setup Guide

## Required software

- Anno 117: Pax Romana on PC. Mods are built into the game, so you don't need a separate mod loader.
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.8 or newer.
- `anno117.apworld`. It contains the randomizer, the Anno 117 Client, and the game mod.

## Installing

1. **Install the apworld.** Double-click `anno117.apworld`, or use *Install APWorld* in the Archipelago Launcher.
   Restart the Launcher afterwards.
2. **Install the game mod.** Open *Anno 117 Client* from the Launcher. It finds your Anno 117 user folder
   (usually `Documents/Anno 117`) and installs the `AP-Anno117` mod into its `mods` folder by itself.
   - If it can't find the folder, type `/anno_folder <path>`. This is the folder that contains `mods` and `log`.
   - If you'd rather install by hand, unzip `AP-Anno117.zip` into that `mods` folder.
3. **Check the mod is active.** New mods are on by default. If you changed that, make sure `ap-anno117-bridge` is
   not commented out (`#`) in `mods/active-profile.txt`.

## Creating your options file

Generate a template with *Generate Template Options* in the Launcher, or start from the example below. Set `name`
to your slot name. Population numbers are residents, not workforce.

```yaml
name: YourName
game: Anno 117
Anno 117:
  provinces: latium        # latium, albion or both
  starting_province: latium
  goal: auto               # auto, patricians, aldermen, nobles, all_top_tiers
  goal_population: 500     # residents of each goal tier at the same time
  milestones_per_tier: 6
  milestone_cap: 1000      # biggest milestone of the first tiers; higher tiers scale down
  building_checks: true
  military_buildings: true
  tiered_placement: true   # your items stay in checks of their own tier or lower
  shuffle_residences: false
  prophecies_of_ash: false # only if you own the DLC
  denarii_per_cache: 10000
```

## Generating and hosting a game

The archipelago.gg website can't generate games that include custom worlds, so generate on your computer and let
the website host the result:

1. Put every player's options file in the `Players` folder of your Archipelago installation. Everyone using
   Anno 117 needs the apworld installed, but only the person generating needs everyone's files.
2. Run *Generate* from the Launcher, or `ArchipelagoGenerate.exe`. The result is an `AP_<number>.zip` in the
   `output` folder.
3. Go to [archipelago.gg/uploads](https://archipelago.gg/uploads), upload the zip and click *Create Room*.

## Playing

1. **Connect the client.** Open *Anno 117 Client* and connect to the room address (for example
   `archipelago.gg:38281`) with your slot name. Clicking your slot name on the room page also works. Connect
   *before* starting the game: the client writes your session into the mod folder, and the game reads it at startup.
2. **Start the game.** Launch Anno 117 and start a **new single-player sandbox game** in the province you chose
   (start in your starting province if you picked both).
3. **Check the client.** After a few seconds it should say `Game bridge connected`. Shuffled buildings stay locked
   in your build menu until you receive them.
4. **Watch how items arrive.** The client tells you which delivery method your game supports:
   - *"The game picks up updates while it runs."* Items arrive automatically. This is the normal case.
   - *"Items will be typed into the game through the bridge keybinds."* On Windows, the client types waiting items
     in by pressing Shift+F6 to Shift+F9 for you, while you play: whenever Anno 117 is the active window and you
     haven't clicked or pressed a key for a moment (moving the mouse is fine). It stops the moment you click and
     carries on when you pause, so you don't need to do anything. Each item takes several seconds to type, and the
     client says when it's typing. `/deliver` forces it right away.
   - *"The game only reads the session when it starts."* New items arrive when you save, restart Anno 117 and
     load the save again. The client counts how many are waiting.

Type `/anno` in the client to see the bridge status at any time.

## Settings

These go in the `anno117_options` section of `host.yaml` in your Archipelago folder:

- **`user_folder`**: your Anno 117 user folder. Leave it empty to detect it automatically.
- **`bridge_mode`**: how items reach the game. `auto` (the default) tries files, then keys. `files` never uses
  keys, and `keys` always types items in (Windows only).
- **`item_typing`**: only matters in keys mode. `idle` (the default) types items in when the game is the active
  window and you haven't clicked or pressed a key for 1.5 seconds; it pauses whenever you click. `request` waits for Shift+F5 in game or `/deliver` in the client.
  `auto` types them in whenever the game is the active window, even while you play.
- **`key_press_ms`**: how long each typed key is held (default 50). Raise it if the client says the game missed
  key presses.

## Troubleshooting

- **The client never says "Game bridge connected".**
  - Open `mods/mod-loader.log` in your Anno 117 user folder and check that `ap-anno117-bridge` loaded without errors.
  - Make sure you loaded a game (the bridge waits for a save to load), and give it a few seconds.
- **"The game reports seed …, but you are connected to …".** The game still has another session loaded. Restart
  Anno 117 after connecting the client.
- **A keybind clashes with something else.** Change the `KeyType` entries in
  `mods/AP-Anno117/data/base/config/export/assets.xml`. The client always presses Shift+F6 to F9, so only change
  Shift+F5, or adjust both sides.
- **Shift+F5 does nothing.** On many laptops F5 is a media key: try Fn+Shift+F5, or just type `/deliver` in the
  client. With the default `idle` delivery you don't need Shift+F5 at all.
- **A tier won't unlock although its needs are met** (with residences not shuffled). The mod unlocks each
  residence upgrade by itself once the tier below has residents, because the game's own unlock can depend on
  buildings you haven't received. If one still stays locked, type `/unlock_residence <tier>` in the client, for
  example `/unlock_residence Equites`. Only works for residences your seed does not shuffle.
- **The mod was updated.** The client updates it by itself when your apworld ships a newer one; restart Anno 117
  to load it. `/install_mod` does the same by hand.
