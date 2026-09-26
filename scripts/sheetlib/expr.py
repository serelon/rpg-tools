"""Tiny safe expression language for sheet rules (spec S4).

Expressions are parsed with ``ast`` in eval mode, checked against a node
whitelist at load time, and evaluated by an explicit tree walker. Nothing is
ever passed to ``eval``; values are only JSON data (dict, list, str, int,
float, bool, None), and attribute/subscript access is implemented here on
those types without ``getattr``/``getitem`` on arbitrary Python objects.

Name resolution is delegated to an *environment* object (see ``Env``), so the
fold can hand the evaluator whichever state it needs (unanchored, anchored,
creation).
"""
import ast
import keyword
import math
import re


class SheetError(Exception):
    """Fatal input error (exit 2): malformed pack/manifest, bad expression..."""


class ExprError(Exception):
    """Runtime expression failure: reported as ``expr-error``, value None."""


BUILTINS = frozenset([
    "sum", "count", "min", "max", "table", "catalog", "clamp", "if", "_if",
    "round", "floor", "ceil", "abs", "rank", "get",
])

# Names that may never be a trait key's first segment, derived key, class,
# list or span name (S2).
RESERVED = frozenset([
    "current", "target", "key", "id", "entry", "value", "index", "list",
    "span_years", "span_open", "span_note", "span_id",
]) | BUILTINS

SEGMENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

MAX_SOURCE = 1000
MAX_DEPTH = 50

_ALLOWED_NODES = (
    ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Attribute,
    ast.Subscript, ast.List, ast.Tuple, ast.Call, ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd, ast.BinOp, ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Compare, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)
_CONST_TYPES = (int, float, str, bool, type(None))

_IF_RE = re.compile(r"\bif\s*\(")


def valid_segment(seg):
    return bool(SEGMENT_RE.match(seg)) and not keyword.iskeyword(seg)


def valid_key(key):
    """Dotted key whose every segment is ``[a-z_][a-z0-9_]*`` and no keyword."""
    if not isinstance(key, str) or not key:
        return False
    return all(valid_segment(s) for s in key.split("."))


def pretokenise(src):
    """``[*]`` -> ``.__all__``; ``if(`` -> ``_if(`` (textual, S4)."""
    return _IF_RE.sub("_if(", src.replace("[*]", ".__all__"))


class Compiled:
    """A parsed, whitelisted expression."""

    __slots__ = ("src", "tree", "where")

    def __init__(self, src, tree, where):
        self.src = src
        self.tree = tree
        self.where = where

    def __repr__(self):
        return "Compiled(%r)" % self.src


def _depth(node):
    children = list(ast.iter_child_nodes(node))
    if not children:
        return 1
    return 1 + max(_depth(c) for c in children)


def compile_expr(src, where="expression"):
    """Parse and whitelist-check an expression. Raises SheetError (fatal)."""
    if not isinstance(src, str):
        raise SheetError("%s: expression must be a string, got %r" % (where, src))
    if len(src) > MAX_SOURCE:
        raise SheetError("%s: expression longer than %d characters" % (where, MAX_SOURCE))
    text = pretokenise(src)
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise SheetError("%s: syntax error in expression %r: %s" % (where, src, exc.msg))
    if _depth(tree) > MAX_DEPTH:
        raise SheetError("%s: expression nested deeper than %d" % (where, MAX_DEPTH))
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise SheetError("%s: %s not allowed in expression %r"
                             % (where, type(node).__name__, src))
        if isinstance(node, ast.Constant) and type(node.value) not in _CONST_TYPES:
            raise SheetError("%s: constant of type %s not allowed in expression %r"
                             % (where, type(node.value).__name__, src))
        if isinstance(node, ast.Attribute) and node.attr.startswith("_") \
                and node.attr != "__all__":
            raise SheetError("%s: attribute %r not allowed in expression %r"
                             % (where, node.attr, src))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in BUILTINS:
                raise SheetError("%s: only builtin calls (%s) allowed in expression %r"
                                 % (where, ", ".join(sorted(BUILTINS - {"_if"})), src))
            if node.keywords:
                raise SheetError("%s: keyword arguments not allowed in expression %r"
                                 % (where, src))
    return Compiled(src, tree, where)


