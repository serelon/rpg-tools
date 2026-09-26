"""The d20-lite toy pack resolves as documented (spec S13)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import SCRIPTS  # noqa: E402
from sheetlib import load_sheet, resolve_full  # noqa: E402

WREN = os.path.normpath(os.path.join(SCRIPTS, "..", "examples", "sheet", "d20-lite", "wren"))


class TestToy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sheet = load_sheet(WREN)
        cls.doc, cls.res = resolve_full(cls.sheet)

    def section(self, gid, sid):
        g = next(g for g in self.doc["groups"] if g["id"] == gid)
        return next(s for s in g["sections"] if s["id"] == sid)

    def test_clean(self):
        self.assertEqual(self.doc["warnings"], [])
        self.assertEqual(self.doc["character"]["name"], "Wren Tallow")

    def test_values(self):
        v = self.doc["values"]
        self.assertEqual([v["ability.%s" % a] for a in ("might", "grace", "grit", "wit", "sense", "charm")],
                         [15, 14, 13, 12, 10, 8])
        self.assertEqual(v["skill.sneak"], "expert")
        self.assertEqual(v["skill.lore"], "expert")
        self.assertEqual(v["xp"], 350)
        self.assertEqual(v["training"], 1)
        self.assertEqual(v["bond"], {"target": "the ferryman who raised her", "strength": 2})
        self.assertEqual(v["patron"], {"ref": "lamplighters-guild", "name": "The Lamplighters' Guild"})

    def test_derived(self):
        d = self.doc["derived"]
        self.assertEqual((d["mod_might"], d["mod_charm"], d["level"], d["prof"]), (2, -1, 2, 2))
        self.assertEqual((d["load"], d["capacity"]), (77, 75))

    def test_skill_bonus_per_trait(self):
        f = {x["key"]: x for x in self.section("skills", "skills")["fields"]}
        self.assertEqual(f["skill.sneak"]["computed"], {"bonus": 6})   # grace +2, prof 2 × 2
        self.assertEqual(f["skill.lore"]["computed"], {"bonus": 5})    # wit +1, 2 × 2
        self.assertEqual(f["skill.persuade"]["computed"], {"bonus": -1})
        self.assertEqual(f["skill.climb"]["index"], 0)

    def test_lists(self):
        feats = self.section("feats", "feats")
        self.assertEqual((feats["count"], feats["cap"]), (2, 2))
        self.assertEqual([e["name"] for e in feats["entries"]], ["Quick Step", "Iron Gut"])
        gear = {e["id"]: e for e in self.doc["lists"]["gear"]}
        self.assertEqual(gear["rations"]["fields"], {"weight": 1, "qty": 5, "load": 5})

    def test_notice_and_span(self):
        self.assertEqual([n["code"] for n in self.doc["notices"]], ["overloaded"])
        self.assertEqual([s["id"] for s in self.doc["spans"]], ["north-road"])
        self.assertTrue(self.doc["spans"][0]["open"])

    def test_earlier_date(self):
        doc, _ = resolve_full(self.sheet, at="412-03")
        self.assertEqual(doc["values"]["skill.sneak"], "proficient")
        self.assertEqual(doc["derived"]["level"], 1)
        self.assertEqual(doc["notices"], [])
        self.assertEqual(doc["warnings"], [])
        feats = [s for g in doc["groups"] for s in g["sections"] if s["id"] == "feats"][0]
        self.assertEqual(feats["cap"], 1)


if __name__ == "__main__":
    unittest.main()
