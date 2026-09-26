"""Tests for the fold (spec S5 effects, S6 ordering, S7 algorithm)."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import (BASE_CATALOG, BASE_RULES, SheetDir, codes, creation_event,  # noqa: E402
                           ev, warnings_of)


def rules(**patch):
    r = copy.deepcopy(BASE_RULES)
    for k, v in patch.items():
        r[k] = v
    return r


class FoldCase(unittest.TestCase):
    rules = BASE_RULES

    def sheet(self, history, rules=None, catalog=None, patterns=None):
        sd = SheetDir(rules or self.rules, catalog=catalog or BASE_CATALOG, history=history,
                      patterns=patterns)
        self.addCleanup(sd.cleanup)
        return sd

    def fold(self, history, at=None, **kw):
        return self.sheet(history, **kw).fold(at=at)


class TestOps(FoldCase):
    def test_set_every_type(self):
        res = self.fold({"creation": [creation_event()], "s01": [ev(
            "1101",
            {"set": "tier", "to": "mid"},
            {"set": "mentor", "to": {"ref": "../other/sheet.json", "name": "Old One"}},
            {"set": "bond", "to": {"who": "a friend", "grip": 1}},
            {"set": "bond.mood", "to": "warm"},
            {"set": "level", "to": 2.5},
            free="test")]})
        v = res.astate.values
        self.assertEqual(v["tier"], "mid")
        self.assertEqual(v["mentor"], {"ref": "../other/sheet.json", "name": "Old One"})
        self.assertEqual(v["bond"], {"who": "a friend", "grip": 1, "mood": "warm"})
        self.assertEqual(v["level"], 2.5)
        self.assertEqual(v["kind"], "k1")

    def test_add_rating_enum_number_part(self):
        res = self.fold({"creation": [creation_event()], "s01": [ev(
            "1101",
            {"add": "attr.one"},            # by defaults to 1
            {"add": "tier", "by": 2},
            {"add": "level", "by": 1},
            {"add": "bond.grip", "by": 2},
            free="test")]})
        v = res.astate.values
        self.assertEqual(v["attr.one"], 3)
        self.assertEqual(v["tier"], "high")
        self.assertEqual(v["level"], 2)
        self.assertEqual(v["bond"]["grip"], 2)
        self.assertEqual(v["bond"]["mood"], "cold")  # part default
        self.assertNotIn("cost-mismatch", codes(res))

    def test_add_from_absent_starts_at_default(self):
        res = self.fold({"s01": [ev("1101", {"add": "virtue.gamma", "by": 2}, free="x")]})
        self.assertEqual(res.astate.values["virtue.gamma"], 3)  # min 1 + 2

    def test_trait_meta_on_set_and_edit(self):
        res = self.fold({"s01": [
            ev("1101", {"set": "knack.weaving", "to": 1, "name": "Basket Weaving", "group": "craft"},
               free="x"),
            ev("1102", {"edit": "knack.weaving", "fields": {"note": "learned from a neighbour",
                                                            "name": None}})]})
        meta = res.astate.meta["knack.weaving"]
        self.assertEqual(meta, {"group": "craft", "note": "learned from a neighbour"})
        self.assertEqual(res.astate.refs["knack.weaving"], ["s01#1", "s01#2"])

    def test_edit_bad_field_invalid(self):
        res = self.fold({"s01": [ev("1101", {"set": "level", "to": 1}),
                                 ev("1102", {"edit": "level", "fields": {"value": 3}})]})
        self.assertIn("invalid-event", codes(res))

    def test_list_gain_edit_retire(self):
        res = self.fold({"s01": [
            ev("1101", {"gain": "list.marks", "id": "m1", "entry": {"name": "Mark", "text": "t"}}),
            ev("1102", {"edit": "list.marks", "id": "m1", "fields": {"depth": 2, "text": None}}),
            ev("1103", {"gain": "list.marks", "id": "m2", "entry": {"name": "Other"}}),
            ev("1104", {"retire": "list.marks", "id": "m2"})]})
        live = res.astate.live_entries("marks")
        self.assertEqual([e.data for e in live], [{"id": "m1", "name": "Mark", "depth": 2}])
        self.assertEqual(live[0].refs, ["s01#1", "s01#2"])
        self.assertTrue(res.astate.lists["marks"]["m2"].retired)

    def test_spans(self):
        res = self.fold({"s01": [
            ev("1140", {"start": "sleep", "id": "t1", "note": "under the hill"}),
            ev("1165", {"end": "sleep", "id": "t1", "note": "woke hungry"}),
            ev("1170", {"start": "sleep", "id": "t2"})]}, at="1180")
        sp = res.astate.spans
        self.assertEqual((sp["t1"].start, sp["t1"].end), ("1140", "1165"))
        self.assertEqual(sp["t1"].note, "under the hill woke hungry")
        self.assertEqual(sp["t1"].refs, ["s01#1", "s01#2"])
        self.assertIsNone(sp["t2"].end)
        self.assertEqual(sp["t1"].name, "Sleep")


class TestOrdering(FoldCase):
    def test_date_then_seq_then_file_then_index(self):
        res = self.fold({
            "s01": [ev("1100-05", {"set": "level", "to": 1}),
                    ev("1100-05", {"set": "level", "to": 2}, seq=2),
                    ev("1100-05", {"set": "level", "to": 3}, seq=1)],
            "s02": [ev("1100-05", {"set": "level", "to": 4}),
                    ev("1100", {"set": "level", "to": 5})]})
        order = [e.ref for e in res.events]
        # 1100 (vaguer) first; then seq 0: s01#1, s02#1 (file order); seq 1; seq 2
        self.assertEqual(order, ["s02#2", "s01#1", "s02#1", "s01#3", "s01#2"])
        self.assertEqual(res.astate.values["level"], 2)

    def test_folds_by_date_not_record_order(self):
        res = self.fold({"s01": [ev("1200", {"set": "level", "to": 3})],
                         "s02": [ev("1100", {"set": "level", "to": 1})]})
        self.assertEqual(res.astate.values["level"], 3)

    def test_at(self):
        sd = self.sheet({"s01": [ev("1130", {"set": "level", "to": 1}),
                                 ev("1130-10-31", {"set": "level", "to": 2}),
                                 ev("1131", {"set": "level", "to": 3})]})
        self.assertEqual(sd.fold(at="1130").astate.values["level"], 2)
        self.assertEqual(sd.fold(at="1130-10").astate.values["level"], 2)
        self.assertEqual(sd.fold(at="1130-09").astate.values["level"], 1)
        self.assertEqual(sd.fold().astate.values["level"], 3)
        self.assertNotIn("level", sd.fold(at="1129").astate.values)


class TestLifecycle(FoldCase):
    def test_retire_then_touch_reappears_fresh(self):
        res = self.fold({"s01": [
            ev("1101", {"set": "virtue.gamma", "to": 4}),
            ev("1102", {"retire": "virtue.gamma"}),
            ev("1103", {"add": "virtue.gamma", "by": 1}, free="x")]})
        self.assertEqual(res.astate.values["virtue.gamma"], 2)  # default 1 + 1, not 5
        self.assertEqual(res.astate.refs["virtue.gamma"], ["s01#1", "s01#2", "s01#3"])

    def test_retired_trait_not_in_state_values(self):
        res = self.fold({"s01": [ev("1101", {"set": "level", "to": 1}),
                                 ev("1102", {"retire": "level"})]})
        self.assertNotIn("level", res.astate.values)
        self.assertIn("level", res.astate.retired)

    def test_gain_revives_retired_with_new_entry_only(self):
        res = self.fold({"s01": [
            ev("1101", {"gain": "list.marks", "id": "m", "entry": {"name": "Old", "extra": 1}}),
            ev("1102", {"retire": "list.marks", "id": "m"}),
            ev("1103", {"gain": "list.marks", "id": "m", "entry": {"name": "New"}})]})
        e = res.astate.lists["marks"]["m"]
        self.assertFalse(e.retired)
        self.assertEqual(e.data, {"id": "m", "name": "New"})
        self.assertEqual(e.refs, ["s01#1", "s01#2", "s01#3"])

    def test_gain_of_live_id_invalid(self):
        res = self.fold({"s01": [ev("1101", {"gain": "list.marks", "id": "m", "entry": {"name": "A"}}),
                                 ev("1102", {"gain": "list.marks", "id": "m", "entry": {"name": "B"}})]})
        self.assertEqual(codes(res), ["invalid-event"])
        self.assertEqual(res.astate.lists["marks"]["m"].data["name"], "A")

    def test_edit_retire_missing_or_retired_invalid(self):
        res = self.fold({"s01": [
            ev("1101", {"edit": "level", "fields": {"note": "x"}}),
            ev("1102", {"retire": "level"}),
            ev("1103", {"edit": "list.marks", "id": "nope", "fields": {"a": 1}}),
            ev("1104", {"retire": "list.marks", "id": "nope"}),
            ev("1105", {"set": "level", "to": 1}),
            ev("1106", {"retire": "level"}),
            ev("1107", {"retire": "level"}),
            ev("1108", {"edit": "level", "fields": {"note": "x"}})]})
        self.assertEqual(codes(res), ["invalid-event"] * 6)

    def test_span_id_reuse_and_end_on_closed(self):
        res = self.fold({"s01": [
            ev("1101", {"start": "sleep", "id": "t"}),
            ev("1102", {"end": "sleep", "id": "t"}),
            ev("1103", {"start": "sleep", "id": "t"}),
            ev("1104", {"end": "sleep", "id": "t"}),
            ev("1105", {"end": "sleep", "id": "never"})]})
        self.assertEqual(codes(res), ["invalid-event"] * 3)
        self.assertEqual(res.astate.spans["t"].end, "1102")


class TestAnchors(FoldCase):
    def test_at_least_lifts_and_is_unsatisfied(self):
        res = self.fold({"s01": [ev("1101", {"set": "attr.two", "to": 2}, free="x")],
                         "branch-1200": [ev("1200", {"anchor": "attr.two", "id": "a1", "at_least": 4})]})
        self.assertEqual(res.state.values["attr.two"], 2)       # unanchored untouched
        self.assertEqual(res.astate.values["attr.two"], 4)      # anchored floor
        self.assertEqual(res.astate.refs["attr.two"], ["s01#1", "branch-1200#1"])
        a = res.anchors[0]
        self.assertFalse(a["satisfied"])
        self.assertEqual(a["folded"], 2)
        self.assertEqual(codes(res), ["unsatisfied-anchor"])

    def test_at_least_satisfied_does_not_lift(self):
        res = self.fold({"s01": [ev("1101", {"set": "attr.two", "to": 5}, free="x")],
                         "branch-1200": [ev("1200", {"anchor": "attr.two", "id": "a1", "at_least": 4})]})
        self.assertEqual(res.astate.values["attr.two"], 5)
        self.assertTrue(res.anchors[0]["satisfied"])
        self.assertEqual(res.astate.refs["attr.two"], ["s01#1"])
        self.assertEqual(codes(res), [])

    def test_at_most_ceiling(self):
        res = self.fold({"s01": [ev("1101", {"set": "level", "to": 3})],
                         "branch-1200": [ev("1200", {"anchor": "level", "id": "g", "at_most": 2})]})
        self.assertEqual(res.astate.values["level"], 2)
        self.assertFalse(res.anchors[0]["satisfied"])

    def test_composition(self):
        res = self.fold({"s01": [ev("1101", {"set": "attr.two", "to": 1})],
                         "branch-1200": [ev("1200",
                                            {"anchor": "attr.two", "id": "a", "at_least": 3},
                                            {"anchor": "attr.two", "id": "b", "at_least": 4},
                                            {"anchor": "attr.two", "id": "c", "at_most": 3})]})
        # max(1, 3, 4) = 4, then min(4, 3) = 3
        self.assertEqual(res.astate.values["attr.two"], 3)

    def test_is_and_has(self):
        res = self.fold({"s01": [ev("1101", {"set": "path", "to": "first"}),
                                 ev("1102", {"gain": "list.marks", "id": "m", "entry": {}})],
                         "branch-1200": [ev("1200",
                                            {"anchor": "path", "id": "p", "is": "second"},
                                            {"anchor": "tier", "id": "t", "is": "high"},
                                            {"anchor": "list.marks", "id": "h1", "has": "m"},
                                            {"anchor": "list.marks", "id": "h2", "has": "zz"})]})
        self.assertEqual(res.astate.values["path"], "second")
        self.assertEqual(res.astate.values["tier"], "high")
        sat = {a["id"]: a["satisfied"] for a in res.anchors}
        self.assertEqual(sat, {"p": False, "t": False, "h1": True, "h2": False})
        self.assertNotIn("zz", res.astate.lists["marks"])  # has never synthesises

    def test_absent_key_present_only_if_lifted(self):
        res = self.fold({"branch-1200": [ev("1200",
                                            {"anchor": "virtue.gamma", "id": "a", "at_least": 1},
                                            {"anchor": "virtue.delta", "id": "b", "at_least": 3})]})
        self.assertNotIn("virtue.gamma", res.astate.values)  # default 1 already meets it
        self.assertEqual(res.astate.values["virtue.delta"], 3)
        self.assertEqual(res.astate.refs["virtue.delta"], ["branch-1200#1"])
        sat = {a["id"]: a["satisfied"] for a in res.anchors}
        self.assertEqual(sat, {"a": True, "b": False})

    def test_enum_at_least_by_index(self):
        res = self.fold({"s01": [ev("1101", {"set": "tier", "to": "low"})],
                         "branch-1200": [ev("1200", {"anchor": "tier", "id": "t", "at_least": 1})]})
        self.assertEqual(res.astate.values["tier"], "mid")

    def test_satisfies_provenance(self):
        res = self.fold({"s01": [ev("1150", {"set": "attr.two", "to": 4}, satisfies="a1", free="x")],
                         "branch-1200": [ev("1200", {"anchor": "attr.two", "id": "a1", "at_least": 4})]})
        self.assertEqual(res.anchors[0]["satisfied_by"], ["s01#1"])
        self.assertTrue(res.anchors[0]["satisfied"])

    def test_invalid_anchor_target(self):
        res = self.fold({"s01": [ev("1101", {"set": "path", "to": "first"})],
                         "branch-1200": [ev("1200",
                                            {"anchor": "path", "id": "x", "at_least": 3},
                                            {"anchor": "level", "id": "y", "is": 3})]})
        self.assertEqual(res.astate.values["path"], "first")
        self.assertNotIn("level", res.astate.values)
        self.assertEqual(codes(res).count("unknown-trait"), 2)
        self.assertEqual(codes(res).count("unsatisfied-anchor"), 2)

    def test_anchor_does_not_change_costs(self):
        res = self.fold({"creation": [creation_event()],
                         "branch-1100": [ev("1100-06", {"anchor": "attr.one", "id": "a", "at_least": 4})],
                         "s01": [ev("1101", {"add": "attr.one"}, {"add": "xp", "by": -8})]},
                        patterns=["history/creation.json", "history/s*.json", "history/branch-*.json"])
        # raise 2→3 against the unanchored running state: current*4 = 8
        self.assertEqual(res.expected["s01#1"], {"xp": 8})
        self.assertNotIn("cost-mismatch", codes(res))


class TestWarnings(FoldCase):
    def test_before_creation(self):
        res = self.fold({"creation": [creation_event("1100")],
                         "s01": [ev("1099", {"set": "level", "to": 1})]})
        w = warnings_of(res, "before-creation")
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["ref"], "s01#1")

    def test_inactive_trait_at_event_and_sweep(self):
        sd = self.sheet({"creation": [creation_event("1100")],
                         "s01": [ev("1110", {"set": "path", "to": "second"})],
                         "s02": [ev("1120", {"retire": "virtue.alpha"}, {"retire": "virtue.beta"},
                                    {"set": "virtue.gamma", "to": 2}, {"set": "virtue.delta", "to": 1})]})
        res = sd.fold(at="1115")
        ev_level = [w for w in warnings_of(res, "inactive-trait") if "ref" in w]
        self.assertEqual(len(ev_level), 1)
        self.assertEqual(ev_level[0]["ref"], "s01#1")
        self.assertNotIn("key", ev_level[0])
        self.assertIn("alpha, beta now inactive", ev_level[0]["message"])
        self.assertIn("gamma, delta need explicit values", ev_level[0]["message"])
        swept = sorted(w["key"] for w in warnings_of(res, "inactive-trait") if "key" in w)
        # beta sits at its default (1) and still warns
        self.assertEqual(swept, ["virtue.alpha", "virtue.beta"])
        # nothing converted
        self.assertEqual(res.astate.values["virtue.alpha"], 2)
        self.assertNotIn("virtue.gamma", res.astate.values)
        later = sd.fold()
        self.assertEqual([w for w in warnings_of(later, "inactive-trait") if "key" in w], [])
        ev_level = [w for w in warnings_of(later, "inactive-trait") if "ref" in w]
        self.assertEqual([w["ref"] for w in ev_level], ["s01#1"])

    def test_invalid_events(self):
        res = self.fold({"s01": [
            ev("1130-13", {"set": "level", "to": 1}),               # bad date → skipped
            {"date": "1101"},                                        # no effects
            ev("1102", {"set": "level", "to": 1, "add": "level"}),   # two ops
            ev("1103", {"add": "path", "by": 1}),                    # add on text
            ev("1104", {"set": "tier", "to": "ultra"}),              # enum value
            ev("1105", {"set": "attr.one.x", "to": 1}),              # 3 segments, not compound
            ev("1106", {"set": "level", "to": 2}, kind="weird"),
            ev("1107", {"set": "attr.one", "to": "high"})]})
        self.assertEqual(codes(res), ["invalid-event"] * 8)
        self.assertEqual(res.astate.values, {"level": 2})

    def test_bad_effect_skipped_rest_applies(self):
        res = self.fold({"s01": [ev("1101", {"bogus": 1}, {"set": "level", "to": 2})]})
        self.assertEqual(res.astate.values["level"], 2)
        self.assertEqual(codes(res), ["invalid-event"])

    def test_unknown_trait(self):
        res = self.fold({"s01": [ev("1101",
                                    {"set": "mystery", "to": 2},
                                    {"set": "attr.nine", "to": 2},
                                    {"set": "power.zap", "to": 1},
                                    {"set": "knack.anything", "to": 1},
                                    {"gain": "list.nolist", "id": "x", "entry": {}},
                                    {"start": "nokind", "id": "s"},
                                    {"anchor": "undeclared", "id": "a", "at_least": 1},
                                    free="x")]})
        uk = [w["key"] for w in warnings_of(res, "unknown-trait")]
        self.assertEqual(uk, ["mystery", "attr.nine", "power.zap", "list.nolist", "nokind",
                              "undeclared"])
        # the effects still apply
        self.assertEqual(res.astate.values["mystery"], 2)
        self.assertIn("x", res.astate.lists["nolist"])
        self.assertIn("s", res.astate.spans)

    def test_over_cap_rating_and_enum_clamp_and_negative_pool(self):
        res = self.fold({"s01": [
            ev("1101", {"set": "attr.one", "to": 6}),
            ev("1102", {"add": "tier", "by": 5}, free="x"),
            ev("1103", {"set": "xp", "to": 2}, {"add": "xp", "by": -5})]})
        c = codes(res)
        self.assertEqual(c.count("over-cap"), 2)
        self.assertEqual(res.astate.values["tier"], "high")
        self.assertIn("negative-pool", c)
        self.assertEqual([w["key"] for w in warnings_of(res, "over-cap")], ["attr.one", "tier"])

    def test_over_cap_uses_derived_max(self):
        res = self.fold({"s01": [ev("1101", {"set": "level", "to": 1},
                                    {"set": "power.glow", "to": 4})]})
        self.assertEqual([w["key"] for w in warnings_of(res, "over-cap")], ["power.glow"])

    def test_list_over_cap_from_dropped_derived_cap(self):
        res = self.fold({"s01": [
            ev("1101", {"set": "level", "to": 3},
               {"gain": "list.items", "id": "a", "entry": {}},
               {"gain": "list.items", "id": "b", "entry": {}},
               {"gain": "list.items", "id": "c", "entry": {}}),
            ev("1102", {"set": "level", "to": 1})]})
        w = warnings_of(res, "over-cap")
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["key"], "list.items")
        self.assertNotIn("ref", w[0])  # caught by the final sweep

    def test_list_over_cap_per_event_not_duplicated(self):
        res = self.fold({"s01": [ev("1101", {"set": "level", "to": 1},
                                    {"gain": "list.items", "id": "a", "entry": {}},
                                    {"gain": "list.items", "id": "b", "entry": {}},
                                    {"gain": "list.items", "id": "c", "entry": {}})]})
        w = warnings_of(res, "over-cap")
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["ref"], "s01#1")

    def test_reserved_modifiers_notice(self):
        res = self.fold({}, rules=rules(modifiers={"x": 1}, tallies={}))
        self.assertEqual([n["code"] for n in res.notices], ["reserved-unimplemented"])
        self.assertEqual(codes(res), [])

    def test_notices(self):
        r = rules(notices={
            "high-level": {"scope": "sheet", "when": "level >= 3", "message": "High"},
            "long-sleep": {"scope": "span:sleep", "when": "span_years >= 10 and not span_note",
                           "message": "Long sleep"},
            "open-sleep": {"scope": "span:sleep", "when": "span_open", "message": "Asleep"}})
        res = self.fold({"s01": [
            ev("1100", {"set": "level", "to": 3}),
            ev("1110", {"start": "sleep", "id": "t1"}),
            ev("1125", {"end": "sleep", "id": "t1"}),
            ev("1130", {"start": "sleep", "id": "t2", "note": "noted"}),
            ev("1150", {"end": "sleep", "id": "t2"}),
            ev("1160", {"start": "sleep", "id": "t3"})]}, rules=r)
        got = [(n["code"], n.get("span")) for n in res.notices]
        self.assertEqual(got, [("high-level", None), ("long-sleep", "t1"), ("open-sleep", "t3")])


if __name__ == "__main__":
    unittest.main()
