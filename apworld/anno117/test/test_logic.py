from . import Anno117TestBase


class TestLatiumLogic(Anno117TestBase):
    options = {"provinces": "latium", "milestones_per_tier": 6, "milestone_cap": 1000, "early_upgrade": "off",
               "shuffle_residences": True}
    run_default_tests = False

    def test_base_tier_free(self) -> None:
        self.assertTrue(self.can_reach_location("Population: 10 Liberti"))
        self.assertTrue(self.can_reach_location("Population: 1000 Liberti"))

    def test_upgrade_needs_residence(self) -> None:
        self.assertFalse(self.can_reach_location("Population: 10 Plebeians"))
        self.collect_by_name("Plebeian Residence")
        self.assertTrue(self.can_reach_location("Population: 10 Plebeians"))
        # growing past the first milestone needs the tier established
        self.assertFalse(self.can_reach_location("Population: 75 Plebeians"))

    def test_established_needs_one_new_good_per_category(self) -> None:
        # Food: bread or garum, Fashion: sandals or soap, Household: amphorae or olive oil, plus tiles (coal-fired)
        self.collect_by_name(["Plebeian Residence", "Tiler (Latium)", "Clay Pit (Latium)", "Charcoal Burner (Latium)",
                              "Salt Ponds (Latium)", "Scomber's Shack (Latium)", "Garum Works (Latium)",
                              "Pig Farm (Latium)", "Tannery (Latium)", "Sandal Maker (Latium)"])
        self.assertFalse(self.can_reach_location("Population: 75 Plebeians"))  # nothing for Household yet
        self.collect_by_name(["Olive Grower (Latium)", "Olive Press (Latium)"])
        self.assertTrue(self.can_reach_location("Population: 75 Plebeians"))
        self.assertTrue(self.can_reach_location("Population: 500 Plebeians"))
        # the biggest milestone needs every good that adds residents (bread, soap, amphorae, ...)
        self.assertFalse(self.can_reach_location("Population: 1000 Plebeians"))
        # Equites can now move in once their residence arrives
        self.collect_by_name("Eques Residence")
        self.assertTrue(self.can_reach_location("Population: 10 Equites"))

    def test_full_plebeian_basket(self) -> None:
        self.collect_all_but(["Olive Press (Latium)", "Eques Residence", "Patrician Residence", "Victory"])
        self.assertTrue(self.can_reach_location("Population: 500 Plebeians"))  # amphorae cover Household
        self.assertFalse(self.can_reach_location("Population: 1000 Plebeians"))
        self.collect_by_name("Olive Press (Latium)")
        self.assertTrue(self.can_reach_location("Population: 1000 Plebeians"))

    def test_build_needs_item_and_workers(self) -> None:
        self.assertFalse(self.can_reach_location("Build: Bakery (Latium)"))
        self.collect_by_name("Bakery (Latium)")
        self.assertFalse(self.can_reach_location("Build: Bakery (Latium)"))  # Plebeian workers
        self.collect_by_name("Plebeian Residence")
        self.assertTrue(self.can_reach_location("Build: Bakery (Latium)"))

    def test_starter_builds_are_free(self) -> None:
        self.assertTrue(self.can_reach_location("Build: Fishing Hut (Latium)"))
        self.assertTrue(self.can_reach_location("Build: Sawmill (Latium)"))

    def test_goal(self) -> None:
        self.assertFalse(self.can_reach_location("Pax Romana"))
        # collect_all_but also collects the Victory event, so test the goal location rather than beatability
        self.collect_all_but(["Fish Gutter (Latium)", "Victory"])  # caviar for Oysters with Caviar
        self.assertFalse(self.can_reach_location("Pax Romana"))
        self.collect_by_name("Fish Gutter (Latium)")
        self.assertTrue(self.can_reach_location("Pax Romana"))


class TestSecondProvince(Anno117TestBase):
    options = {"provinces": "both", "starting_province": "latium", "goal": "patricians", "shuffle_residences": True}
    run_default_tests = False

    def test_albion_after_equites(self) -> None:
        self.assertFalse(self.can_reach_region("Albion"))
        albion = [n for n in self.world.plan.item_names if "(Albion)" in n]
        self.collect_all_but(albion + ["Eques Residence"])
        self.assertFalse(self.can_reach_region("Albion"))  # Plebeians alone do not open it
        self.collect_by_name("Eques Residence")
        self.assertTrue(self.can_reach_region("Albion"))
        self.assertTrue(self.can_reach_location("Population: 10 Waders"))


