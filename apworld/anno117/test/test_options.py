"""Each class generates a world with these options and runs AP's default reachability and fill tests."""
from . import Anno117TestBase


class TestLatiumDefault(Anno117TestBase):
    options = {"provinces": "latium"}

    def test_counts(self) -> None:
        plan = self.world.plan
        self.assertEqual(len(plan.upgrade_tiers), 0)
        self.assertEqual(len(plan.goal_tiers), 1)
        self.assertEqual(plan.goal_tiers[0].name, "Patricians")
        locations = [loc for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertEqual(len(locations), len(plan.milestones) + len(plan.build_checks))


class TestAlbion(Anno117TestBase):
    options = {"provinces": "albion", "goal": "aldermen"}


class TestAlbionNobles(Anno117TestBase):
    options = {"provinces": "albion", "goal": "nobles"}


class TestBothFromLatium(Anno117TestBase):
    options = {"provinces": "both", "starting_province": "latium", "goal": "all_top_tiers"}

    def test_goal_tiers(self) -> None:
        self.assertEqual({t.name for t in self.world.plan.goal_tiers}, {"Patricians", "Aldermen", "Nobles"})


class TestBothFromAlbion(Anno117TestBase):
    options = {"provinces": "both", "starting_province": "albion", "goal": "patricians"}


class TestNoBuildingChecks(Anno117TestBase):
    """Fewer checks than unlocks: the extras become starting items instead of failing generation."""
    options = {"provinces": "latium", "building_checks": False, "milestones_per_tier": 3}

    def test_surplus_precollected(self) -> None:
        precollected = self.multiworld.precollected_items[self.player]
        self.assertGreater(len(precollected), 0)
        shuffled = [item for item in self.multiworld.itempool if item.player == self.player and item.advancement]
        placed = [loc for loc in self.multiworld.get_locations(self.player) if loc.item and loc.address is not None]
        self.assertEqual(len(shuffled) + len(precollected) + len(placed), len(self.world.plan.item_names))
        locations = [loc for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertLessEqual(len(shuffled), int(len(locations) * 0.75))


class TestManyMilestones(Anno117TestBase):
    options = {"provinces": "both", "milestones_per_tier": 23, "milestone_cap": 10000, "goal_population": 2000}


class TestProphecies(Anno117TestBase):
    options = {"provinces": "both", "prophecies_of_ash": True}

    def test_dlc_buildings_present(self) -> None:
        names = {b.base_name for b in self.world.plan.item_buildings}
        self.assertIn("Caelator", names)
        self.assertIn("Latrunculi Workshop", names)


class TestNoMilitary(Anno117TestBase):
    options = {"provinces": "latium", "military_buildings": False}

    def test_military_not_shuffled(self) -> None:
        self.assertFalse([b for b in self.world.plan.item_buildings if b.military])


class TestShuffledResidences(Anno117TestBase):
    options = {"provinces": "both", "shuffle_residences": True, "goal": "all_top_tiers"}

    def test_counts(self) -> None:
        self.assertEqual(len(self.world.plan.upgrade_tiers), 7)


class TestEarlyUpgradeDefault(Anno117TestBase):
    options = {"provinces": "both", "starting_province": "albion", "shuffle_residences": True}

    def test_both_tier_two_upgrades_early(self) -> None:
        plan = self.world.plan
        base = [m for m in plan.milestones if m.tier.name == "Waders"]
        early_spots = {b.location_name for b in plan.build_checks if b.guid in plan.starters and b.region == "Celtic"}
        early_spots |= {m.name for m in sorted(base, key=lambda m: m.value)[:2]}
        placed = {loc.item.name: loc.name for loc in self.multiworld.get_locations(self.player)
                  if loc.item and loc.item.name in ("Smith Residence", "Mercator Residence")}
        self.assertEqual(set(placed), {"Smith Residence", "Mercator Residence"})
        self.assertTrue(set(placed.values()) <= early_spots, placed)


class TestEarlyUpgradeStart(Anno117TestBase):
    options = {"provinces": "latium", "early_upgrade": "start", "shuffle_residences": True}

    def test_start_with_upgrade(self) -> None:
        names = [item.name for item in self.multiworld.precollected_items[self.player]]
        self.assertIn("Plebeian Residence", names)
        self.assertNotIn("Plebeian Residence", [i.name for i in self.multiworld.itempool if i.player == self.player])


class TestEarlyUpgradeOff(Anno117TestBase):
    options = {"provinces": "latium", "early_upgrade": "off", "shuffle_residences": True}

    def test_nothing_forced(self) -> None:
        self.assertFalse(self.multiworld.local_early_items[self.player])


class TestTieredPlacement(Anno117TestBase):
    """After a full fill, none of your items sits in a check above its own tier (second province: one higher)."""
    options = {"provinces": "both", "goal": "all_top_tiers", "shuffle_residences": True}

    def test_items_stay_in_their_tier(self) -> None:
        from Fill import distribute_items_restrictive
        from .. import gamedata as gd

        distribute_items_restrictive(self.multiworld)
        world, plan = self.world, self.world.plan
        loc_rank = world.location_phases()
        bad = []
        for loc in self.multiworld.get_locations(self.player):
            item = loc.item
            if item is None or item.player != self.player or loc.name not in loc_rank:
                continue
            if loc_rank[loc.name] > world.item_rank.get(item.name, 99):
                bad.append(f"{item.name} in {loc.name}")
        self.assertEqual(bad, [])
        # the example that started this: a Latium Wheat Farm never behind Albion's Nobles
        wheat = next(loc for loc in self.multiworld.get_locations(self.player)
                     if loc.item and loc.item.name == "Wheat Farm (Latium)")
        self.assertNotIn("Nobles", wheat.name)
        self.assertNotIn("Bird Charmer", wheat.name)

    def test_phases(self) -> None:
        from .. import gamedata as gd
        items = self.world.item_phases()
        self.assertEqual(items["Tiler (Latium)"], gd.EARLY)
        self.assertEqual(items["Charcoal Burner (Latium)"], gd.EARLY)
        self.assertEqual(items["Labourer's Yard (Albion)"], gd.MIDDLE)   # Albion opens at Equites
        self.assertEqual(items["Concrete Mixer (Latium)"], gd.MIDDLE)
        self.assertEqual(items["Granite Quarry (Albion)"], gd.MIDDLE)
        self.assertEqual(items["Marble Quarry (Latium)"], gd.MIDDLE)
        self.assertEqual(items["Tessera Works (Latium)"], gd.LATE)
        self.assertEqual(items["Eques Residence"], gd.EARLY)      # needed while still on Plebeians
        locs = self.world.location_phases()
        self.assertEqual(locs["Population: 10 Plebeians"], gd.EARLY)
        self.assertEqual(locs["Population: 10 Smiths"], gd.MIDDLE)   # Albion only opens at Equites
        self.assertEqual(locs["Population: 10 Equites"], gd.MIDDLE)
        self.assertEqual(locs["Population: 10 Patricians"], gd.LATE)


class TestTieredPlacementScarce(Anno117TestBase):
    """Few checks: overflow moves to a later phase instead of failing the fill."""
    options = {"provinces": "both", "milestones_per_tier": 2, "shuffle_residences": True, "military_buildings": False}


class TestTieredPlacementNeedsBuildChecks(Anno117TestBase):
    """Milestones only: Tiered Placement is skipped rather than risking an unfillable seed."""
    options = {"provinces": "both", "building_checks": False, "milestones_per_tier": 13, "milestone_cap": 3000,
               "goal": "nobles"}

    def test_skipped(self) -> None:
        self.assertFalse(hasattr(self.world, "item_rank") and self.world.item_rank)


class TestGoodsStayInProvince(Anno117TestBase):
    # shuffled residences: Equites (and so Albion) only need Plebeians established, which garum can do
    options = {"provinces": "both", "starting_province": "latium", "goal": "patricians", "shuffle_residences": True}
    run_default_tests = False

    def test_albion_bread_does_not_feed_latium(self) -> None:
        from .. import gamedata as gd
        logic = self.world.logic
        everything_but = [n for n in self.world.plan.item_names if not n.endswith("(Latium)") or "Bakery" not in n]
        w = logic.evaluate(lambda name: name in everything_but)
        bread = next(iter(b.outputs for b in gd.BUILDINGS.values() if b.base_name == "Bakery"))
        bread_id = next(iter(bread))
        self.assertTrue(w.products & logic.product_bit[(gd.REGION_ALBION, bread_id)])
        self.assertFalse(w.products & logic.product_bit[(gd.REGION_LATIUM, bread_id)])
        self.assertFalse(logic.sustained(w, 1496))  # Plebeians need their own bread


class TestPhasesFromAlbion(Anno117TestBase):
    """Phases follow the starting province: starting in Albion, Latium is the second province."""
    options = {"provinces": "both", "starting_province": "albion", "goal": "all_top_tiers"}

    def test_phases_follow_start(self) -> None:
        from .. import gamedata as gd
        items, locs = self.world.item_phases(), self.world.location_phases()
        self.assertEqual(items["Labourer's Yard (Albion)"], gd.EARLY)
        self.assertEqual(items["Tiler (Latium)"], gd.MIDDLE)          # Latium opens at Aldermen/Nobles
        self.assertEqual(locs["Population: 10 Smiths"], gd.EARLY)
        self.assertEqual(locs["Population: 10 Plebeians"], gd.MIDDLE)
        self.assertEqual(locs["Population: 10 Patricians"], gd.LATE)

    def test_early_materials_follow_start(self) -> None:
        self.assertEqual(set(self.multiworld.early_items[self.player]), {"Labourer's Yard (Albion)"})


class TestEarlyMaterialsLatium(Anno117TestBase):
    options = {"provinces": "both", "starting_province": "latium"}

    def test_latium_chain(self) -> None:
        self.assertEqual(set(self.multiworld.early_items[self.player]),
                         {"Tiler (Latium)", "Clay Pit (Latium)", "Charcoal Burner (Latium)"})


class TestEarlyMaterialsOff(Anno117TestBase):
    options = {"provinces": "latium", "early_materials": False}

    def test_none(self) -> None:
        self.assertFalse(self.multiworld.early_items[self.player])
