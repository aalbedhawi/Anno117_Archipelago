# Contributing

Thanks for helping. Playtest reports are worth as much as code right now.

## Reporting

Use the issue templates:

- **Bug report**: the client, the mod or generation misbehaves. Attach the client log (in Archipelago's `logs`
  folder, `Anno117Client_*.txt`) and the lines starting with `AP117|` from your Anno 117 log
  (`Documents/Anno 117/log`).
- **Logic issue**: an item you need is behind a check you can't do, or logic expects something the game doesn't
  allow (a building the game won't offer yet, a good that needs something else). Attach the spoiler log
  (generate with `--spoiler 2`) and name the item and the check. These get fixed fastest.
- **Feedback**: balance, options, pacing.

Please don't post anything from the game's files beyond what's needed to describe a problem.

## Changing things

1. Set up an Archipelago source checkout (0.6.8 or newer) with its requirements, as in the README.
2. Edit the mod in `mod/`, the world in `apworld/anno117/`. `apworld/anno117/mod/` is a build copy.
3. Run the tests from the README. A logic change should come with a test in `apworld/anno117/test/`; there are
   examples for unlock tiers, coal, tiered placement and province access.
4. If you change what the mod or the client send each other, bump `AP.VERSION` in `ap_bridge.lua` and `Version`
   in `modinfo.json` together, and keep `test_bridge_contract.py` passing.
5. If you change options or logic, bump `world_version` in `apworld/anno117/archipelago.json` and
   `WORLD_VERSION` in `gamedata.py`, and add a line to `CHANGELOG.md`.

Keep the logic conservative: when the game's rules are unclear, require more, not less. A seed that asks a bit
much is a nuisance; a seed that expects the impossible locks a whole multiworld.

Changes go in through pull requests: fork the repository, push to a branch in your fork and open a pull
request. The tests run automatically, and @aalbedhawi reviews and merges.

By contributing you agree that your contribution is released under the project's MIT licence.
