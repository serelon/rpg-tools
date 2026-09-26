"""Tests for the resolved JSON output and JS fragment (spec S8, S10)."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import BASE_CATALOG, BASE_RULES, SheetDir, creation_event, ev  # noqa: E402
from sheetlib import export_js  # noqa: E402


def out_rules():
    r = copy.deepcopy(BASE_RULES)
    r["classes"]["power"]["per_trait"] = {"double": "value * 2", "is_kin": "id in catalog('kind', kind).powers"}
    r["derived"]["secret"] = {"expr": "level * 100", "gm_only": True}
    r["derived"]["half"] = "level / 2"
    r["lists"]["marks"] = {"name": "Marks", "catalog": "markcat",
                           "fields": {"weight": "if(entry.depth == None, 0, entry.depth * 2)"}}
    r["lists"]["hidden"] = {"name": "Hidden", "gm_only": True}
    r["spans"]["dream"] = {"name": "Dream", "gm_only": True}
    r["traits"]["secret_name"] = {"type": "text", "gm_only": True}
    return r


CATALOG = copy.deepcopy(BASE_CATALOG)
CATALOG["markcat"] = {"scar": {"name": "Old Scar", "text": "From the catalog.",
                               "levels": {"1": {"name": "Faint", "text": "Barely there."}}}}

SHAPE = {"id": "out-shape", "groups": {
    "ident": {"name": "Identity", "order": 10, "sections": {
        "core": {"order": 10, "fields": [
            {"key": "kind", "kind": "choice", "options": {"catalog": "kind"}},
            {"key": "path", "kind": "choice", "options": {"table": "path"}},
            {"key": "tier", "kind": "choice", "options": {"values": ["low", "mid", "high"]}},
            {"key": "level", "kind": "scalar"},
            {"key": "cap", "kind": "derived"},
            {"key": "pool", "kind": "pool"},
            {"key": "xp", "kind": "pool"},
            {"kind": "track", "name": "Health", "levels": ["a", "b"]},
            {"kind": "track", "name": "Stress", "max": "cap + 1"},
            {"key": "mentor", "kind": "relation"},
            {"key": "bond", "kind": "fixed"},
            {"key": "secret_name", "kind": "scalar"},
            {"key": "secret", "kind": "derived"},
            {"key": "knack.hidden", "kind": "named", "show": "present"},
            {"kind": "nested", "name": "Box", "fields": [
                {"key": "attr.one", "kind": "fixed", "name": "Custom One", "max": 9}]}]},
        "gm": {"order": 20, "gm_only": True, "fields": [{"key": "level", "kind": "scalar"}]}}},
    "attrs": {"name": "Attributes", "order": 20, "sections": {
        "body": {"name": "Body", "order": 10, "class": "attr", "where": {"group": "body"}, "show": "all"},
        "mind": {"name": "Mind", "order": 20, "class": "attr", "where": {"group": "mind"}}}},
    "powers": {"name": "Powers", "order": 30, "sections": {
        "powers": {"class": "power", "show": "present"}}},
    "knacks": {"name": "Knacks", "order": 40, "sections": {
        "knacks": {"class": "knack"}}},
    "virtues": {"name": "Virtues", "order": 50, "sections": {
        "v": {"class": "virtue", "show": "active"}}},
    "marks": {"name": "Marks", "order": 60, "sections": {
        "marks": {"list": "marks", "note": "Things that stay"},
        "items": {"order": 2, "list": "items"},
        "hidden": {"order": 3, "list": "hidden"}}},
    "time": {"name": "Time", "order": 70, "sections": {"spans": {"spans": "*"}}},
    "secret": {"name": "Secret", "order": 80, "gm_only": True, "sections": {
        "s": {"fields": [{"key": "level", "kind": "scalar"}]}}},
}}


def history():
    return {
        "creation": [creation_event("1100")],
        "s01": [
            ev("1110", {"add": "power.glow", "by": 2}, {"add": "xp", "by": 5},
               note="contains </script> and <!-- comment", free="x"),
            ev("1111", {"set": "knack.zeta", "to": 1}, {"set": "knack.alpha", "to": 2},
               {"gain": "list.marks", "id": "scar-1", "entry": {"ref": "scar", "depth": 3}},
               {"gain": "list.marks", "id": "plain", "entry": {"name": "Plain", "text": "own", "depth": 0}},
               {"set": "mentor", "to": {"ref": "../elder/sheet.json", "name": "The Elder"}},
               {"set": "bond", "to": {"who": "Someone", "grip": 1}},
               {"start": "sleep", "id": "sl-1"}, free="x"),
            ev("1112", {"set": "knack.hidden", "to": 2},
               {"gain": "list.marks", "id": "gm-mark", "entry": {"name": "Secret mark"}},
               {"start": "sleep", "id": "gm-sleep"},
               {"set": "secret_name", "to": "Hidden Name"},
               gm_only=True, free="x"),
            ev("1113", {"gain": "list.hidden", "id": "h", "entry": {}},
               {"start": "dream", "id": "d1"},
               {"gain": "list.marks", "id": "flagged", "entry": {"name": "Flagged", "gm_only": True}},
               {"set": "knack.retired", "to": 1}, free="x"),
            ev("1114", {"retire": "knack.retired"}, {"end": "sleep", "id": "sl-1"}),
            ev("1120-07", {"add": "attr.two"}, free="x")],
        "branch-1200": [ev("1200", {"anchor": "attr.two", "id": "a2", "at_least": 3})],
    }


class OutputCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sd = SheetDir(out_rules(), shape=SHAPE, catalog=CATALOG, history=history())
        cls.gm, cls.res = cls.sd.resolve()
        cls.pl, _ = cls.sd.resolve(view="player")

    @classmethod
    def tearDownClass(cls):
        cls.sd.cleanup()

    def group(self, doc, gid):
        return next(g for g in doc["groups"] if g["id"] == gid)

    def section(self, doc, gid, sid):
        return next(s for s in self.group(doc, gid)["sections"] if s["id"] == sid)

    def field(self, doc, gid, sid, key, name=None):
        for f in self.section(doc, gid, sid)["fields"]:
            if f["key"] == key and (name is None or f["name"] == name):
                return f
        return None


class TestStructure(OutputCase):
    def test_top_level_key_order(self):
        self.assertEqual(list(self.gm), ["format", "view", "at", "character", "system", "groups",
                                         "lists", "spans", "values", "derived", "anchors",
                                         "warnings", "notices"])
        self.assertEqual(list(self.pl), ["format", "view", "at", "character", "system", "groups",
                                         "lists", "spans", "values", "derived"])
        self.assertEqual(self.gm["format"], "sheet/1")
        self.assertEqual(self.gm["view"], "gm")
        self.assertIsNone(self.gm["at"])
        self.assertEqual(self.gm["character"], {"id": "test-char", "name": "Test Character",
                                                "meta": {"concept": "synthetic"}})
        self.assertEqual(self.gm["system"], {"rules": "gen", "shape": "out-shape"})

    def test_group_and_section_order(self):
        self.assertEqual([g["id"] for g in self.gm["groups"]],
                         ["ident", "attrs", "powers", "knacks", "virtues", "marks", "time", "secret"])
        self.assertEqual([s["id"] for s in self.group(self.gm, "marks")["sections"]],
                         ["marks", "items", "hidden"])
        sec = self.section(self.gm, "marks", "marks")
        self.assertEqual(list(sec)[:3], ["id", "name", "kind"])
        self.assertEqual(sec["note"], "Things that stay")

    def test_type_on_every_trait_backed_field(self):
        def walk(fields):
            for f in fields:
                yield f
                yield from walk(f.get("fields") or [])
        derived = set(out_rules()["derived"])
        for g in self.gm["groups"]:
            for s in g["sections"]:
                for f in walk(s.get("fields") or []):
                    if f["key"] is None or f["key"] in derived:
                        self.assertNotIn("type", f, f)
                        self.assertNotIn("from", f, f)
                    else:
                        self.assertIn("type", f, f)
                        self.assertIn("from", f, f)
                        self.assertEqual(list(f)[:5], ["key", "kind", "type", "name", "value"])

    def test_values_membership(self):
        v = self.gm["values"]
        self.assertNotIn("virtue.gamma", v)       # declared, absent
        self.assertNotIn("knack.retired", v)      # retired
        self.assertEqual(v["attr.two"], 3)        # anchored (lifted from 2)
        self.assertEqual(v["power.glow"], 2)

    def test_derived_integral_floats(self):
        self.assertEqual(self.gm["derived"]["half"], 0.5)
        self.assertEqual(self.gm["derived"]["pool"], 6)
        self.assertIsInstance(self.gm["derived"]["pool"], int)


class TestFieldKinds(OutputCase):
    def test_rating_fixed(self):
        f = self.field(self.gm, "attrs", "body", "attr.one")
        self.assertEqual((f["kind"], f["type"], f["value"], f["min"], f["max"]), ("fixed", "rating", 2, 1, 5))
        self.assertEqual(f["name"], "One")
        self.assertEqual(f["from"], ["creation#1"])

    def test_show_all_includes_absent_declared_with_empty_from(self):
        f = self.field(self.gm, "attrs", "body", "attr.two")
        self.assertEqual(f["value"], 3)
        self.assertEqual(f["from"], ["s01#6", "branch-1200#1"])
        self.assertIsNone(self.field(self.gm, "attrs", "mind", "attr.three"))  # show present

    def test_catalog_levels_up_to_value(self):
        f = self.field(self.gm, "powers", "powers", "power.glow")
        self.assertEqual(f["kind"], "catalog")
        self.assertEqual(f["text"], "Gives light.")
        self.assertEqual([lv["level"] for lv in f["levels"]], [1, 2])
        self.assertEqual(f["levels"][1], {"level": 2, "name": "Lamp", "text": "A lamp."})
        self.assertEqual(f["computed"], {"double": 4, "is_kin": True})

    def test_named_open_class_order(self):
        keys = [f["key"] for f in self.section(self.gm, "knacks", "knacks")["fields"]]
        self.assertEqual(keys, ["knack.alpha", "knack.hidden", "knack.zeta"])  # undeclared by name
        self.assertEqual(self.field(self.gm, "knacks", "knacks", "knack.alpha")["kind"], "named")

    def test_choice(self):
        f = self.field(self.gm, "ident", "core", "kind")
        self.assertEqual((f["value"], f["display"], f["text"]), ("k1", "Kind One", "First kind."))
        f = self.field(self.gm, "ident", "core", "path")
        self.assertEqual((f["value"], f["display"], f["text"]), ("first", "First Path", None))
        f = self.field(self.gm, "ident", "core", "tier")
        self.assertEqual((f["type"], f["value"], f["display"], f["values"], f["index"]),
                         ("enum", "low", "low", ["low", "mid", "high"], 0))

    def test_scalar_derived_pool(self):
        self.assertEqual(self.field(self.gm, "ident", "core", "level")["value"], 1)
        cap = self.field(self.gm, "ident", "core", "cap")
        self.assertEqual(cap, {"key": "cap", "kind": "derived", "name": "Cap", "value": 3})
        pool = self.field(self.gm, "ident", "core", "pool")
        self.assertEqual((pool["name"], pool["value"], pool["max"]), ("Pool", 6, 6))
        xp = self.field(self.gm, "ident", "core", "xp")
        self.assertEqual((xp["type"], xp["value"], xp["max"]), ("number", 5, 5))
        self.assertIn("from", xp)

    def test_track(self):
        health = self.field(self.gm, "ident", "core", None, "Health")
        self.assertEqual(health, {"key": None, "kind": "track", "name": "Health", "value": None,
                                  "levels": ["a", "b"]})
        stress = self.field(self.gm, "ident", "core", None, "Stress")
        self.assertEqual(stress["max"], 4)

    def test_relation_compound(self):
        f = self.field(self.gm, "ident", "core", "mentor")
        self.assertEqual(f["type"], "relation")
        self.assertEqual(f["value"], {"ref": "../elder/sheet.json", "name": "The Elder"})
        self.assertTrue(f["gm_only"])
        b = self.field(self.gm, "ident", "core", "bond")
        self.assertEqual(b["type"], "compound")
        self.assertEqual(b["value"], {"who": "Someone", "grip": 1, "mood": "cold"})
        self.assertEqual(b["parts"], [
            {"part": "who", "type": "text", "value": "Someone"},
            {"part": "grip", "type": "rating", "value": 1, "min": 0, "max": 3},
            {"part": "mood", "type": "enum", "value": "cold", "values": ["cold", "warm"], "index": 0}])

    def test_nested_and_display_max(self):
        box = self.field(self.gm, "ident", "core", None, "Box")
        self.assertEqual(box["kind"], "nested")
        inner = box["fields"][0]
        self.assertEqual((inner["name"], inner["max"]), ("Custom One", 9))

    def test_active_show_and_inactive_flag(self):
        keys = [f["key"] for f in self.section(self.gm, "virtues", "v")["fields"]]
        self.assertEqual(keys, ["virtue.alpha", "virtue.beta"])

    def test_warn_on_fields(self):
        f = self.field(self.gm, "attrs", "body", "attr.two")
        self.assertEqual(f["warn"], ["unsatisfied-anchor"])  # warnings carrying the key
        self.assertNotIn("warn", self.field(self.gm, "attrs", "body", "attr.one"))

    def test_fixture_warnings(self):
        self.assertEqual(sorted(w["code"] for w in self.gm["warnings"]),
                         ["unsatisfied-anchor"])


class TestListsSpans(OutputCase):
    def test_list_entries_catalog_join_and_computed(self):
        sec = self.section(self.gm, "marks", "marks")
        self.assertEqual(list(sec), ["id", "name", "kind", "list", "count", "cap", "entries", "note"])
        e = sec["entries"][0]
        self.assertEqual(e["id"], "scar-1")
        self.assertEqual((e["name"], e["text"], e["ref"]), ("Old Scar", "From the catalog.", "scar"))
        self.assertEqual(e["levels"], [{"level": 1, "name": "Faint", "text": "Barely there."}])
        self.assertEqual(e["fields"], {"depth": 3, "weight": 6})
        self.assertEqual(e["from"], ["s01#2"])
        plain = sec["entries"][1]
        self.assertEqual((plain["name"], plain["text"]), ("Plain", "own"))
        self.assertEqual(sec["count"], 4)
        items = self.section(self.gm, "marks", "items")
        self.assertEqual(items["cap"], 2)

    def test_spans_and_years(self):
        sp = {s["id"]: s for s in self.gm["spans"]}
        s = sp["sl-1"]
        self.assertEqual((s["start"], s["end"], s["open"], s["years"]), ("1111", "1114", False, 3.0))
        self.assertIsInstance(s["years"], float)
        # open span runs to the latest included event (1200)
        self.assertEqual(sp["gm-sleep"]["years"], 88.0)
        doc, _ = self.sd.resolve(at="1120")
        g = {s["id"]: s for s in doc["spans"]}["gm-sleep"]
        self.assertEqual(g["years"], round(1120 + 11 / 12 + 30 / 372 - 1112, 2))

    def test_anchors_block(self):
        a = self.gm["anchors"][0]
        self.assertEqual(a, {"id": "a2", "key": "attr.two", "at_least": 3, "date": "1200",
                             "satisfied": False, "folded": 2, "satisfied_by": [],
                             "from": ["branch-1200#1"]})


class TestPlayerView(OutputCase):
    def test_gm_only_stripped(self):
        pl = self.pl
        self.assertNotIn("secret", [g["id"] for g in pl["groups"]])
        self.assertNotIn("gm", [s["id"] for s in self.group(pl, "ident")["sections"]])
        self.assertIsNone(self.field(pl, "ident", "core", "mentor"))       # TraitDef gm_only
        self.assertIsNone(self.field(pl, "ident", "core", "secret"))       # gm_only derived
        self.assertNotIn("secret", pl["derived"])
        self.assertIn("half", pl["derived"])
        self.assertNotIn("mentor", pl["values"])
        self.assertNotIn("hidden", pl["lists"])
        self.assertNotIn("hidden", [s["id"] for s in self.group(pl, "marks")["sections"]])
        self.assertNotIn("d1", [s["id"] for s in pl["spans"]])            # gm_only span kind
        self.assertNotIn("gm_only", json.dumps(pl))

    def test_gm_only_created_inheritance(self):
        pl, gm = self.pl, self.gm
        self.assertIn("knack.hidden", gm["values"])
        self.assertNotIn("knack.hidden", pl["values"])
        self.assertNotIn("secret_name", pl["values"])
        self.assertIsNone(self.field(pl, "ident", "core", "knack.hidden"))
        self.assertNotIn("knack.hidden", [f["key"] for f in self.section(pl, "knacks", "knacks")["fields"]])
        ids = [e["id"] for e in pl["lists"]["marks"]]
        self.assertEqual(ids, ["scar-1", "plain"])  # gm-created and gm_only-flagged dropped
        self.assertEqual(self.section(pl, "marks", "marks")["count"], 2)
        self.assertNotIn("gm-sleep", [s["id"] for s in pl["spans"]])
        self.assertTrue(self.field(gm, "knacks", "knacks", "knack.hidden")["gm_only"])

    def test_refs_to_gm_and_anchor_events_removed(self):
        f = self.field(self.pl, "attrs", "body", "attr.two")
        self.assertEqual(f["value"], 3)             # values identical to GM
        self.assertEqual(f["from"], ["s01#6"])      # anchor event ref dropped
        self.assertEqual(self.pl["values"], {k: v for k, v in self.gm["values"].items()
                                             if k not in ("knack.hidden", "secret_name", "mentor")})

    def test_no_warn_in_player(self):
        self.assertNotIn('"warn"', json.dumps(self.pl))


class TestProvenanceOff(unittest.TestCase):
    def test_off_removes_from_and_satisfied_by(self):
        sd = SheetDir(out_rules(), shape=SHAPE, catalog=CATALOG, history=history())
        self.addCleanup(sd.cleanup)
        doc, _ = sd.resolve(provenance=False)
        text = json.dumps(doc)
        self.assertNotIn('"from"', text)
        self.assertNotIn('"satisfied_by"', text)


class TestFragment(OutputCase):
    def test_escaping_and_header(self):
        doc, _ = self.sd.resolve(view="player")
        doc["character"]["meta"]["note"] = "a </script> b <!-- c"
        js = export_js(doc, "path/to/char", at="1200")
        self.assertTrue(js.startswith("/* GENERATED — do not hand-edit.\n"))
        self.assertIn("Source: path/to/char (player view, at 1200)", js)
        self.assertIn("Regenerate: python rpg-tools/scripts/sheet.py export path/to/char --at 1200 */", js)
        body = js.split("*/\n", 1)[1]
        self.assertTrue(body.startswith("DATA.sheet = "))
        self.assertTrue(body.endswith(";\n"))
        self.assertNotIn("<", body)
        self.assertIn("\\u003c/script>", body)
        self.assertIn("\\u003c!--", body)
        payload = json.loads(body[len("DATA.sheet = "):-2])
        self.assertEqual(payload["character"]["meta"]["note"], "a </script> b <!-- c")

    def test_key(self):
        js = export_js({"format": "sheet/1"}, "x", key="ailsa")
        self.assertIn('(DATA.sheets = DATA.sheets || {})["ailsa"] = {', js)
        self.assertIn("at latest", js)


if __name__ == "__main__":
    unittest.main()
