"""The apworld, client and Lua bridge share an ID scheme and a file format; these tests keep them in sync."""
import pkgutil
import re
import tempfile
import unittest
from pathlib import Path

from .. import gamedata as gd
from ..client import bridge_files, keys
from ..client.mod_install import MOD_FILES, bundled_file
from ..items import ITEM_NAME_TO_ID
from ..locations import LOCATION_NAME_TO_ID


def bridge_source() -> str:
    return bundled_file("ap_anno117/ap_bridge.lua").decode("utf-8")


class TestIds(unittest.TestCase):
    def test_item_ids_decode_to_assets(self) -> None:
        residences = {t.residence for t in gd.TIERS.values()}
        for name, item_id in ITEM_NAME_TO_ID.items():
            if item_id == gd.FILLER_ITEM_ID:
                continue
            guid = item_id - gd.ITEM_BASE
            self.assertTrue(guid in gd.BUILDINGS or guid in residences, name)
            self.assertLess(item_id, gd.ITEM_BASE + 900_000)

    def test_location_ids_decode(self) -> None:
        for name, loc_id in LOCATION_NAME_TO_ID.items():
            if loc_id >= gd.BUILD_LOCATION_BASE:
                self.assertIn(loc_id - gd.BUILD_LOCATION_BASE, gd.BUILDINGS, name)
            else:
                rel = loc_id - gd.POP_LOCATION_BASE
                tier, index = divmod(rel, 100)
                self.assertIn(tier, gd.TIERS, name)
                self.assertEqual(name, gd.TIERS[tier].milestone_name(gd.THRESHOLDS[index]))

    def test_lua_constants_match(self) -> None:
        src = bridge_source()

        def const(name: str) -> int:
            return int(re.search(rf"local {name} = (\d+)", src).group(1))

        self.assertEqual(const("ITEM_BASE"), gd.ITEM_BASE)
        self.assertEqual(const("POP_BASE"), gd.POP_LOCATION_BASE)
        self.assertEqual(const("BUILD_BASE"), gd.BUILD_LOCATION_BASE)
        self.assertEqual(const("DENARII"), gd.DENARII_GUID)
        self.assertLessEqual(const("FILLER_BASE"), gd.FILLER_ITEM_ID)
        table = re.search(r"local THRESHOLDS = \{([^}]*)\}", src).group(1)
        self.assertEqual(tuple(int(x) for x in re.findall(r"\d+", table)), gd.THRESHOLDS)
        self.assertIn(f"AP.PROTOCOL = {gd.BRIDGE_PROTOCOL}", src)

    def test_mod_files_bundled(self) -> None:
        for relative in MOD_FILES:
            self.assertTrue(bundled_file(relative), relative)
        modinfo = bundled_file("modinfo.json").decode("utf-8")
        self.assertIn('"Anno": 8', modinfo)

    def test_data_file_bundled(self) -> None:
        self.assertIsNotNone(pkgutil.get_data("worlds.anno117", "data/game_data.json"))


class TestClientFiles(unittest.TestCase):
    def test_parse_message(self) -> None:
        msg = bridge_files.parse_message("[12:00:01][Lua] AP117|123|CHECK|118149600\r\n")
        self.assertEqual((msg.seed, msg.kind, msg.payload), ("123", "CHECK", "118149600"))
        self.assertIsNone(bridge_files.parse_message("nothing to see"))
        self.assertEqual(bridge_files.parse_message("AP117|-|HELLO|1,0.1.0,a=1;b=0,none,-").kind, "HELLO")
        self.assertEqual(bridge_files.parse_message("AP117|1|SYNC|").payload, "")

    def test_state_file_lines(self) -> None:
        text = bridge_files.render_state(nonce=5, seed="98765", slot='Mar"cus\\', denarii=7, consumed=2,
                                         goal_count=100, goal=[1498], locked=[3141, 3174],
                                         locations={119003174, 118149600}, items=[117003141],
                                         bridge_dir=Path("C:\\Users\\a b\\ap_anno117"), unlock={3142},
                                         auto_unlock=[1499, 3141])
        self.assertIn('S.seed = "98765"', text)
        self.assertIn("S.unlock = {3142}", text)
        self.assertIn("S.auto_unlock = {1499,3141}", text)
        self.assertIn('S.slot = "Mar_cus_"', text)
        self.assertIn("S.locations = {118149600,119003174}", text)
        self.assertIn('S.mod_dir = "C:/Users/a b/ap_anno117/"', text)
        self.assertTrue(text.rstrip().endswith("return AP117_STATE"))
        for line in text.splitlines():
            if line.startswith("S."):
                self.assertNotIn("\n", line)

    def test_tailer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "a.log"
            log.write_bytes(b"old line\nAP117|1|CHECK|5\npartial")
            tail = bridge_files.LogTailer()
            self.assertEqual(tail.poll([log]), ["old line", "AP117|1|CHECK|5"])
            with log.open("ab") as f:
                f.write(b" done\nnext\n")
            self.assertEqual(tail.poll([log]), ["partial done", "next"])
            self.assertEqual(tail.poll([log]), [])
            log.write_bytes(b"new file\n")  # game restarted and truncated the log
            self.assertEqual(tail.poll([log]), ["new file"])
            wide = Path(tmp) / "w.log"
            wide.write_bytes("\ufeffAP117|1|GOAL|100\r\n".encode("utf-16-le"))
            self.assertEqual(tail.poll([wide]), ["AP117|1|GOAL|100"])

    def test_key_frames(self) -> None:
        self.assertEqual(keys.frame("P1"), f"P1*{(ord('P') + ord('1')) % 251}")
        bits = keys.to_bits("A")
        self.assertEqual(bits, [0, 1, 0, 0, 0, 0, 0, 1])


class TestUnlockResidenceCommand(unittest.TestCase):
    def test_names(self) -> None:
        from ..client.context import RESIDENCE_BY_NAME, RESIDENCE_NAMES
        self.assertEqual(RESIDENCE_BY_NAME["equites"], 3142)
        self.assertEqual(RESIDENCE_BY_NAME["eques residence"], 3142)
        self.assertEqual(RESIDENCE_NAMES[3142], "Eques Residence")
        self.assertNotIn(3087, RESIDENCE_NAMES)  # the first tier has nothing to unlock