def compile_slot(value, where):
    """An expression slot: JSON number/bool literal, None, or expression string."""
    if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return compile_expr(value, where)
    raise SheetError("%s: expected a number, bool or expression string, got %r"
                     % (where, value))


# ---------------------------------------------------------------- values

def is_number(x):
    return isinstance(x, (int, float))  # bool counts as int


def normalise(x):
    """Integral floats -> int (recursively through lists and dicts)."""
    if isinstance(x, float) and not isinstance(x, bool) and math.isfinite(x) \
            and x == int(x):
        return int(x)
    if isinstance(x, list):
        return [normalise(v) for v in x]
    if isinstance(x, dict):
        return {k: normalise(v) for k, v in x.items()}
    return x


def _typename(x):
    if x is None:
        return "None"
    return {bool: "bool", int: "number", float: "number", str: "string",
            list: "list", dict: "object"}.get(type(x), type(x).__name__)


def attr_of(value, attr):
    if isinstance(value, dict):
        return value.get(attr)
    if value is None:
        return None
    raise ExprError("cannot read .%s of a %s" % (attr, _typename(value)))


def subscript(container, index):
    if isinstance(index, bool) or not isinstance(index, (str, int)):
        raise ExprError("index must be a string or integer, got %s" % _typename(index))
    if isinstance(container, dict):
        return container.get(index)
    if isinstance(container, list):
        if not isinstance(index, int):
            raise ExprError("list index must be an integer, got %r" % index)
        if 0 <= index < len(container):
            return container[index]
        return None
    raise ExprError("cannot index a %s" % _typename(container))


def _items(xs, fname):
    if isinstance(xs, dict):
        return list(xs.values())
    if isinstance(xs, (list, tuple)):
        return list(xs)
    raise ExprError("%s() needs a list or object, got %s" % (fname, _typename(xs)))


def _num(x, what):
    if not is_number(x):
        raise ExprError("%s needs numbers, got %s" % (what, _typename(x)))
    return x


def _finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        raise ExprError("non-finite result")
    return x


class Env:
    """Interface the evaluator needs. The fold supplies a real one."""

    def lookup(self, segs, local):
        """Resolve a dotted path. Return ``(value, consumed_segments)``."""
        raise ExprError("unknown name %s" % ".".join(segs))

    def table(self, name, key):
        raise ExprError("no table %r" % name)

    def catalog(self, ns, key):
        return None

    def rank(self, key, local):
        raise ExprError("rank() unavailable")


def lookup_table(tables, name, key):
    """``table(name, key)`` against ``rules.tables`` (S4)."""
    if not isinstance(name, str):
        raise ExprError("table name must be a string")
    tab = tables.get(name)
    if not isinstance(tab, dict):
        raise ExprError("unknown table %r" % name)
    if key is None:
        return None
    key = normalise(key)
    if "rows" in tab:
        rows = tab.get("rows") or {}
        k = key if isinstance(key, str) else (
            ("true" if key else "false") if isinstance(key, bool) else str(key))
        if k not in rows:
            raise ExprError("table %r has no row %r" % (name, k))
        return rows[k]
    if "steps" in tab:
        if not is_number(key):
            raise ExprError("table %r steps need a number key, got %r" % (name, key))
        found = None
        for step in tab.get("steps") or []:
            if not isinstance(step, list) or len(step) != 2:
                raise ExprError("table %r has a malformed step" % name)
            if step[0] <= key:
                found = step
            else:
                break
        if found is None:
            raise ExprError("table %r has no step at or below %r" % (name, key))
        return found[1]
    raise ExprError("table %r has neither rows nor steps" % name)


