"""Mounts: sheets inside sheets, read one way down, plus lens sections.
Synthetic data only (a 'hold' mounting 'pods' mounting 'cells')."""
import os
import shutil
import tempfile
import unittest

from sheet_helpers import codes, ev, write_json  # noqa: E402
from sheetlib import load_sheet, resolve_full  # noqa: E402

RULES = {"id": "m", "traits": {"fuel": {"type": "number"}},
         "mounts": {"pod": {"name": "Pods"}, "cell": {"name": "Cells"}},
         "derived": {"total": "sum(mounts.pod[*].fuel)",
                     "a_fuel": "mount.pod.a.fuel",
                     "deep": "mount.pod.a.mount.cell.c1.fuel",
                     "twice": "mount.pod.b.double"}}
CHILD_RULES = {"id": "c", "traits": {"fuel": {"type": "number"}},
               "mounts": {"cell": {}}, "derived": {"double": "fuel * 2"}}
SHAPE = {"id": "s", "groups": {"g": {"sections": {
    "lens": {"mounts": "pod", "fields": [{"key": "fuel", "name": "Fuel"}, {"key": "double"}]}}}}}


class MountCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        write_json(self.p("pack/rules.json"), RULES)
        write_json(self.p("pack/child.json"), CHILD_RULES)
        write_json(self.p("pack/shape.json"), SHAPE)
        write_json(self.p("pack/empty.json"), {"id": "e", "groups": {}})
        write_json(self.p("pack/catalog.json"), {})

    def p(self, rel):
        return os.path.join(self.root, rel)

    def sheet(self, name, rules, events, shape="empty"):
        write_json(self.p("%s/sheet.json" % name), {
            "id": name, "name": name.title(), "rules": "../pack/%s.json" % rules,
            "shape": "../pack/%s.json" % shape, "catalog": "../pack/catalog.json",
            "history": ["history/*.json"]})
        write_json(self.p("%s/history/s01.json" % name), {"source": "s01", "events": events})

    def build(self):
        self.sheet("cell1", "child", [ev("1100", {"set": "fuel", "to": 7})])
        self.sheet("a", "child", [ev("1100", {"set": "fuel", "to": 3}),
                                  ev("1100", {"mount": "cell", "id": "c1", "ref": "../cell1"}),
                                  ev("1102", {"set": "fuel", "to": 30})])
        self.sheet("b", "child", [ev("1100", {"set": "fuel", "to": 5})])
        self.sheet("hold", "rules", [
            ev("1100", {"set": "fuel", "to": 0}),
            ev("1100-02", {"mount": "pod", "id": "a", "ref": "../a"},
               {"mount": "pod", "id": "b", "ref": "../b"}),
            ev("1101", {"mount": "pod", "id": "x", "ref": "../b"}, gm_only=True),
            ev("1103", {"unmount": "pod", "id": "x"})], shape="shape")

    def resolve(self, at=None, view="gm"):
        return resolve_full(load_sheet(self.p("hold")), at=at, view=view)


class TestMounts(MountCase):
    def test_reads_one_way_down(self):
        self.build()
        doc, res = self.resolve(at="1100-06")
        self.assertEqual(doc["derived"]["total"], 8)
        self.assertEqual(doc["derived"]["a_fuel"], 3)
        self.assertEqual(doc["derived"]["deep"], 7)
        self.assertEqual(doc["derived"]["twice"], 10)
        self.assertEqual(codes(res), [])

    def test_children_resolve_at_parent_date(self):
        self.build()
        doc, _ = self.resolve(at="1101-06")
        self.assertEqual(doc["derived"]["total"], 3 + 5 + 5)  # x mounted (gm_only) too
        doc, _ = self.resolve(at="1102-06")
        self.assertEqual(doc["derived"]["a_fuel"], 30)
        doc, _ = self.resolve()
        self.assertEqual(doc["derived"]["total"], 35)  # x unmounted in 1103
        doc, _ = self.resolve(at="1099")
        self.assertIsNone(doc["derived"]["a_fuel"])
        self.assertEqual(doc["derived"]["total"], 0)

    def test_lens_and_player_view(self):
        self.build()
        doc, _ = self.resolve(at="1101-06")
        sec = doc["groups"][0]["sections"][0]
        self.assertEqual(sec["kind"], "mounts")
        self.assertEqual([r["id"] for r in sec["rows"]], ["a", "b", "x"])
        self.assertEqual(sec["rows"][0]["fields"],
                         [{"key": "fuel", "name": "Fuel", "value": 3},
                          {"key": "double", "name": "Double", "value": 6}])
        self.assertEqual(sec["rows"][0]["name"], "A")
        self.assertTrue(doc["mounts"]["pod"][2]["gm_only"])
        pdoc, _ = self.resolve(at="1101-06", view="player")
        self.assertEqual([r["id"] for r in pdoc["groups"][0]["sections"][0]["rows"]], ["a", "b"])
        self.assertEqual([m["id"] for m in pdoc["mounts"]["pod"]], ["a", "b"])

    def test_lifecycle_warnings(self):
        self.build()
        self.sheet("hold", "rules", [
            ev("1100", {"mount": "pod", "id": "a", "ref": "../a"}),
            ev("1101", {"mount": "pod", "id": "a", "ref": "../a"}),
            ev("1102", {"unmount": "pod", "id": "zz"}),
            ev("1103", {"mount": "boat", "id": "q", "ref": "../b"}),
            ev("1104", {"mount": "pod", "id": "n"})], shape="shape")
        doc, res = self.resolve()
        c = codes(res)
        self.assertEqual(c.count("invalid-event"), 3)  # double mount, unmount missing, no ref
        self.assertIn("unknown-trait", c)
        self.assertEqual(doc["mounts"]["boat"][0]["id"], "q")

    def test_missing_child_and_cycle(self):
        self.build()
        self.sheet("a", "child", [ev("1100", {"mount": "cell", "id": "loop", "ref": "../hold"})])
        self.sheet("hold", "rules", [ev("1100", {"mount": "pod", "id": "a", "ref": "../a"},
                                            {"mount": "pod", "id": "gone", "ref": "../nowhere"})],
                   shape="empty")
        write_json(self.p("pack/rules.json"), dict(RULES, derived={
            "loop": "mount.pod.a.mount.cell.loop.fuel", "gone": "mount.pod.gone.fuel"}))
        doc, res = self.resolve()
        self.assertIsNone(doc["derived"]["loop"])
        self.assertIsNone(doc["derived"]["gone"])
        msgs = " ".join(w["message"] for w in res.warnings if w["code"] == "expr-error")
        self.assertIn("mount cycle", msgs)
        self.assertIn("missing sheet.json", msgs)

    def test_bad_shapes(self):
        from sheetlib import SheetError
        self.build()
        for shape in ({"mounts": "nope"}, {"mounts": "pod", "fields": [{"name": "x"}]}):
            write_json(self.p("pack/shape.json"), {"id": "s", "groups": {"g": {"sections": {
                "lens": shape}}}})
            with self.assertRaises(SheetError):
                load_sheet(self.p("hold"))


if __name__ == "__main__":
    unittest.main()
