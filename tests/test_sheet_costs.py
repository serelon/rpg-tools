"""Tests for costs, payments and creation budgets (spec S5, S7 steps 5 and 8)."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import (BASE_CATALOG, BASE_RULES, SheetDir, codes, creation_event,  # noqa: E402
                           ev, warnings_of)
from sheetlib import quote  # noqa: E402


def cost_rules():
    r = copy.deepcopy(BASE_RULES)
    r["lists"]["boons"] = {"name": "Boons", "cost": "entry.price", "currency": "karma"}
    r["traits"]["karma"] = {"type": "number", "min": 0}
    return r


class CostCase(unittest.TestCase):
    def fold(self, history, rules=None, at=None):
        sd = SheetDir(rules or cost_rules(), catalog=BASE_CATALOG, history=history)
        self.addCleanup(sd.cleanup)
        self.sd = sd
        return sd.fold(at=at)


class TestPricing(CostCase):
    def test_new_vs_raise_in_and_out_of_clan(self):
        res = self.fold({"creation": [creation_event()], "s01": [
            ev("1101", {"add": "power.glow"}, {"add": "xp", "by": -10}),
            ev("1102", {"add": "power.glow"}, {"add": "xp", "by": -5}),
            ev("1103", {"add": "power.drift"}, {"add": "xp", "by": -10}),
            ev("1104", {"add": "power.drift"}, {"add": "xp", "by": -7})]})
        self.assertEqual(res.expected["s01#1"], {"xp": 10})
        self.assertEqual(res.expected["s01#2"], {"xp": 5})
        self.assertEqual(res.expected["s01#4"], {"xp": 7})
        self.assertEqual(codes(res), ["negative-pool"] * 4)  # xp started at 0: payment → negative

    def test_multi_step(self):
        res = self.fold({"creation": [creation_event()],
                         "s01": [ev("1101", {"add": "xp", "by": 100}),
                                 ev("1102", {"add": "power.glow", "by": 3}, {"add": "xp", "by": -25})]})
        self.assertEqual(res.expected["s01#2"], {"xp": 25})  # 10 + 1*5 + 2*5
        self.assertEqual(res.astate.values["xp"], 75)
        self.assertEqual(codes(res), [])

    def test_set_higher_is_priced_lower_is_not(self):
        res = self.fold({"creation": [creation_event()],
                         "s01": [ev("1101", {"set": "attr.one", "to": 4}, free="gift"),
                                 ev("1102", {"set": "attr.one", "to": 1})]})
        self.assertEqual(res.expected["s01#1"], {"xp": 20})  # 2*4 + 3*4
        self.assertEqual(res.expected["s01#2"], {})

    def test_enum_cost(self):
        res = self.fold({"s01": [ev("1101", {"add": "tier", "by": 2}, {"add": "xp", "by": -9})]})
        self.assertEqual(res.expected["s01#1"], {"xp": 9})  # target 1*3 + target 2*3

    def test_compound_part_cost(self):
        res = self.fold({"s01": [ev("1101", {"add": "bond.grip", "by": 2}, {"add": "xp", "by": -3}),
                                 ev("1102", {"set": "bond", "to": {"grip": 3}}, {"add": "xp", "by": -3})]})
        self.assertEqual(res.expected["s01#1"], {"xp": 3})
        self.assertEqual(res.expected["s01#2"], {"xp": 3})

    def test_in_event_running_state(self):
        res = self.fold({"creation": [creation_event()],
                         "s01": [ev("1101", {"set": "kind", "to": "k2"},
                                    {"add": "power.drift", "by": 2}, {"add": "xp", "by": -15})]})
        self.assertEqual(res.expected["s01#1"], {"xp": 15})  # drift in-clan once kind is k2

    def test_per_currency(self):
        res = self.fold({"s01": [ev("1101", {"set": "xp", "to": 50}, {"set": "karma", "to": 5})],
                         "s02": [ev("1102",
                                    {"add": "attr.one", "by": 1},
                                    {"gain": "list.boons", "id": "b1", "entry": {"price": 3}},
                                    {"add": "xp", "by": -4}, {"add": "karma", "by": -3})]})
        self.assertEqual(res.expected["s02#1"], {"xp": 4, "karma": 3})
        self.assertEqual(codes(res), [])

    def test_per_currency_mismatch_only_one(self):
        res = self.fold({"s01": [ev("1101", {"set": "xp", "to": 50}, {"set": "karma", "to": 5})],
                         "s02": [ev("1102",
                                    {"add": "attr.one", "by": 1},
                                    {"gain": "list.boons", "id": "b1", "entry": {"price": 3}},
                                    {"add": "xp", "by": -4}, {"add": "karma", "by": -1})]})
        w = warnings_of(res, "cost-mismatch")
        self.assertEqual([x["message"] for x in w], ["paid 1 karma, quote 3 karma"])

    def test_no_cost_free_and_mismatch(self):
        res = self.fold({"creation": [creation_event()], "s01": [
            ev("1101", {"add": "attr.one"}),
            ev("1102", {"add": "attr.one"}, free="story reward"),
            ev("1103", {"add": "xp", "by": 100}),
            ev("1104", {"add": "attr.one"}, {"add": "xp", "by": -3})]})
        self.assertEqual([(w["code"], w["ref"]) for w in res.warnings],
                         [("no-cost", "s01#1"), ("cost-mismatch", "s01#4")])
        self.assertIn("paid 3 xp, quote 16 xp", warnings_of(res, "cost-mismatch")[0]["message"])
        self.assertEqual(warnings_of(res, "no-cost")[0]["key"], "attr.one")

    def test_payment_on_undeclared_currency(self):
        r = cost_rules()
        r["classes"]["attr"]["cost"] = {"raise": "2", "currency": "sparks"}
        res = self.fold({"s01": [ev("1101", {"add": "attr.one"}, {"add": "sparks", "by": -2})]}, rules=r)
        # still counted as paid (no cost-mismatch); undeclared → rating min 0 → below min
        self.assertEqual(codes(res), ["unknown-trait", "over-cap"])
        self.assertEqual(warnings_of(res, "unknown-trait")[0]["key"], "sparks")

    def test_creation_events_are_not_priced(self):
        res = self.fold({"creation": [creation_event()]})
        self.assertEqual(res.expected["creation#1"], {})
        self.assertEqual(codes(res), [])

    def test_out_of_order_insert_keeps_stored_cost(self):
        res = self.fold({"creation": [creation_event()],
                         "s01": [ev("1101", {"add": "xp", "by": 100}),
                                 ev("1110", {"add": "attr.one"}, {"add": "xp", "by": -8})],
                         "s02": [ev("1105", {"add": "attr.one"}, {"add": "xp", "by": -8})]})
        # 1105 raise 2→3 = 8 (fine); 1110 now raises 3→4 = 12 but 8 was stored
        self.assertEqual(res.astate.values["xp"], 84)
        self.assertEqual(res.astate.values["attr.one"], 4)
        w = warnings_of(res, "cost-mismatch")
        self.assertEqual([(x["ref"], x["message"]) for x in w], [("s01#2", "paid 8 xp, quote 12 xp")])

    def test_quote(self):
        sd = SheetDir(cost_rules(), catalog=BASE_CATALOG,
                      history={"creation": [creation_event()],
                               "s01": [ev("1101", {"add": "power.glow"}, free="x")]})
        self.addCleanup(sd.cleanup)
        q = quote(sd.load(), "power.glow", by=2)
        self.assertEqual((q["from"], q["to"], q["total"], q["currency"]), (1, 3, 15, "xp"))
        self.assertEqual([s["cost"] for s in q["steps"]], [5, 10])
        q0 = quote(sd.load(), "power.glow", by=1, at="1100")
        self.assertEqual((q0["from"], q0["total"]), (0, 10))
        qe = quote(sd.load(), "tier", by=1)
        self.assertEqual((qe["from"], qe["to"], qe["total"]), ("low", "mid", 3))
        qp = quote(sd.load(), "bond.grip", by=2)
        self.assertEqual(qp["total"], 3)


# ------------------------------------------------------------------ budgets

def budget_rules():
    r = copy.deepcopy(BASE_RULES)
    r["classes"]["attr"]["base"] = 1
    r["traits"]["grit"] = {"max": 10}
    r["lists"]["gifts"] = {"name": "Gifts"}
    r["lists"]["flaws"] = {"name": "Flaws"}
    r["creation"] = {
        "budgets": {
            "attrs": {"class": "attr", "by": "group", "priority": [3, 1]},
            "powers": {"class": "power", "total": 1,
                       "where": "id in catalog('kind', kind).powers"},
            "virtues": {"class": "virtue", "total": 2},
            "grit": {"keys": ["grit"], "total": 0, "base": "virtue.alpha"},
            "gifts": {"list": "gifts", "total": 2, "spend": "sum(list.gifts[*].points)"},
            "knacks": {"class": "knack", "total": 5, "step_cost": "if(target > 2, 2, 1)"},
        },
        "freebies": {"total": "3 + min(2, count(list.flaws))",
                     "cost": {"grit": 1, "attr": 5}},
        "checks": {"lvl": {"when": "level != 1", "message": "Start at level 1"}},
    }
    return r


def budget_creation(**over):
    vals = {"kind": "k1", "path": "first", "level": 1, "attr.one": 3, "attr.two": 2,
            "attr.three": 2, "power.glow": 1, "virtue.alpha": 2, "virtue.beta": 2,
            "grit": 6, "knack.a": 3, "knack.b": 1}
    vals.update(over)
    effects = [{"set": k, "to": v} for k, v in vals.items() if v is not None]
    return effects


def gifts(*points):
    return [{"gain": "list.gifts", "id": "g%d" % i, "entry": {"points": p}}
            for i, p in enumerate(points)]


FLAW = [{"gain": "list.flaws", "id": "f1", "entry": {"name": "Flaw"}}]


class TestBudgets(CostCase):
    def run_budget(self, effects, extra=None, rules=None):
        hist = {"creation": [ev("1100", *effects, kind="creation")]}
        if extra:
            hist["s01"] = extra
        return self.fold(hist, rules=rules or budget_rules())

    def cb(self, res):
        return [w["message"] for w in warnings_of(res, "creation-budget")]

    def test_valid_creation_is_silent(self):
        # grit: base = virtue.alpha (2) → 6 is 4 over → 4 freebies; total 3 + 1 flaw = 4
        res = self.run_budget(budget_creation() + gifts(1, 1) + FLAW)
        self.assertEqual(codes(res), [])

    def test_total_underspend(self):
        res = self.run_budget(budget_creation(**{"virtue.beta": 1}) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["budget virtues: spent 1 of 2 (1 under)"])

    def test_priority_slots_and_freebies_by_class(self):
        # body spends 3, mind 2 → sorted [3, 2] vs priority [3, 1]: mind over by 1 → 5 freebies (attr)
        res = self.run_budget(budget_creation(**{"attr.three": 3}) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["freebies: spent 9 of 4"])

    def test_priority_underspend_names_the_group(self):
        res = self.run_budget(budget_creation(**{"attr.one": 2}) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["budget attrs (body): spent 2 of 3 (1 under)"])

    def test_keys_budget_with_base_expr(self):
        res = self.run_budget(budget_creation(grit=2) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["freebies: spent 0 of 4"])

    def test_expression_freebies_total(self):
        res = self.run_budget(budget_creation() + gifts(1, 1))  # no flaw → total 3
        self.assertEqual(self.cb(res), ["freebies: spent 4 of 3"])

    def test_list_spend_over_with_no_freebie_cost(self):
        res = self.run_budget(budget_creation() + gifts(2, 1) + FLAW)
        self.assertEqual(self.cb(res), ["budget gifts: spent 3 of 2 (1 over, no freebie cost)"])

    def test_step_cost(self):
        # knack.a 4: 1 + 1 + 2 + 2 = 6, knack.b 1 → 7 of 5
        res = self.run_budget(budget_creation(**{"knack.a": 4}) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["budget knacks: spent 7 of 5 (2 over, no freebie cost)"])

    def test_where(self):
        res = self.run_budget(budget_creation(**{"power.glow": None, "power.drift": 1})
                              + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["budget powers: power.drift spent outside where"])

    def test_checks_on_creation_state(self):
        res = self.run_budget(budget_creation(level=2) + gifts(1, 1) + FLAW)
        self.assertEqual(self.cb(res), ["check lvl: Start at level 1"])
        later = self.run_budget(budget_creation() + gifts(1, 1) + FLAW,
                                extra=[ev("1200", {"set": "level", "to": 3})])
        self.assertEqual(self.cb(later), [])

    def test_absent_freebies_is_total_zero(self):
        r = budget_rules()
        del r["creation"]["freebies"]
        res = self.run_budget(budget_creation(grit=2) + gifts(1, 1), rules=r)
        self.assertEqual(self.cb(res), [])
        res = self.run_budget(budget_creation() + gifts(1, 1), rules=r)
        self.assertEqual(self.cb(res), ["budget grit: spent 4 of 0 (4 over, no freebie cost)"])

    def test_no_budget_check_without_creation_events(self):
        res = self.fold({"s01": [ev("1100", {"set": "level", "to": 1})]}, rules=budget_rules())
        self.assertEqual(self.cb(res), [])

    def test_value_below_base_is_underspend(self):
        r = budget_rules()
        res = self.run_budget(budget_creation(grit=1) + gifts(1, 1) + FLAW, rules=r)
        self.assertEqual(self.cb(res), ["budget grit: spent -1 of 0 (1 under)",
                                        "freebies: spent 0 of 4"])


if __name__ == "__main__":
    unittest.main()
