# AP-Anno117: Archipelago Randomizer Bridge

This mod connects Anno 117: Pax Romana to an [Archipelago](https://archipelago.gg) multiworld.
It does nothing on its own: run the **Anno 117 Client** (from the `anno117.apworld`) next to the game.

What it does while you play:

- Keeps every shuffled production building (and residence upgrade, if those are shuffled) locked until you receive it.
- Unlocks buildings and adds denarii when the client hands it received items.
- Reports population milestones and first constructions to the client, which sends them to the server.
- Tells the client when you reach your goal.

Files:

- `ap_anno117/ap_bridge.lua`: the bridge script.
- `ap_anno117/ap_state.lua`: written by the client; leave it alone.
- `data/base/config/export/assets.xml`: keybinds. Shift+F5 asks the client for waiting items when items are
  typed in through keys (optional: by default the client types them in when you pause). Shift+F6 to Shift+F9 are
  pressed by the client itself.

Start a **new single-player sandbox game** with this mod active. Multiplayer and the campaign are not supported.

By aalbedhawi. MIT licence (see `LICENSE`). Unofficial fan project; Anno 117: Pax Romana is © Ubisoft.