class TestVanillaResidences(Anno117TestBase):
    """Default: residences are not shuffled, tiers unlock the normal way, buildings wait for their usual tier."""
    options = {"provinces": "latium", "milestones_per_tier": 6, "milestone_cap": 1000}
    run_default_tests = False

    def test_no_residence_items(self) -> None:
        names = {i.name for i in self.multiworld.itempool if i.player == self.player}
        self.assertFalse(names & {"Plebeian Residence", "Eques Residence", "Patrician Residence"})
        self.assertNotIn(3141, self.world.plan.locked_guids)

    def test_oyster_bed_waits_for_patricians(self) -> None:
        self.collect_by_name("Oyster Bed (Latium)")
        self.assertFalse(self.can_reach_location("Build: Oyster Bed (Latium)"))  # Liberti alone: not yet

    def test_oyster_bed_buildable_late(self) -> None:
        self.collect_all_but(["Oyster Bed (Latium)"])
        self.assertFalse(self.can_reach_location("Build: Oyster Bed (Latium)"))
        self.collect_by_name("Oyster Bed (Latium)")
        self.assertTrue(self.can_reach_location("Build: Oyster Bed (Latium)"))

    def test_gate_applies_to_every_holder(self) -> None:
        # whatever sits on the oyster check, logic only counts it once Patricians exist
        logic = self.world.logic
        w = logic.status(self.multiworld.state)
        self.assertFalse(logic.can_build(w, next(b for b in self.world.plan.buildings if b.base_name == "Oyster Bed")))


class TestFuel(Anno117TestBase):
    """Kilns, bakeries and smelters burn coal: without a coal producer they make nothing."""
    options = {"provinces": "latium", "milestones_per_tier": 6, "milestone_cap": 1000, "early_upgrade": "off",
               "shuffle_residences": True}
    run_default_tests = False

    def test_tiles_need_coal(self) -> None:
        self.collect_by_name(["Plebeian Residence", "Tiler (Latium)", "Clay Pit (Latium)",
                              "Salt Ponds (Latium)", "Scomber's Shack (Latium)", "Garum Works (Latium)",
                              "Pig Farm (Latium)", "Tannery (Latium)", "Sandal Maker (Latium)",
                              "Olive Grower (Latium)", "Olive Press (Latium)"])
        self.assertFalse(self.can_reach_location("Population: 75 Plebeians"))
        self.collect_by_name("Charcoal Burner (Latium)")
        self.assertTrue(self.can_reach_location("Population: 75 Plebeians"))


class TestCoalMinesNotRelied(Anno117TestBase):
    """Coal Mines need deposits that may be missing: logic only trusts Charcoal Burners for coal."""
    options = {"provinces": "latium", "prophecies_of_ash": True, "milestones_per_tier": 6, "milestone_cap": 1000,
               "early_upgrade": "off", "shuffle_residences": True}
    run_default_tests = False

    def test_coal_mine_is_no_coal_source(self) -> None:
        self.collect_by_name(["Plebeian Residence", "Tiler (Latium)", "Clay Pit (Latium)", "Coal Mine (Latium)",
                              "Salt Ponds (Latium)", "Scomber's Shack (Latium)", "Garum Works (Latium)",
                              "Pig Farm (Latium)", "Tannery (Latium)", "Sandal Maker (Latium)",
                              "Olive Grower (Latium)", "Olive Press (Latium)"])
        self.assertFalse(self.can_reach_location("Population: 75 Plebeians"))
        self.collect_by_name("Charcoal Burner (Latium)")
        self.assertTrue(self.can_reach_location("Population: 75 Plebeians"))

    def test_no_check_and_not_progression(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("Build: Coal Mine (Latium)", names)
        item = self.world.create_item("Coal Mine (Latium)")
        self.assertFalse(item.advancement)


class TestProvinceAccess(Anno117TestBase):
    """Both provinces: the second one opens with third-tier residents at home, as in the game."""
    options = {"provinces": "both", "starting_province": "latium", "goal": "all_top_tiers"}
    run_default_tests = False

    def test_needs_third_tier(self) -> None:
        from .. import gamedata as gd
        logic = self.world.logic
        latium_only = [n for n in self.world.plan.item_names if n.endswith("(Latium)")]
        w = logic.evaluate(lambda name: name in latium_only)
        self.assertTrue(logic.established(w, 1497))           # Equites established with Latium alone
        self.assertTrue(logic.region_open(w, gd.REGION_ALBION))
        # without anything that Equites need, Plebeians can be sustained but Albion stays shut
        equites_goods = set().union(*gd.CATEGORY_PRODUCTS[1497].values()) - set().union(
            *gd.CATEGORY_PRODUCTS[1496].values())
        blockers = {b.name for b in self.world.plan.item_buildings if b.outputs & equites_goods}
        w = logic.evaluate(lambda name: name in latium_only and name not in blockers)
        self.assertTrue(logic.sustained(w, 1496))
        self.assertFalse(logic.established(w, 1497))
        self.assertFalse(logic.region_open(w, gd.REGION_ALBION))
