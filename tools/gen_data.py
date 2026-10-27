"""Builds the compact game data file used by the Anno 117 apworld and client.

Source: js/params.js from https://github.com/anno-mods/anno-117-calculator (MIT License,
Copyright (c) 2019-2024 Nico Hoellerich). That file is generated from the game's own assets,
so it carries the real asset GUIDs that the mod needs for Unlock/Relock calls.

Usage:
    python tools/gen_data.py tools/params.js apworld/anno117/data/game_data.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REGION_NAMES = {"Roman": "Latium", "Celtic": "Albion"}


def load_params(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    return json.loads(src[src.index("{"): src.rindex("}") + 1])


def english(entry: dict) -> str:
    return entry.get("locaText", {}).get("english") or entry["name"]


def build(params: dict) -> dict:
    products = {p["guid"]: p for p in params["products"]}
    needs = {n["guid"]: n for n in params["needs"]}
    workforce_ids = {w["guid"] for w in params["workforce"]}
    levels = {lvl["guid"]: lvl for lvl in params["populationLevels"]}

    # ---- population tiers (one per residence building) ----
    residence_by_level = {r["populationLevel"]: r for r in params["residenceBuildings"]}
    parent_of: dict[int, int] = {}
    for res in params["residenceBuildings"]:
        for upgrade_guid in res.get("possibleUpgrades", []):
            target = next(r for r in params["residenceBuildings"] if r["guid"] == upgrade_guid)
            parent_of[target["populationLevel"]] = res["populationLevel"]

    def depth(level_guid: int) -> int:
        d = 1
        while level_guid in parent_of:
            level_guid = parent_of[level_guid]
            d += 1
        return d

    tiers = []
    for level_guid, res in residence_by_level.items():
        lvl = levels[level_guid]
        region = res["associatedRegions"][0]
        tier_needs = []
        for entry in res["needsList"]:
            need = needs[entry["need"]]
            tier_needs.append({
                "name": english(need),
                "product": need.get("needProduct"),
                "category": need["needCategory"],
                "building": bool(need.get("isBuilding")),
                "attrs": sorted(k for k, v in need["needAttributes"].items() if v),
                "requires_item": entry.get("requiresItem"),
                "dlc": need.get("dlcUnlocks", []),
            })
        tiers.append({
            "guid": level_guid,
            "name": english(lvl),
            "region": region,
            "province": REGION_NAMES[region],
            "workforce": lvl.get("connectedWorkforce"),
            "residence": res["guid"],
            "residence_name": english(res),
            "parent": parent_of.get(level_guid),
            "index": depth(level_guid),
            "needs": tier_needs,
        })
    tiers.sort(key=lambda t: (t["region"] != "Roman", t["index"], t["guid"]))

    # ---- production buildings ----
    fuel = params["constants"]["fuelProduct"]
    factories = []
    for f in params["factories"]:
        regions = f["associatedRegions"]
        assert len(regions) == 1, f
        region = regions[0]
        workforce = [m["product"] for m in f.get("maintenances", []) if m["product"] in workforce_ids]
        assert len(workforce) == 1, f
        name_tokens = f["name"].split()
        category = name_tokens[1] if len(name_tokens) > 1 and name_tokens[0] == "Production" else "Other"
        factories.append({
            "guid": f["guid"],
            "name": english(f),
            "region": region,
            "province": REGION_NAMES[region],
            "category": category,
            "workforce": workforce[0],
            # buildings that burn fuel need coal on top of their listed inputs
            "inputs": [i["product"] for i in f["inputs"]] + ([fuel] if f.get("needsFuelInput") else []),
            "outputs": [o["product"] for o in f["outputs"]],
            "dlc": f.get("dlcUnlocks", []),
            "fertility": f.get("neededFertility") or 0,
        })
    factories.sort(key=lambda x: (x["region"] != "Roman", x["guid"]))

    used_products = set()
    for f in factories:
        used_products.update(f["inputs"])
        used_products.update(f["outputs"])
    for t in tiers:
        used_products.update(n["product"] for n in t["needs"] if n["product"])

    return {
        "source": "anno-mods/anno-117-calculator js/params.js (MIT, (c) 2019-2024 Nico Hoellerich)",
        "regions": REGION_NAMES,
        "dlcs": {str(d["guid"]): english(d) for d in params["dlcs"]},
        "denarii_guid": 1010017,
        "products": {
            str(g): {"name": english(products[g]),
                     "construction": bool(products[g].get("isConstructionMaterial"))}
            for g in sorted(used_products) if g in products
        },
        "tiers": tiers,
        "factories": factories,
    }


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    data = build(load_params(src))
    dst.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {dst}: {len(data['tiers'])} tiers, {len(data['factories'])} buildings, "
          f"{len(data['products'])} products")


if __name__ == "__main__":
    main()
