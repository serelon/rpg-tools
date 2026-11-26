"""The tick: flows, scarcity, diets, capacities, providers, transitions, rolls,
occurrences, checkpoints, guards and mounted subtrees. Synthetic packs only
(an invented mill-and-warren economy; no campaign data)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from sheet_helpers import SHEET_PY, write_json  # noqa: E402
from sheetlib import SheetError, load_sheet, resolve_full  # noqa: E402
from sheetlib.tick import Tick  # noqa: E402


def num(**kw):
    d = {"type": "number", "default": 0}
    d.update(kw)
    return d


class TickCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def p(self, rel):
        return os.path.join(self.root, rel)

    def pack(self, rules, name="rules"):
        rules = dict({"id": name}, **rules)
        write_json(self.p("pack/%s.json" % name), rules)
        write_json(self.p("pack/shape.json"), {"id": "s", "groups": {}})
        write_json(self.p("pack/catalog.json"), {})

    def sheet(self, name, events, rules="rules", patterns=None, **manifest):
        m = {"id": name, "name": name.title(), "rules": "../pack/%s.json" % rules,
             "shape": "../pack/shape.json", "catalog": "../pack/catalog.json",
             "history": patterns or ["history/s*.json", "history/tick-*.json"]}
        m.update(manifest)
        write_json(self.p("%s/sheet.json" % name), m)
        write_json(self.p("%s/history/s01.json" % name), {"source": "s01", "events": events})
        return self.p(name)

    def tick(self, path, tid, to, start=None, write=True, **kw):
        t = Tick(load_sheet(path), tid, to, start=start, **kw)
        rep = t.run()
        if write:
            t.write()
        return t, rep

    def values(self, path, at=None):
        doc, res = resolve_full(load_sheet(path), at=at)
        return doc["values"], doc, res

    def tickfile(self, name, tid):
        with open(self.p("%s/history/tick-%s.json" % (name, tid)), encoding="utf-8") as fh:
            return json.load(fh)["events"]


def start(*effects, date="1200-01-01"):
    return [{"date": date, "effects": list(effects)}]


class TestFlows(TickCase):
    def test_chain_priority_and_ledger_agreement(self):
        self.pack({"traits": {"grain": num(), "flour": num(), "bread": num()},
                   "flows": {"mill": {"priority": 1, "consume": {"grain": 10}, "produce": {"flour": 5}},
                             "bake": {"priority": 2, "consume": {"flour": 4}, "produce": {"bread": 4}}}})
        v = self.sheet("v", start({"set": "grain", "to": 35}))
        t, rep = self.tick(v, "t1", "1200-01-05", start="1200-01-01")
        # mill runs fully days 1-3, at half on day 4, not at all on day 5. Bake is served
        # after mill each day, so it bakes the same day's flour: 4, 4, 4, 4, then the 1.5 left
        vals, _, res = self.values(v)
        self.assertEqual(vals["grain"], 0)
        self.assertEqual(vals.get("flour", 0), 0)  # a stock never set that ends at 0 stays absent
        self.assertEqual(vals["bread"], 17.5)
        self.assertEqual(rep.stocks["v"]["bread"], 17.5)
        self.assertAlmostEqual(rep.flows["v"]["mill"]["short_days"], 0.5 + 1)
        self.assertEqual([w for w in res.warnings if w["code"] != "unknown-trait"], [])

    def test_scarcity_serves_priority_first_and_counts_short(self):
        self.pack({"traits": {"food": num(), "a_short": num(), "b_short": num(),
                              "fed_a": num(), "fed_b": num()},
                   "flows": {"a": {"priority": 1, "consume": {"food": 6}, "produce": {"fed_a": 1},
                                   "short": "a_short"},
                             "b": {"priority": 2, "consume": {"food": 6}, "produce": {"fed_b": 1},
                                   "short": "b_short"}}})
        v = self.sheet("v", start({"set": "food", "to": 9}))
        self.tick(v, "t1", "1200-01-01", start="1200-01-01")
        vals, _, _ = self.values(v)
        self.assertEqual(vals["fed_a"], 1)
        self.assertEqual(vals["fed_b"], 0.5)
        self.assertEqual(vals["b_short"], 0.5)
        self.assertEqual(vals.get("a_short", 0), 0)

    def test_overflow_lost_and_routed(self):
        self.pack({"traits": {"bin": num(max=10, overflow="spill"), "spill": num(max=3),
                              "jar": num(max=2)},
                   "flows": {"pour": {"produce": {"bin": 6, "jar": 5}}}})
        v = self.sheet("v", start({"set": "bin", "to": 0}))
        t, rep = self.tick(v, "t1", "1200-01-03", start="1200-01-01")
        vals, _, _ = self.values(v)
        self.assertEqual((vals["bin"], vals["spill"], vals["jar"]), (10, 3, 2))
        self.assertEqual(rep.overflow["v"]["bin"], 8)
        self.assertEqual(rep.overflow["v"]["jar"], 13)

    def test_diet_ranked_sources_reserve_and_substitution(self):
        self.pack({"traits": {"honey": num(), "pulp": num(), "short": num(), "subst": num()},
                   "flows": {
                       "special": {"priority": 1, "consume": {"food": {
                           "need": 4, "from": [["honey", 1], ["pulp", 2]]}}},
                       "common": {"priority": 2, "consume": {"food": {
                           "need": 5, "from": [["honey", 1, {"above": 6}], ["pulp", 1.5]]}},
                           "short": "short", "substituted": "subst"}}})
        v = self.sheet("v", start({"set": "honey", "to": 12}, {"set": "pulp", "to": 6}))
        self.tick(v, "t1", "1200-01-01", start="1200-01-01")
        vals, _, _ = self.values(v)
        # special eats 4 honey (8 left); common takes 2 honey above the 6 reserve,
        # then 3 more from pulp at 1.5 = 4.5 pulp
        self.assertEqual(vals["honey"], 6)
        self.assertEqual(vals["pulp"], 1.5)
        self.assertEqual(vals["subst"], 0.6)
        self.assertEqual(vals.get("short", 0), 0)

    def test_pooled_capacity_resets_daily(self):
        self.pack({"traits": {"hands": num(), "ore": num(), "ingot": num()},
                   "capacities": {"work": {"amount": "hands * 2"}},
                   "flows": {"smelt": {"consume": {"ore": 5, "work": 10},
                                       "produce": {"ingot": 1}}}})
        v = self.sheet("v", start({"set": "hands", "to": 3}, {"set": "ore", "to": 100}))
        self.tick(v, "t1", "1200-01-04", start="1200-01-01")
        vals, _, _ = self.values(v)
        self.assertEqual(vals["ingot"], 2.4)  # 6 work of 10, every day

    def test_active_gate_and_today(self):
        self.pack({"traits": {"x": num()}, "lists": {"tech": {}},
                   "flows": {"gated": {"active": "has('tech', 'wheel')", "produce": {"x": 1}},
                             "dated": {"active": "today() >= day('1200-01-03')",
                                       "produce": {"x": 10}}}})
        v = self.sheet("v", start({"set": "x", "to": 0}) + [
            {"date": "1200-01-02", "effects": [{"gain": "list.tech", "id": "wheel"}]}])
        self.tick(v, "t1", "1200-01-04", start="1200-01-01")
        vals, _, _ = self.values(v)
        self.assertEqual(vals["x"], 3 + 20)


class TestEntriesAndProviders(TickCase):
    RULES = {"traits": {"folk": num(integer=True)},
             "lists": {"brood": {}, "tutors": {}},
             "capacities": {"care": {"providers": "tutors", "amount": "entry.hours",
                                     "keys": "entry.knows"}},
             "flows": {"raise": {"for_each": "brood", "order": "entry.rank",
                                 "needs": {"care": {"key": "entry.craft", "amount": 4}},
                                 "produce": {"entry.progress": 1}}},
             "transitions": {"brood": {"done": {"at": "entry.span", "roll": "notable?",
                                                "effects": [{"add": "folk", "by_expr": "entry.n"},
                                                            {"retire": "list.brood", "id": "{id}"}]}}}}

    def tutors(self, *specs):
        return [{"gain": "list.tutors", "id": tid, "entry": {"hours": h, "knows": k}}
                for tid, h, k in specs]

    def brood(self, bid, craft, rank, span=5, n=3):
        return {"gain": "list.brood", "id": bid,
                "entry": {"craft": craft, "rank": rank, "span": span, "n": n, "progress": 0}}

    def test_tangle_least_flexible_first(self):
        self.pack(self.RULES)
        # 'y' is served first; greedy gives it to the specialist, so 'x' still finds ama
        v = self.sheet("v", start(*self.tutors(("ama", 4, {"x": 1, "y": 1}), ("bo", 4, {"y": 1})),
                                  self.brood("b1", "y", 1), self.brood("b2", "x", 2)))
        t, rep = self.tick(v, "t1", "1200-01-02", start="1200-01-01", write=False)
        self.assertEqual(rep.flows["v"]["raise"]["short_days"], 0)
        self.assertEqual(rep.hours["v"]["care"], {"bo": {"raise": 8}, "ama": {"raise": 8}})

    def test_partial_skill_slows_progress_and_transition_fires(self):
        self.pack(self.RULES)
        v = self.sheet("v", start({"set": "folk", "to": 10},
                                  *self.tutors(("ama", 4, {"x": 0.5})), self.brood("b1", "x", 1)))
        t, rep = self.tick(v, "t1", "1200-01-12", start="1200-01-01")
        self.assertEqual([tr["date"] for tr in rep.transitions], ["1200-01-10"])
        self.assertEqual(rep.owed[0]["roll"], "transition:done")
        vals, doc, _ = self.values(v)
        self.assertEqual(vals["folk"], 13)
        self.assertEqual(doc["lists"]["brood"], [])

    def test_sticky_keeps_pairing_daily_splits(self):
        rules = json.loads(json.dumps(self.RULES))
        rules["flows"]["raise"]["needs"]["care"]["amount"] = 6
        self.pack(rules)
        v = self.sheet("v", start(*self.tutors(("ama", 4, {"x": 1}), ("bo", 4, {"x": 1})),
                                  self.brood("b1", "x", 1, span=99)))
        t, rep = self.tick(v, "t1", "1200-01-03", start="1200-01-01")
        self.assertAlmostEqual(rep.flows["v"]["raise"]["short_days"], 1.0)  # 4 of 6, three days
        _, doc, _ = self.values(v)
        self.assertEqual(doc["lists"]["brood"][0]["fields"]["assigned_care"], "ama")  # tie → id
        self.assertEqual(len(rep.assignments), 1)
        rules["flows"]["raise"]["needs"]["care"]["assign"] = "daily"
        self.pack(rules)
        v2 = self.sheet("w", start(*self.tutors(("ama", 4, {"x": 1}), ("bo", 4, {"x": 1})),
                                   self.brood("b1", "x", 1, span=99)))
        t, rep = self.tick(v2, "t1", "1200-01-03", start="1200-01-01")
        self.assertEqual(rep.flows["w"]["raise"]["short_days"], 0)

    def test_sticky_reassigns_when_provider_leaves(self):
        self.pack(self.RULES)
        v = self.sheet("v", start(*self.tutors(("ama", 4, {"x": 1}), ("bo", 4, {"x": 1})),
                                  self.brood("b1", "x", 1, span=99)) + [
            {"date": "1200-01-03", "effects": [{"retire": "list.tutors", "id": "ama"}]}])
        t, rep = self.tick(v, "t1", "1200-01-04", start="1200-01-01")
        self.assertEqual([(a["from"], a["to"]) for a in rep.assignments],
                         [(None, "ama"), ("ama", "bo")])


class TestRollsOccurrencesCheckpoints(TickCase):
    def test_rolls_rise_once(self):
        self.pack({"traits": {"bad": num()},
                   "flows": {"rot": {"produce": {"bad": 1}}},
                   "rolls": {"plague": {"when": "bad >= 2 and bad < 4", "message": "roll plague"}}})
        v = self.sheet("v", start({"set": "bad", "to": 0}))
        t, rep = self.tick(v, "t1", "1200-01-10", start="1200-01-01")
        self.assertEqual([o["date"] for o in rep.owed], ["1200-01-02"])
        end = self.tickfile("v", "t1")[-1]
        self.assertEqual(end["tick"]["owed"][0]["roll"], "plague")

    def test_occurrence_params_and_bounds(self):
        self.pack({"traits": {"fuel": num(), "strain": num()},
                   "occurrences": {"jump": {"roll": "navigator roll", "flows": {
                       "burn": {"consume": {"fuel": "occ.distance * 2"},
                                "produce": {"strain": "occ.distance"}}}}},
                   "flows": {"rest": {"active": "strain > 0", "consume": {"strain": 1}}}})
        v = self.sheet("v", start({"set": "fuel", "to": 100}))
        t, rep = self.tick(v, "t1", "1200-01-10", start="1200-01-01",
                           occurrences=[("jump", "1200-01-02", {"distance": 9}),
                                        ("jump", "1200-01-05", {"distance": 3})])
        vals, _, _ = self.values(v)
        self.assertEqual(vals["fuel"], 76)
        # +9 on day 2 (rest starts day 3: strain read at dawn) → 7 by day 4; day 5 the jump
        # fires before flows (+3, rest −1) → 9; days 6-10 rest → 4
        self.assertEqual(vals["strain"], 4)
        self.assertEqual([o["roll"] for o in rep.owed], ["occurrence:jump"] * 2)
        for bad in ([("jump", "1199-12-31", {})], [("warp", "1200-01-02", {})]):
            with self.assertRaises(SheetError):
                Tick(load_sheet(v), "t9", "1200-01-10", start="1200-01-01", occurrences=bad)

    def test_month_checkpoints_and_mid_skip_resolution(self):
        self.pack({"traits": {"x": num()}, "flows": {"grow": {"produce": {"x": 1}}}})
        v = self.sheet("v", start({"set": "x", "to": 0}))
        self.tick(v, "t1", "1200-03-10", start="1200-01-01")
        evs = self.tickfile("v", "t1")
        self.assertEqual([e["date"] for e in evs], ["1200-01-31", "1200-02-29", "1200-03-10"])
        self.assertTrue(evs[-1]["tick"]["end"])
        self.assertEqual(self.values(v, at="1200-02-15")[0]["x"], 31)
        self.assertEqual(self.values(v)[0]["x"], 70)

    def test_integer_stock_carry_across_ticks(self):
        self.pack({"traits": {"folk": num(integer=True)},
                   "flows": {"births": {"produce": {"folk": 0.4}}}})
        v = self.sheet("v", start({"set": "folk", "to": 10}))
        self.tick(v, "t1", "1200-01-03", start="1200-01-01", checkpoint="skip")
        self.assertEqual(self.values(v)[0]["folk"], 11)  # 11.2 → 11, carry 0.2
        self.assertEqual(self.tickfile("v", "t1")[-1]["tick"]["carry"], {"folk": 0.2})
        self.tick(v, "t2", "1200-01-05", checkpoint="skip")  # continues from 01-04
        self.assertEqual(self.values(v)[0]["folk"], 12)  # 11.2 + 0.8 = 12.0


class TestGuardsAndLedger(TickCase):
    def setUp(self):
        super().setUp()
        self.pack({"traits": {"grain": num()}, "flows": {"grow": {"produce": {"grain": 2}}}})

    def test_ledger_events_inside_the_tick(self):
        v = self.sheet("v", start({"set": "grain", "to": 0}) + [
            {"date": "1200-01-03", "effects": [{"add": "grain", "by": -3}]},
            {"date": "1200-02-10", "effects": [{"add": "grain", "by": 100}]}])
        self.tick(v, "t1", "1200-01-05", start="1200-01-01")
        self.assertEqual(self.values(v, at="1200-01-31")[0]["grain"], 10 - 3)
        self.assertEqual(self.values(v)[0]["grain"], 107)  # the later event still folds after

    def test_overlap_default_start_and_reused_id(self):
        v = self.sheet("v", start({"set": "grain", "to": 0}))
        self.tick(v, "t1", "1200-01-05", start="1200-01-01")
        with self.assertRaises(SheetError):
            Tick(load_sheet(v), "t2", "1200-01-09", start="1200-01-04")
        with self.assertRaises(SheetError):
            Tick(load_sheet(v), "t1", "1200-01-09")
        t, _ = self.tick(v, "t2", "1200-01-09")
        self.assertEqual(t.cal.date(t.start), "1200-01-06")
        self.assertEqual(self.values(v)[0]["grain"], 18)
        with self.assertRaises(SheetError):
            Tick(load_sheet(self.sheet("w", start())), "t1", "1200-01-09")  # first needs --from

    def test_glob_guard_writes_nothing(self):
        v = self.sheet("v", start({"set": "grain", "to": 0}), patterns=["history/s*.json"])
        t = Tick(load_sheet(v), "t1", "1200-01-05", start="1200-01-01")
        t.run()
        with self.assertRaises(SheetError):
            t.write()
        self.assertFalse(os.path.exists(self.p("v/history/tick-t1.json")))


class TestDrift(TickCase):
    def test_replay_matches_then_drifts(self):
        from sheetlib.tick import check_ticks
        self.pack({"traits": {"fuel": num(), "x": num()},
                   "occurrences": {"hop": {"flows": {"b": {"consume": {"fuel": "occ.n"}}}}},
                   "flows": {"grow": {"produce": {"x": 1}}}})
        v = self.sheet("v", start({"set": "fuel", "to": 50}))
        self.tick(v, "t1", "1200-02-10", start="1200-01-01",
                  occurrences=[("hop", "1200-01-05", {"n": 7})])
        self.tick(v, "t2", "1200-03-01")
        self.assertEqual(check_ticks(load_sheet(v)), [])
        self.pack({"traits": {"fuel": num(), "x": num()},
                   "occurrences": {"hop": {"flows": {"b": {"consume": {"fuel": "occ.n"}}}}},
                   "flows": {"grow": {"produce": {"x": 2}}}})
        drift = check_ticks(load_sheet(v))
        self.assertEqual([d["ref"] for d in drift], ["tick-t1", "tick-t2"])


class TestEditBy(TickCase):
    def test_entry_field_deltas_compose(self):
        self.pack({"lists": {"bag": {}}})
        v = self.sheet("v", start({"gain": "list.bag", "id": "b", "entry": {"n": 2, "tag": "x"}}) + [
            {"date": "1200-02", "effects": [{"edit": "list.bag", "id": "b", "by": {"n": 3, "m": 1}}]},
            {"date": "1200-01-15", "effects": [{"edit": "list.bag", "id": "b", "by": {"n": 10}}]},
            {"date": "1200-03", "effects": [{"edit": "list.bag", "id": "b", "by": {"tag": 1}},
                                            {"edit": "attr", "by": {"n": 1}}]}])
        _, doc, res = self.values(v)
        self.assertEqual(doc["lists"]["bag"][0]["fields"], {"n": 15, "tag": "x", "m": 1})
        self.assertEqual([w["code"] for w in res.warnings], ["invalid-event", "invalid-event"])


class TestMountedTree(TickCase):
    def test_parent_reads_and_writes_children(self):
        self.pack({"traits": {"fuel": num(), "used": num()},
                   "flows": {"idle": {"consume": {"fuel": 1}, "produce": {"used": 1}}}},
                  name="child")
        self.pack({"traits": {"depot": num(), "fleet_fuel": num()},
                   "mounts": {"ship": {}},
                   "derived": {"total": "sum(mounts.ship[*].fuel)"},
                   "flows": {"refuel": {"priority": 1, "for_each": "mounts.ship",
                                        "where": "entry.fuel < 5",
                                        "consume": {"depot": 3}, "produce": {"child.fuel": 3}},
                             "census": {"priority": 2, "consume": {"fleet_fuel": "fleet_fuel"},
                                        "produce": {"fleet_fuel": "total"}},
                             "gift": {"priority": 3, "produce": {"mount.ship.b.fuel": 0.5}}}})
        self.sheet("a", start({"set": "fuel", "to": 6}), rules="child")
        self.sheet("b", start({"set": "fuel", "to": 2}), rules="child")
        f = self.sheet("fleet", start({"set": "depot", "to": 30},
                                      {"mount": "ship", "id": "a", "ref": "../a"},
                                      {"mount": "ship", "id": "b", "ref": "../b"}))
        t, rep = self.tick(f, "t1", "1200-01-04", start="1200-01-01")
        self.assertEqual(sorted(os.path.basename(os.path.dirname(os.path.dirname(p)))
                                for p in rep.files), ["a", "b", "fleet"])
        a, _, _ = self.values(self.p("a"))
        b, _, _ = self.values(self.p("b"))
        fl, doc, _ = self.values(f)
        # dawn reads: b refuels every day (2→ +3+0.5−1 = 4.5 → 7 ...), a only once it dips
        self.assertEqual(a["used"], 4)
        self.assertEqual(fl["depot"] + 3 * (rep.flows["fleet"]["refuel"]["runs"]), 30)
        self.assertEqual(doc["derived"]["total"], a["fuel"] + b["fuel"])
        self.assertEqual(rep.stocks["b"]["fuel"], b["fuel"])


class TestTreeEdges(TickCase):
    def crew_pack(self):
        self.pack({"traits": {"strain": num(), "x": num()},
                   "flows": {"live": {"produce": {"x": 1}}}}, name="crew")
        self.pack({"traits": {"x": num()}, "mounts": {"crew": {}}}, name="ship")

    def test_writes_two_levels_down(self):
        self.crew_pack()
        self.pack({"traits": {"exotic": num()}, "mounts": {"ship": {}},
                   "occurrences": {"jump": {"flows": {"burn": {
                       "consume": {"exotic": 5},
                       "produce": {"mount.ship.s1.mount.crew.nav.strain": "occ.d"}}}}}})
        self.sheet("nav", start(), rules="crew")
        self.sheet("s1", start({"mount": "crew", "id": "nav", "ref": "../nav"}), rules="ship")
        f = self.sheet("fleet", start({"set": "exotic", "to": 20},
                                      {"mount": "ship", "id": "s1", "ref": "../s1"}))
        self.tick(f, "t1", "1200-01-03", start="1200-01-01",
                  occurrences=[("jump", "1200-01-02", {"d": 9})])
        nav, _, _ = self.values(self.p("nav"))
        self.assertEqual((nav["strain"], nav["x"]), (9, 3))
        self.assertEqual(self.values(f)[0]["exotic"], 15)
        self.assertEqual(self.values(self.p("s1"))[0].get("strain"), None)

    def test_one_sim_per_sheet_and_unmounted_children_rest(self):
        self.crew_pack()
        self.pack({"mounts": {"ship": {}}})
        self.sheet("nav", start(), rules="crew")
        self.sheet("old", start({"set": "x", "to": 0}), rules="crew")
        self.sheet("a", start({"mount": "crew", "id": "nav", "ref": "../nav"}) + [
            {"date": "1200-01-04", "effects": [{"unmount": "crew", "id": "nav"}]}], rules="ship")
        self.sheet("b", [{"date": "1200-01-04", "effects": [
            {"mount": "crew", "id": "nav", "ref": "../nav"}]}], rules="ship")
        f = self.sheet("fleet", start({"mount": "ship", "id": "a", "ref": "../a"},
                                      {"mount": "ship", "id": "b", "ref": "../b"},
                                      {"mount": "ship", "id": "o", "ref": "../old"}) + [
            {"date": "1200-01-03", "effects": [{"unmount": "ship", "id": "o"}]}])
        t, rep = self.tick(f, "t1", "1200-01-06", start="1200-01-01")
        self.assertEqual(self.values(self.p("nav"))[0]["x"], 6)  # once a day, through the move
        self.assertEqual(self.values(self.p("old"))[0]["x"], 2)  # ticks only while mounted
        self.assertEqual(len([p for p in rep.files if "/nav/" in p]), 1)

    def test_nonzero_defaults_and_rating_min(self):
        self.pack({"traits": {"fuel": num(default=10), "morale": {"min": 1, "max": 9}},
                   "flows": {"up": {"produce": {"fuel": 1, "morale": 1}}}})
        v = self.sheet("v", start())
        self.tick(v, "t1", "1200-01-03", start="1200-01-01")
        vals, _, res = self.values(v)
        self.assertEqual((vals["fuel"], vals["morale"]), (13, 4))
        self.assertNotIn("no-cost", [w["code"] for w in res.warnings])

    def test_currency_stock_is_not_a_purchase(self):
        self.pack({"currency": "credits", "traits": {"credits": num(), "x": {"cost": {"raise": 5}}},
                   "flows": {"burn": {"consume": {"credits": 30}}}})
        v = self.sheet("v", start({"set": "credits", "to": 100}))
        self.tick(v, "t1", "1200-01-02", start="1200-01-01")
        vals, _, res = self.values(v)
        self.assertEqual(vals["credits"], 40)
        self.assertEqual([w for w in res.warnings if w["code"] in ("cost-mismatch", "no-cost")], [])


class TestChainedListFields(TickCase):
    RULES = {"traits": {"adults": num()},
             "lists": {"cohorts": {"fields": {
                 "age": "today() - day(entry.laid)",
                 "eff": "entry.age - entry.stretch",
                 "stage": "if(entry.eff < 3, 'egg', if(entry.eff < 6, 'grub', 'adult'))",
                 "ahead": "entry.later",
                 "later": "1"}}}}

    def test_fields_see_earlier_fields(self):
        rules = dict(self.RULES, derived={"stages": "list.cohorts[*].stage"})
        self.pack(rules)
        v = self.sheet("v", start({"gain": "list.cohorts", "id": "a",
                                   "entry": {"laid": "1200-01-01", "stretch": 1}}) + [
            {"date": "1200-01-05", "effects": [{"set": "adults", "to": 0}]}])
        _, doc, res = self.values(v)
        f = doc["lists"]["cohorts"][0]["fields"]
        self.assertEqual((f["age"], f["eff"], f["stage"]), (4, 3, "grub"))
        self.assertIsNone(f["ahead"])  # a later field is not visible yet
        self.assertEqual(f["later"], 1)
        self.assertEqual(doc["derived"]["stages"], ["grub"])
        self.assertEqual([w["code"] for w in res.warnings], [])

    def test_transitions_and_flows_see_computed_fields(self):
        self.pack({"traits": {"adults": num()},
                   "lists": {"cohorts": {"fields": {"age": "today() - day(entry.laid)",
                                                    "due": "entry.span - entry.age"}}},
                   "flows": {"grow": {"for_each": "cohorts", "where": "entry.due > 0",
                                      "produce": {"entry.progress": 1}}},
                   "transitions": {"cohorts": {"done": {
                       "at": "entry.age + entry.due",
                       "effects": [{"add": "adults", "by_expr": "entry.n"},
                                   {"retire": "list.cohorts", "id": "{id}"}]}}}})
        v = self.sheet("v", start({"gain": "list.cohorts", "id": "a", "entry": {
            "laid": "1200-01-01", "span": 4, "n": 5, "progress": 0}}))
        t, rep = self.tick(v, "t1", "1200-01-08", start="1200-01-01")
        self.assertEqual([tr["date"] for tr in rep.transitions], ["1200-01-04"])
        self.assertEqual(self.values(v)[0]["adults"], 5)


class TestLensPrivacy(TickCase):
    def test_child_gm_only_trait_hidden_in_player_lens(self):
        self.pack({"traits": {"fuel": num(), "secret": num(gm_only=True)}}, name="child")
        write_json(self.p("pack/lens.json"), {"id": "l", "groups": {"g": {"sections": {"pods": {
            "mounts": "pod", "fields": [{"key": "fuel"}, {"key": "secret"}]}}}}})
        self.pack({"mounts": {"pod": {}}})
        self.sheet("c", start({"set": "fuel", "to": 1}, {"set": "secret", "to": 7}), rules="child")
        f = self.sheet("f", start({"mount": "pod", "id": "c", "ref": "../c"}))
        m = json.load(open(self.p("f/sheet.json")))
        m["shape"] = "../pack/lens.json"
        write_json(self.p("f/sheet.json"), m)
        for view, keys in (("gm", ["fuel", "secret"]), ("player", ["fuel"])):
            doc, _ = resolve_full(load_sheet(f), view=view)
            row = doc["groups"][0]["sections"][0]["rows"][0]
            self.assertEqual([x["key"] for x in row["fields"]], keys, view)


class TestCli(TickCase):
    def test_dry_run_and_json(self):
        self.pack({"traits": {"grain": num()}, "flows": {"grow": {"produce": {"grain": 2}}}})
        v = self.sheet("v", start({"set": "grain", "to": 0}))
        p = subprocess.run([sys.executable, SHEET_PY, "tick", v, "--id", "t1", "--from",
                            "1200-01-01", "--to", "1200-01-03", "--dry-run", "--json"],
                           capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = json.loads(p.stdout)
        self.assertTrue(rep["dry_run"])
        self.assertEqual(rep["stocks"]["v"]["grain"], 6)
        self.assertFalse(os.path.exists(self.p("v/history/tick-t1.json")))
        p = subprocess.run([sys.executable, SHEET_PY, "tick", v, "--id", "t1", "--to",
                            "1200-01-03"], capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        self.assertIn(b"--from", p.stderr)


if __name__ == "__main__":
    unittest.main()
