# Credits

## Author

- **aalbedhawi**: design, playtesting and maintenance.

## Built with

- **[Archipelago](https://archipelago.gg)** ([source](https://github.com/ArchipelagoMW/Archipelago)), the multiworld
  randomizer framework this world plugs into. MIT licence. The apworld uses Archipelago's world, client and
  launcher APIs and is not part of Archipelago itself.
- **[anno-117-calculator](https://github.com/anno-mods/anno-117-calculator)** by Nico Höllerich (NiHoel) and the
  anno-mods community. Its `js/params.js`, exported from the game's assets, is the source of every building, good,
  tier and need in the logic (`tools/params.js` → `apworld/anno117/data/game_data.json`). MIT licence, Copyright (c)
  2019-2024 Nico Höllerich; the full text ships next to the data in `data/LICENSE-anno-117-calculator.txt`.
- **[anno-mods/modding-guide](https://github.com/anno-mods/modding-guide)**: documentation of the Anno 117 mod
  format, script hooks and Lua bindings that the bridge mod relies on.
- **[Luau](https://luau.org)** (MIT) and **[lupa](https://github.com/scoder/lupa)** (MIT), used only by the test
  suite to run the bridge outside the game.

## AI assistance

Most of the code and documentation was written with the help of Claude (Anthropic), directed, reviewed and
playtested by the author.

## Disclaimer

Anno 117: Pax Romana is © Ubisoft Entertainment. All game names, content and data belong to their owners. This is
an unofficial fan project, not affiliated with, endorsed by or sponsored by Ubisoft. You need your own copy of the
game to play.
