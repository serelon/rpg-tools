"""Tests for the safe expression language (spec S4)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import SheetDir, ev, warnings_of  # noqa: E402
from sheetlib.expr import (DictEnv, Evaluator, ExprError, SheetError, compile_expr,  # noqa: E402
                           pretokenise)


def run(src, names=None, tables=None, catalog=None, local=None):
    env = DictEnv(names or {}, tables or {}, catalog or {})
    return Evaluator(env).evaluate(compile_expr(src), local or {})


class TestPretokenise(unittest.TestCase):
    def test_star_and_if(self):
        self.assertEqual(pretokenise("sum(list.gear[*].w)"), "sum(list.gear.__all__.w)")
        self.assertEqual(pretokenise("if(a, 1, 2)"), "_if(a, 1, 2)")
        self.assertEqual(pretokenise("if (a, 1, 2)"), "_if(a, 1, 2)")
        self.assertEqual(pretokenise("x + _if(a,1,2)"), "x + _if(a,1,2)")
        self.assertEqual(pretokenise("gif(1)"), "gif(1)")


class TestWhitelist(unittest.TestCase):
    def test_every_whitelisted_node(self):
        n = {"a": 3, "b": 2, "s": "hi", "d": {"k": 1}, "l": [1, 2]}
        cases = [
            ("1", 1), ("2.5", 2.5), ("'x'", "x"), ("True", True), ("None", None),
            ("a", 3), ("d.k", 1), ("d['k']", 1), ("l[1]", 2), ("[1, a]", [1, 3]),
            ("(1, 2)", [1, 2]), ("max(a, b)", 3),
            ("a and b", 2), ("0 or b", 2), ("not a", False), ("-a", -3), ("+a", 3),
            ("a + b", 5), ("a - b", 1), ("a * b", 6), ("a / b", 1.5), ("a // b", 1),
            ("a % b", 1),
            ("a == 3", True), ("a != 3", False), ("a < b", False), ("a <= 3", True),
            ("a > b", True), ("a >= 4", False), ("'h' in s", True), ("3 not in l", True),
            ("1 < a < 5", True), ("'k' in d", True),
        ]
        for src, want in cases:
            self.assertEqual(run(src, n), want, src)

    def test_rejected_nodes_fatal(self):
        for src in ["lambda: 1", "1 if a else 2", "2 ** 3", "[x for x in l]", "f(a=1)",
                    "max(*l)", "l[1:2]", "{'a': 1}", "{1, 2}", "f'{a}'", "(a := 1)",
                    "a & b", "a << 1", "~a", "open('x')", "a.b()", "__import__('os')",
                    "sum(l, start=1)", "a is None", "print(a)"]:
            with self.assertRaises(SheetError, msg=src):
                compile_expr(src)

    def test_load_limits(self):
        for src in ["b'x'", "1j", "a._private", "a.__class__", "x.__dict__"]:
            with self.assertRaises(SheetError, msg=src):
                compile_expr(src)
        with self.assertRaises(SheetError):
            compile_expr("1 + " * 300 + "1")  # > 1000 chars
        deep = "(" * 60 + "1" + ")" * 60
        compile_expr(deep)  # parentheses don't nest AST nodes
        with self.assertRaises(SheetError):
            compile_expr("-" * 60 + "1")  # depth > 50
        compile_expr("a.__all__")  # the tokeniser's own attribute is allowed

    def test_syntax_error_fatal(self):
        with self.assertRaises(SheetError):
            compile_expr("1 +")


class TestOperatorRules(unittest.TestCase):
    def test_abuse_is_expr_error(self):
        for src in ["[0] * 9", "'x' * 9", "'%d' % 1", "'a' + 'b'", "[1] + [2]", "1 / 0",
                    "1 // 0", "1 % 0", "1e308 * 10", "None + 1", "None < 1", "'a' < 1",
                    "-'a'", "l.x", "a.x", "s[0]", "l['k']", "1 in a"]:
            with self.assertRaises(ExprError, msg=src):
                run(src, {"a": 1, "l": [1], "s": "str"})

    def test_bool_counts_as_int(self):
        self.assertEqual(run("True + 1"), 2)


class TestNoneRules(unittest.TestCase):
    def test_none(self):
        n = {"n": None, "d": {"k": None}}
        self.assertIsNone(run("n.anything", n))
        self.assertIsNone(run("d.missing", n))
        self.assertFalse(run("1 in n", n))
        self.assertTrue(run("1 not in n", n))
        self.assertTrue(run("n == None", n))
        self.assertFalse(run("n != None", n))
        self.assertIsNone(run("d.k.deeper", n))


class TestBuiltins(unittest.TestCase):
    def test_sum_count(self):
        self.assertEqual(run("sum([1, 2, None, 3])"), 6)
        self.assertEqual(run("sum([])"), 0)
        self.assertEqual(run("sum(d)", {"d": {"a": 2, "b": 5}}), 7)
        self.assertEqual(run("count([0, 1, None, False, '', 'x', 2])"), 3)
        with self.assertRaises(ExprError):
            run("sum(['a'])")

    def test_min_max(self):
        self.assertEqual(run("min(3, 1, 2)"), 1)
        self.assertEqual(run("max([3, 1, 2])"), 3)
        with self.assertRaises(ExprError):
            run("min([])")
        with self.assertRaises(ExprError):
            run("max(None, 1)")

    def test_if_is_lazy(self):
        self.assertEqual(run("if(True, 1, 1 / 0)"), 1)
        self.assertEqual(run("if(0, 1 / 0, 2)"), 2)
        with self.assertRaises(ExprError):
            run("if(True, 1 / 0, 2)")

    def test_clamp_round_floor_ceil_abs(self):
        self.assertEqual(run("clamp(7, 1, 5)"), 5)
        self.assertEqual(run("clamp(-2, 1, 5)"), 1)
        self.assertEqual(run("round(2.6)"), 3)
        self.assertIsInstance(run("round(2.6)"), int)
        self.assertEqual(run("round(2.456, 2)"), 2.46)
        self.assertEqual(run("floor(2.7)"), 2)
        self.assertEqual(run("ceil(2.1)"), 3)
        self.assertIsInstance(run("ceil(2.1)"), int)
        self.assertEqual(run("abs(-4)"), 4)

    def test_table_rows_steps(self):
        tables = {"gen": {"rows": {"8": {"cap": 5}, "9": {"cap": 4}}},
                  "lvl": {"steps": [[0, {"l": 1}], [300, {"l": 2}], [900, {"l": 3}]]}}
        self.assertEqual(run("table('gen', 8).cap", tables=tables), 5)
        self.assertEqual(run("table('gen', 16 / 2).cap", tables=tables), 5)  # 8.0 → 8
        self.assertEqual(run("table('gen', '9').cap", tables=tables), 4)
        self.assertIsNone(run("table('gen', None)", tables=tables))
        self.assertEqual(run("table('lvl', 299).l", tables=tables), 1)
        self.assertEqual(run("table('lvl', 300).l", tables=tables), 2)
        self.assertEqual(run("table('lvl', 5000).l", tables=tables), 3)
        with self.assertRaises(ExprError):
            run("table('gen', 3)", tables=tables)
        with self.assertRaises(ExprError):
            run("table('nope', 3)", tables=tables)
        with self.assertRaises(ExprError):
            run("table('lvl', -1)", tables=tables)

    def test_catalog_get(self):
        cat = {"kind": {"k1": {"name": "One", "powers": ["a"]}}}
        self.assertEqual(run("catalog('kind', 'k1').name", catalog=cat), "One")
        self.assertIsNone(run("catalog('kind', 'zz')", catalog=cat))
        self.assertIsNone(run("catalog('kind', None)", catalog=cat))
        self.assertTrue(run("'a' in catalog('kind', 'k1').powers", catalog=cat))
        self.assertEqual(run("get(d, 'k')", {"d": {"k": 4}}), 4)
        self.assertIsNone(run("get(l, 5)", {"l": [1]}))

    def test_dynamic_subscript(self):
        self.assertEqual(run("d[k]", {"d": {"x": 7}, "k": "x"}), 7)
        self.assertEqual(run("d[catalog('c', 'e').pick]", {"d": {"x": 7}},
                             catalog={"c": {"e": {"pick": "x"}}}), 7)


RULES = {
    "id": "t",
    "classes": {
        "virtue": {"min": 1, "max": 5},
        "knack": {"open": True, "min": 0, "default": 0},
        "v": {},
    },
    "traits": {
        "virtue.one": {}, "virtue.two": {}, "virtue.three": {},
        "pick": {"type": "text"},
        "stance": {"type": "enum", "values": ["low", "mid", "high"]},
        "bond": {"type": "compound", "parts": {"grip": {"type": "rating"}, "who": {"type": "text"}}},
        "v": {"type": "number"},
    },
    "derived": {
        "total": "sum(virtue)",
        "n_virtues": "count(virtue)",
        "bond.grip": "99",
        "loop_a": "loop_b + 1",
        "loop_b": "loop_a + 1",
        "load": "sum(list.gear[*].load)",
        "names": "list.gear[*].name",
    },
    "lists": {"gear": {"fields": {"load": "entry.w * entry.q"}}},
}


class TestResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sd = SheetDir(RULES, history={"s01": [ev(
            "1100",
            {"set": "virtue.one", "to": 3}, {"set": "virtue.two", "to": 2},
            {"set": "pick", "to": "two"}, {"set": "stance", "to": "mid"},
            {"set": "bond", "to": {"grip": 2, "who": "someone"}},
            {"set": "v", "to": 42},
            {"gain": "list.gear", "id": "a", "entry": {"name": "A", "w": 2, "q": 3}},
            {"gain": "list.gear", "id": "b", "entry": {"name": "B", "w": 1, "q": 1}},
            {"gain": "list.gear", "id": "c", "entry": {"name": "C", "w": 5, "q": 1}},
            {"retire": "list.gear", "id": "c"})]})
        cls.res = cls.sd.fold()
        cls.env = cls.res.aenv

    @classmethod
    def tearDownClass(cls):
        cls.sd.cleanup()

    def e(self, src, local=None):
        return self.env.evaluator.evaluate(compile_expr(src), local or {})

    def test_bare_class_dict(self):
        self.assertEqual(self.e("sum(virtue)"), 5)
        self.assertEqual(self.e("count(virtue)"), 2)
        self.assertEqual(self.res.aenv.derived("total"), 5)

    def test_declared_absent_gives_default(self):
        self.assertEqual(self.e("virtue.three"), 1)

    def test_typo_under_closed_class_is_error(self):
        with self.assertRaises(ExprError):
            self.e("virtue.thre")

    def test_open_class_absent_default(self):
        self.assertEqual(self.e("knack.anything"), 0)

    def test_unknown_bare_name_error(self):
        with self.assertRaises(ExprError):
            self.e("nothing_here")

    def test_longest_prefix_first(self):
        # derived 'bond.grip' (2 segments) beats trait 'bond' + attribute 'grip'
        self.assertEqual(self.e("bond.grip"), 99)
        self.assertEqual(self.e("bond.who"), "someone")

    def test_trait_beats_class_at_same_prefix(self):
        self.assertEqual(self.e("v"), 42)

    def test_locals_first(self):
        self.assertEqual(self.e("id", {"id": "two"}), "two")
        self.assertEqual(self.e("virtue[id]", {"id": "two"}), 2)

    def test_dynamic_subscript_on_trait(self):
        self.assertEqual(self.e("virtue[pick]"), 2)
        self.assertIsNone(self.e("virtue['three']"))  # absent → not in the class dict

    def test_enum_is_string_and_rank(self):
        self.assertEqual(self.e("stance"), "mid")
        self.assertTrue(self.e("stance == 'mid'"))
        self.assertEqual(self.e("rank('stance')"), 1)
        self.assertEqual(self.e("rank('virtue.one')"), 3)

    def test_projection_and_flat_entries(self):
        self.assertEqual(self.e("list.gear[*].name"), ["A", "B"])  # retired excluded
        self.assertEqual(self.e("list.gear[*].load"), [6, 1])     # computed field visible
        self.assertEqual(self.env.derived("load"), 7)
        self.assertEqual(self.e("list.gear[0].w"), 2)
        self.assertEqual(self.e("count(list.gear)"), 2)
        with self.assertRaises(ExprError):
            self.e("list.gear.name")

    def test_derived_cycle_is_expr_error(self):
        self.assertIsNone(self.env.derived("loop_a"))
        msgs = [w["message"] for w in warnings_of(self.res, "expr-error")]
        self.assertTrue(any("cycle loop_a -> loop_b -> loop_a" in m for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
