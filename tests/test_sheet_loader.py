"""Tests for sheetlib.loader: extends, merge, globs, manifest (spec S2, S3, S5)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import FIXTURES, SheetDir, write_json  # noqa: E402
from sheetlib.expr import SheetError  # noqa: E402
from sheetlib import loader  # noqa: E402


def fx(*parts):
    return os.path.join(FIXTURES, *parts)


class TestMerge(unittest.TestCase):
    def test_deep_merge_null_removes_arrays_replace(self):
        base = {"a": 1, "d": {"x": 1, "y": 2}, "arr": [1, 2], "gone": 5}
        over = {"d": {"y": 3, "z": 4}, "arr": [9], "gone": None, "new": 1}
        m = loader.merge(base, over)
        self.assertEqual(m, {"a": 1, "d": {"x": 1, "y": 3, "z": 4}, "arr": [9], "new": 1})

    def test_key_order_parent_kept_new_appended(self):
        m = loader.merge({"b": 1, "a": 1, "c": 1}, {"a": 2, "z": 1, "b": 2})
        self.assertEqual(list(m), ["b", "a", "c", "z"])

    def test_null_inside_new_dict_is_removed(self):
        m = loader.merge({}, {"d": {"x": None, "y": 1}})
        self.assertEqual(m, {"d": {"y": 1}})

    def test_merge_does_not_alias_inputs(self):
        base = {"arr": [1]}
        over = {"arr": [2]}
        m = loader.merge(base, over)
        m["arr"].append(3)
        self.assertEqual(over["arr"], [2])


class TestExtends(unittest.TestCase):
    def test_string_extends_relative(self):
        merged, files = loader.load_merged("diamond/a.json", FIXTURES, "rules")
        self.assertEqual(merged["x"], "A")
        self.assertNotIn("gone", merged)
        self.assertEqual(merged["nested"], {"a": 1, "b": 2})
        self.assertEqual(merged["arr"], [9])
        self.assertNotIn("extends", merged)
        self.assertEqual([os.path.basename(f) for f in files], ["c.json", "a.json"])

    def test_diamond_linearisation(self):
        merged, files = loader.load_merged("diamond/x.json", FIXTURES, "rules")
        self.assertEqual([os.path.basename(f) for f in files],
                         ["c.json", "a.json", "b.json", "x.json"])
        # A overrides C's x; B does not touch it → A's value survives.
        self.assertEqual(merged["x"], "A")
        # A removed 'gone' with null; C must not be re-merged to resurrect it.
        self.assertNotIn("gone", merged)
        self.assertEqual(merged["arr"], [9])
        self.assertTrue(merged["b_only"])
        self.assertEqual(merged["own"], 1)

    def test_list_in_manifest_merged_left_to_right_as_if_extended(self):
        merged, files = loader.load_merged(["diamond/a.json", "diamond/b.json"], FIXTURES, "rules")
        self.assertEqual([os.path.basename(f) for f in files], ["c.json", "a.json", "b.json"])
        self.assertEqual(merged["x"], "A")

    def test_cycle_message(self):
        with self.assertRaises(SheetError) as cm:
            loader.load_merged("cycle/a.json", FIXTURES, "rules")
        self.assertIn("Circular extends detected: a.json -> b.json -> a.json", str(cm.exception))

    def test_glob_natural_sort(self):
        merged, files = loader.load_merged("glob/base.json", FIXTURES, "rules")
        self.assertEqual([os.path.basename(f) for f in files],
                         ["p1.json", "p2.json", "p10.json", "base.json"])
        self.assertEqual(merged["last"], "p10")
        self.assertTrue(merged["p1"] and merged["p2"] and merged["p10"] and merged["base"])

    def test_file_matching_its_own_glob_is_skipped(self):
        merged, files = loader.load_merged("selfglob/all.json", FIXTURES, "rules")
        self.assertEqual([os.path.basename(f) for f in files], ["other.json", "all.json"])
        self.assertEqual(merged["who"], "all")

    def test_missing_file_is_fatal(self):
        with self.assertRaises(SheetError):
            loader.load_merged("nope.json", FIXTURES, "rules")

    def test_natural_key(self):
        names = ["s10", "s2", "s1", "branch-1200", "s02b"]
        self.assertEqual(sorted(names, key=loader.natural_key),
                         ["branch-1200", "s1", "s2", "s02b", "s10"])


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.sd = SheetDir({"id": "r"}, patterns=["history/creation.json", "history/s*.json",
                                                  "history/*.json"])
        for stem in ("s10", "s2", "creation", "branch-1"):
            self.sd.write_history(stem, [])

    def tearDown(self):
        self.sd.cleanup()

    def test_history_order_and_file_index(self):
        sheet = self.sd.load()
        self.assertEqual([h.stem for h in sheet.history], ["creation", "s2", "s10", "branch-1"])
        self.assertEqual([h.index for h in sheet.history], [0, 1, 2, 3])

    def test_manifest_dir_or_file(self):
        a = self.sd.load()
        from sheetlib import load_sheet
        b = load_sheet(os.path.join(self.sd.dir, "sheet.json"))
        self.assertEqual(a.path, b.path)
        self.assertEqual(a.id, "test-char")
        self.assertEqual(a.meta, {"concept": "synthetic"})

    def test_missing_required_field_fatal(self):
        write_json(os.path.join(self.sd.dir, "sheet.json"), {"id": "x", "name": "x"})
        with self.assertRaises(SheetError):
            self.sd.load()

    def test_malformed_history_is_warning_not_fatal(self):
        with open(os.path.join(self.sd.dir, "history", "s3.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.sd.write_history("s4", {"events": "not-a-list"})
        res = self.sd.fold()
        msgs = [w["message"] for w in res.warnings if w["code"] == "invalid-event"]
        self.assertEqual(len(msgs), 2)

    def test_history_matches_patterns(self):
        d = self.sd.dir
        self.assertTrue(loader.history_matches(os.path.join(d, "history", "s99.json"),
                                               "history/s*.json", d))
        self.assertFalse(loader.history_matches(os.path.join(d, "history", "x", "s9.json"),
                                                "history/s*.json", d))
        self.assertTrue(loader.history_matches(os.path.join(d, "history", "creation.json"),
                                               "history/creation.json", d))
        self.assertFalse(loader.history_matches(os.path.join(d, "history", "other.json"),
                                                "history/creation.json", d))


class TestRulesValidation(unittest.TestCase):
    def _load(self, rules, shape=None):
        sd = SheetDir(rules, shape=shape)
        try:
            return sd.load()
        finally:
            sd.cleanup()

    def test_reserved_names_fatal(self):
        for rules in ({"classes": {"list": {}}},
                      {"traits": {"current": {}}},
                      {"derived": {"sum": "1"}},
                      {"lists": {"entry": {}}},
                      {"spans": {"value": {}}},
                      {"traits": {"if": {}}}):
            with self.assertRaises(SheetError, msg=rules):
                self._load(rules)

    def test_invalid_keys_fatal(self):
        for rules in ({"traits": {"Bad": {}}},
                      {"traits": {"a.b": {}}},               # 2 segments, no class a
                      {"classes": {"c": {}}, "traits": {"c.x.y": {}}},
                      {"traits": {"class": {}}}):            # python keyword
            with self.assertRaises(SheetError, msg=rules):
                self._load(rules)

    def test_derived_collision_fatal(self):
        with self.assertRaises(SheetError):
            self._load({"traits": {"a": {}}, "derived": {"a": "1"}})

    def test_bad_expression_fatal_at_load(self):
        with self.assertRaises(SheetError):
            self._load({"derived": {"d": "__import__('os')"}})
        with self.assertRaises(SheetError):
            self._load({"traits": {"a": {"max": "1 +"}}})

    def test_priority_length_must_match_groups(self):
        rules = {"classes": {"c": {"groups": ["g1", "g2"]}},
                 "creation": {"budgets": {"b": {"class": "c", "by": "group", "priority": [3, 2, 1]}}}}
        with self.assertRaises(SheetError):
            self._load(rules)

    def test_observed_groups_in_declared_order(self):
        rules = {"classes": {"c": {}},
                 "traits": {"c.a": {"group": "g2"}, "c.b": {"group": "g1"}, "c.d": {"group": "g2"}},
                 "creation": {"budgets": {"b": {"class": "c", "by": "group", "priority": [3, 2]}}}}
        sheet = self._load(rules)
        self.assertEqual(sheet.model.class_groups("c"), ["g2", "g1"])

    def test_shape_section_needs_exactly_one_kind(self):
        shape = {"groups": {"g": {"sections": {"s": {"fields": [], "list": "x"}}}}}
        with self.assertRaises(SheetError):
            self._load({}, shape)
        shape = {"groups": {"g": {"sections": {"s": {"fields": [{"kind": "scalar"}]}}}}}
        with self.assertRaises(SheetError):
            self._load({}, shape)

    def test_malformed_pack_json_fatal(self):
        sd = SheetDir({})
        try:
            with open(os.path.join(sd.pack, "rules.json"), "w", encoding="utf-8") as fh:
                fh.write("{oops")
            with self.assertRaises(SheetError):
                sd.load()
        finally:
            sd.cleanup()


if __name__ == "__main__":
    unittest.main()