class Evaluator:
    """Walks a compiled expression against an ``Env``."""

    def __init__(self, env):
        self.env = env

    def evaluate(self, compiled, local=None):
        if not isinstance(compiled, Compiled):
            return compiled  # literal slot
        try:
            return self._ev(compiled.tree.body, local or {})
        except ExprError:
            raise
        except RecursionError:
            raise ExprError("expression too deep")
        except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ExprError(str(exc))

    # -- nodes
    def _ev(self, node, loc):
        t = type(node)
        if t is ast.Constant:
            return node.value
        if t is ast.Name:
            return self._path([node.id], [], loc)
        if t is ast.Attribute:
            chain = []
            base = node
            while isinstance(base, ast.Attribute):
                chain.append(base.attr)
                base = base.value
            chain.reverse()
            if isinstance(base, ast.Name):
                segs = [base.id] + chain
                if "__all__" in segs:
                    i = segs.index("__all__")
                    return self._path(segs[:i], segs[i:], loc)
                return self._path(segs, [], loc)
            return self._attrs(self._ev(base, loc), chain)
        if t is ast.Subscript:
            return subscript(self._ev(node.value, loc), self._ev(node.slice, loc))
        if t in (ast.List, ast.Tuple):
            return [self._ev(e, loc) for e in node.elts]
        if t is ast.Call:
            return self._call(node, loc)
        if t is ast.BoolOp:
            val = None
            if isinstance(node.op, ast.And):
                for e in node.values:
                    val = self._ev(e, loc)
                    if not val:
                        return val
                return val
            for e in node.values:
                val = self._ev(e, loc)
                if val:
                    return val
            return val
        if t is ast.UnaryOp:
            v = self._ev(node.operand, loc)
            if isinstance(node.op, ast.Not):
                return not v
            _num(v, "unary operator")
            return -v if isinstance(node.op, ast.USub) else +v
        if t is ast.BinOp:
            return self._binop(node, loc)
        if t is ast.Compare:
            return self._compare(node, loc)
        raise ExprError("unsupported node %s" % t.__name__)

    def _path(self, key_segs, rest, loc):
        value, used = self.env.lookup(key_segs, loc)
        return self._attrs(value, list(key_segs[used:]) + list(rest))

    def _attrs(self, value, attrs):
        proj = False
        for a in attrs:
            if a == "__all__":
                if proj or not isinstance(value, list):
                    raise ExprError("[*] needs a list, got %s" % _typename(value))
                proj = True
                continue
            if proj:
                value = [attr_of(v, a) for v in value]
            else:
                if isinstance(value, list):
                    raise ExprError("cannot read .%s of a list (use [*])" % a)
                value = attr_of(value, a)
        return value

    def _binop(self, node, loc):
        a = self._ev(node.left, loc)
        b = self._ev(node.right, loc)
        op = type(node.op)
        _num(a, "arithmetic")
        _num(b, "arithmetic")
        if op is ast.Add:
            r = a + b
        elif op is ast.Sub:
            r = a - b
        elif op is ast.Mult:
            r = a * b
        elif op in (ast.Div, ast.FloorDiv, ast.Mod):
            if b == 0:
                raise ExprError("division by zero")
            r = a / b if op is ast.Div else (a // b if op is ast.FloorDiv else a % b)
        else:
            raise ExprError("unsupported operator")
        return _finite(r)

    def _compare(self, node, loc):
        left = self._ev(node.left, loc)
        for op, comp in zip(node.ops, node.comparators):
            right = self._ev(comp, loc)
            ot = type(op)
            if ot is ast.Eq:
                ok = left == right
            elif ot is ast.NotEq:
                ok = left != right
            elif ot in (ast.In, ast.NotIn):
                ok = self._contains(right, left)
                if ot is ast.NotIn:
                    ok = not ok
            else:
                both_num = is_number(left) and is_number(right)
                both_str = isinstance(left, str) and isinstance(right, str)
                if not (both_num or both_str):
                    raise ExprError("cannot order %s and %s"
                                    % (_typename(left), _typename(right)))
                ok = {ast.Lt: left < right, ast.LtE: left <= right,
                      ast.Gt: left > right, ast.GtE: left >= right}[ot]
            if not ok:
                return False
            left = right
        return True

    @staticmethod
    def _contains(container, item):
        if container is None:
            return False
        if isinstance(container, (list, tuple)):
            return item in container
        if isinstance(container, dict):
            if isinstance(item, (list, dict)):
                return False
            return item in container
        if isinstance(container, str):
            if not isinstance(item, str):
                raise ExprError("'in <string>' needs a string, got %s" % _typename(item))
            return item in container
        raise ExprError("cannot test membership in a %s" % _typename(container))

    def _call(self, node, loc):
        name = node.func.id
        if name in ("if", "_if"):
            if len(node.args) != 3:
                raise ExprError("if() takes 3 arguments")
            cond = self._ev(node.args[0], loc)
            return self._ev(node.args[1] if cond else node.args[2], loc)
        args = [self._ev(a, loc) for a in node.args]
        n = len(args)

        def need(lo, hi=None):
            hi = lo if hi is None else hi
            if not lo <= n <= hi:
                raise ExprError("%s() takes %s argument(s), got %d"
                                % (name, lo if lo == hi else "%d-%d" % (lo, hi), n))

        if name == "sum":
            need(1)
            total = 0
            for x in _items(args[0], "sum"):
                if x is None:
                    continue
                total += _num(x, "sum()")
            return _finite(total)
        if name == "count":
            need(1)
            c = 0
            for x in _items(args[0], "count"):
                if x is None or x is False or x == "":
                    continue
                if is_number(x) and x == 0:
                    continue
                c += 1
            return c
        if name in ("min", "max"):
            if n == 0:
                raise ExprError("%s() of nothing" % name)
            xs = _items(args[0], name) if n == 1 else args
            if not xs:
                raise ExprError("%s() of an empty list" % name)
            for x in xs:
                _num(x, "%s()" % name)
            return min(xs) if name == "min" else max(xs)
        if name == "table":
            need(2)
            return self.env.table(args[0], args[1])
        if name == "catalog":
            need(2)
            if args[1] is None:
                return None
            return self.env.catalog(args[0], args[1])
        if name == "clamp":
            need(3)
            for x in args:
                _num(x, "clamp()")
            return min(max(args[0], args[1]), args[2])
        if name == "round":
            need(1, 2)
            x = _num(args[0], "round()")
            nd = _num(args[1], "round()") if n == 2 else 0
            if isinstance(nd, float):
                nd = int(nd)
            return int(round(x)) if nd == 0 else round(x, nd)
        if name in ("floor", "ceil"):
            need(1)
            x = _num(args[0], name + "()")
            return int(math.floor(x) if name == "floor" else math.ceil(x))
        if name == "abs":
            need(1)
            return abs(_num(args[0], "abs()"))
        if name == "rank":
            need(1)
            if not isinstance(args[0], str):
                raise ExprError("rank() needs a key string")
            return self.env.rank(args[0], loc)
        if name == "get":
            need(2)
            return subscript(args[0], args[1])
        raise ExprError("unknown function %s" % name)


class DictEnv(Env):
    """A minimal environment over plain dicts (tests, simple uses).

    ``names`` maps dotted keys to values; longest prefix wins.
    """

    def __init__(self, names=None, tables=None, catalog=None):
        self.names = names or {}
        self.tables = tables or {}
        self.cat = catalog or {}

    def lookup(self, segs, local):
        for n in range(len(segs), 0, -1):
            k = ".".join(segs[:n])
            if n == 1 and k in local:
                return local[k], 1
            if k in self.names:
                return self.names[k], n
        raise ExprError("unknown name %s" % ".".join(segs))

    def table(self, name, key):
        return lookup_table(self.tables, name, key)

    def catalog(self, ns, key):
        return (self.cat.get(ns) or {}).get(key)

    def rank(self, key, local):
        v, _ = self.lookup(key.split("."), local)
        return v
