# Changelog

World versions are in `apworld/anno117/archipelago.json`, mod versions in `mod/AP-Anno117/modinfo.json`.
Generate a seed with one world version for everyone. Newer apworlds with the same bridge protocol can still
play older seeds, so client and mod fixes apply to a running game.

## World 0.3.3 / mod 0.1.4

- Tiered Placement now works in three phases across both provinces: **early** (Liberti, Plebeians, Waders, Smiths,
  Mercators, plus tiles, wattle & daub and coal), **middle** (Equites, Aldermen, Nobles, plus concrete, granite
  and marble) and **late** (Patricians, plus tessera). Your items only sit in checks of their phase or earlier;
  second-province checks and items count as middle at the earliest. Needs Building Checks on. Everything follows
  Starting Province: start in Albion and Latium becomes the second province.
- **Early Building Materials** (default on): your starting province's tile/coal chain (Latium) or wattle & daub
  (Albion) is placed in the first checks of the whole multiworld, in whichever game it lands.

- Residence upgrades the seed does not shuffle are unlocked by the mod once the tier below has residents. The game's
  own unlock can depend on production buildings the randomizer is holding back, which left tiers stuck.
- Items are typed in while you play: whenever Anno 117 is in front and you haven't clicked or pressed a key for
  1.5 seconds (mouse movement is fine). Typing stops the moment you click and resumes when you pause. No more
  waiting for a long idle or typing `/deliver`.
- The client updates the game mod by itself when the apworld ships a newer version.

## World 0.3.2 / mod 0.1.3

- `/unlock_residence <tier>` in the client unlocks a residence upgrade the game is holding back, for tiers the
  seed does not shuffle. It is typed in right away when the game is in front, and applied on every load. The mod
  refuses anything the seed shuffles.

## World 0.3.1 / mod 0.1.2: first public release

### Logic
- The second province opens with the first province's third tier (Equites, or Aldermen/Nobles), as in the game.
- **Tiered Placement** (default on): your progression items only go into checks of their own tier or lower; the
  second province counts two tiers higher.
- Goods are tracked per province: logic never counts on shipping goods between Latium and Albion.
- Fuel: 28 coal-burning buildings (Tiler, Potter, Bakery, smelters, ...) need coal. Logic only trusts Charcoal
  Burners; Prophecies of Ash Coal Mines are useful items without a build check, because their deposits may be
  missing.
- Unlock tiers: each building waits for the earliest tier of its own province that uses what it makes (an Oyster Bed
  only counts at Patricians).
- **Shuffle Residences** (default off): residents upgrade the normal way unless turned on. **Early Second Tier**
  places your first upgrade in your own first checks when it is on.

### Client
- Items are typed in through keybinds automatically when Anno 117 is in front and you are idle for 3 seconds
  (`item_typing: idle`; `request` and `auto` also available). `/deliver` forces it.
- The client keeps retrying the keybind channel instead of falling back to restarts.
- Slower, configurable key presses (`key_press_ms`, default 50), and the acknowledgement timer starts after typing.
- Clearer messages: how many key presses the game received, what is being typed.

### Mod
- Reports how many bits it received when a typed message fails.
- Credits and licence in `modinfo.json` and `LICENSE`.
