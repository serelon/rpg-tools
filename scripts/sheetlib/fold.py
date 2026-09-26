"""The fold: events → state, plus warnings, anchors and budgets (spec S5–S7).

A character is resolved, not stored: history events are sorted by in-world
date and folded from empty against the rules model. Two states come out:

* **unanchored** — the plain fold; costs and per-event checks use it.
* **anchored** — unanchored with every folded anchor applied in the trait's
  better direction; derived values, output and the final sweep use it.

A third, the **creation state**, is the fold of ``kind: "creation"`` events
only; creation budgets and checks are evaluated on it.
"""
import copy

from . import dates
from .expr import Env, Evaluator, ExprError, is_number, lookup_table, normalise, valid_key

OPS = ("set", "add", "gain", "edit", "retire", "start", "end", "anchor")
ANCHOR_OPS = ("at_least", "at_most", "is", "has")
TRAIT_META = ("name", "group", "note", "gm_only")
# Most single steps one priced raise or creation spend may walk (guards pack- or
# ledger-driven loops: a base of -1e8 must not spin the engine).
MAX_STEPS = 1000


# ------------------------------------------------------------------ sinks

class Sink:
    """Collects warnings; ``expr-error`` deduped by site + message."""

    def __init__(self):
        self.warnings = []
        self._expr_seen = set()

    def warn(self, code, message, key=None, ref=None):
        w = {"code": code, "message": message}
        if key is not None:
            w["key"] = key
        if ref is not None:
            w["ref"] = ref
        self.warnings.append(w)

    def expr_error(self, site, message, ref=None):
        sig = (site, message)
        if sig in self._expr_seen:
            return
        self._expr_seen.add(sig)
        self.warn("expr-error", "%s: %s" % (site, message), ref=ref)


class NullSink(Sink):
    def warn(self, *a, **k):
        pass

    def expr_error(self, *a, **k):
        pass


# ------------------------------------------------------------------ state

class Entry:
    __slots__ = ("data", "retired", "refs", "gm_created")

    def __init__(self, data, refs, gm_created):
        self.data = data
        self.retired = False
        self.refs = refs
        self.gm_created = gm_created


class Span:
    __slots__ = ("id", "kind", "name", "note", "start", "end", "refs", "gm_created")

    def __init__(self, sid, kind, name, note, start, refs, gm_created):
        self.id = sid
        self.kind = kind
        self.name = name
        self.note = note
        self.start = start
        self.end = None
        self.refs = refs
        self.gm_created = gm_created


class State:
    def __init__(self):
        self.values = {}
        self.retired = set()
        self.meta = {}
        self.refs = {}
        self.gm_created = set()
        self.lists = {}
        self.spans = {}
        self.version = 0

    def bump(self):
        self.version += 1

    def copy(self):
        return copy.deepcopy(self)

    def live_entries(self, lname):
        return [e for e in (self.lists.get(lname) or {}).values() if not e.retired]


# ------------------------------------------------------------------ env

class StateEnv(Env):
    """Name resolution tiers 1–6 (S4) over one state; memo per version."""

    def __init__(self, engine, state):
        self.engine = engine
        self.m = engine.model
        self.state = state
        self._version = None
        self._derived = {}
        self._stack = []
        self._listview = None
        self._listbusy = False
        self.evaluator = Evaluator(self)

    def _fresh(self):
        if self._version != self.state.version:
            self._version = self.state.version
            self._derived = {}
            self._listview = None

    # tiers
    def lookup(self, segs, local):
        m = self.m
        st = self.state
        for n in range(len(segs), 0, -1):
            k = ".".join(segs[:n])
            if n == 1 and k in local:
                return local[k], 1
            if k in m.derived:
                return self.derived(k), n
            if k in st.values:
                return st.values[k], n
            if k in m.traits:
                return self.engine.default(self, k), n
            if n == 2 and segs[0] in m.classes:
                if m.classes[segs[0]].get("open"):
                    return self.engine.default(self, k), n
                raise ExprError("unknown trait %s (class %s is closed)" % (k, segs[0]))
            if n == 1 and k in m.classes:
                return self.class_dict(k), 1
            if n == 1 and k == "list":
                return self.list_view(), 1
        raise ExprError("unknown name %s" % ".".join(segs))

    def class_dict(self, cls):
        out = {}
        for k, v in self.state.values.items():
            if self.m.class_of(k) == cls:
                out[k.split(".")[1]] = v
        return out

    def derived(self, key):
        self._fresh()
        if key in self._derived:
            return self._derived[key]
        if key in self._stack:
            chain = self._stack[self._stack.index(key):] + [key]
            raise ExprError("cycle " + " -> ".join(chain))
        self._stack.append(key)
        try:
            val = self.engine.ev(self, self.m.derived[key]["expr"], {}, "derived.%s" % key)
        finally:
            self._stack.pop()
        self._fresh()
        self._derived[key] = val
        return val

    def list_view(self):
        self._fresh()
        if self._listview is not None:
            return self._listview
        if self._listbusy:
            raise ExprError("list fields refer to list (cycle)")
        self._listbusy = True
        try:
            view = {}
            names = list(self.m.lists) + [n for n in self.state.lists if n not in self.m.lists]
            for lname in names:
                ld = self.m.lists.get(lname) or {}
                flds = ld.get("fields") or {}
                rows = []
                for e in self.state.live_entries(lname):
                    flat = dict(e.data)
                    for fk, fx in flds.items():
                        flat[fk] = self.engine.ev(self, fx, {"entry": dict(e.data)},
                                                  "lists.%s.fields.%s" % (lname, fk))
                    rows.append(flat)
                view[lname] = rows
        finally:
            self._listbusy = False
        self._fresh()
        self._listview = view
        return view

    def table(self, name, key):
        return lookup_table(self.m.tables, name, key)

    def catalog(self, ns, key):
        if not isinstance(ns, str) or isinstance(key, (list, dict)):
            return None
        return (self.m.catalog.get(ns) or {}).get(str(normalise(key)) if not isinstance(key, str) else key)

    def rank(self, key, local):
        if not valid_key(key):
            raise ExprError("rank(): invalid key %r" % key)
        td = self.m.tdef(key)
        val, used = self.lookup(key.split("."), local)
        if td.type == "enum" and used == len(key.split(".")):
            vals = td.get("values") or []
            return vals.index(val) if val in vals else None
        return val


# ------------------------------------------------------------------ engine

class Engine:
    """Model + sink; evaluation helpers shared by fold and output."""

    def __init__(self, model, sink):
        self.model = model
        self.sink = sink
        self.current_ref = None

    def env(self, state):
        return StateEnv(self, state)

    def ev(self, env, slot, local, site):
        try:
            return env.evaluator.evaluate(slot, local)
        except ExprError as exc:
            self.sink.expr_error(site, str(exc), ref=self.current_ref)
            return None

    def cat_entry(self, td):
        ns = td.get("catalog")
        if not ns or td.type == "text":
            return None
        return (self.model.catalog.get(ns) or {}).get(td.id)

    def tlocal(self, key):
        td = self.model.tdef(key)
        return {"key": key, "id": td.id, "entry": self.cat_entry(td)}

    def site(self, td, field):
        if td.declared:
            return "traits.%s.%s" % (td.key, field)
        if td.cls:
            return "classes.%s.%s" % (td.cls, field)
        return "%s.%s" % (td.key, field)

    def part_default(self, env, key, part, pd):
        t = pd.get("type", "rating")
        if "default" in pd:
            return pd["default"]
        if t in ("rating", "number"):
            if "min" in pd:
                return self.ev(env, pd["min"], self.tlocal(key), "%s.parts.%s.min" % (key, part))
            return 0 if t == "rating" else None
        if t == "enum":
            vals = pd.get("values") or []
            return vals[0] if vals else None
        return None

    def default(self, env, key):
        td = self.model.tdef(key)
        if "default" in td.d:
            return copy.deepcopy(td.d["default"])
        t = td.type
        if t in ("rating", "number"):
            if "min" in td.d:
                return self.ev(env, td.d["min"], self.tlocal(key), self.site(td, "min"))
            return 0 if t == "rating" else None
        if t == "enum":
            vals = td.get("values") or []
            return vals[0] if vals else None
        if t == "compound":
            return {p: self.part_default(env, key, p, pd)
                    for p, pd in (td.get("parts") or {}).items()}
        return None

    def bounds(self, env, key, part=None):
        td = self.model.tdef(key)
        d = (td.get("parts") or {}).get(part, {}) if part else td.d
        t = d.get("type", "rating")
        loc = self.tlocal(key)
        s = self.site(td, "parts.%s." % part if part else "")
        lo = self.ev(env, d["min"], loc, s + "min") if "min" in d else (0 if t == "rating" else None)
        hi = self.ev(env, d["max"], loc, s + "max") if "max" in d else None
        return lo, hi

    def active(self, env, key):
        """True/False, or None when the trait has no ``active`` expression."""
        td = self.model.tdef(key)
        if "active" not in td.d:
            return None
        return bool(self.ev(env, td.d["active"], self.tlocal(key), self.site(td, "active")))

    def trait_gm_only(self, state, key):
        td = self.model.tdef(key)
        meta = state.meta.get(key) or {}
        # Any one source hides the trait (S8): TraitDef, edit meta, inherited.
        # An explicit meta ``gm_only: false`` never un-hides the other two.
        return (bool(td.get("gm_only")) or key in state.gm_created
                or bool(meta.get("gm_only")))


# ------------------------------------------------------------------ events

class Event:
    __slots__ = ("ref", "date", "key", "seq", "file_index", "event_index", "raw",
                 "effects", "kind", "gm_only", "free", "satisfies", "when", "note",
                 "source", "has_anchor", "pos")

    def order(self):
        return (self.key, self.seq or 0, self.file_index, self.event_index)


def check_effect(eff):
    """Structural check of one effect → problem string or None."""
    if not isinstance(eff, dict):
        return "effect must be an object"
    ops = [o for o in OPS if o in eff]
    if len(ops) != 1:
        return "effect needs exactly one op (%s), got %s" % ("/".join(OPS), ops or "none")
    op = ops[0]
    target = eff[op]
    if not isinstance(target, str) or not valid_key(target):
        return "%s: invalid target %r" % (op, target)
    is_list = target.startswith("list.")
    if is_list and len(target.split(".")) != 2:
        return "%s: list target must be list.NAME" % op
    if op == "set":
        if "to" not in eff:
            return "set needs to"
        if is_list:
            return "set cannot target a list (use gain/edit)"
    elif op == "add":
        by = eff.get("by", 1)
        if isinstance(by, bool) or not is_number(by):
            return "add: by must be a number"
        if is_list:
            return "add cannot target a list (use gain)"
    elif op == "gain":
        if not is_list:
            return "gain needs a list.NAME target"
        if not isinstance(eff.get("id"), str) or not eff.get("id"):
            return "gain needs an id"
        if not isinstance(eff.get("entry", {}), dict):
            return "gain: entry must be an object"
    elif op == "edit":
        if not isinstance(eff.get("fields"), dict):
            return "edit needs a fields object"
        if is_list and (not isinstance(eff.get("id"), str) or not eff.get("id")):
            return "edit of a list entry needs an id"
    elif op == "retire":
        if is_list and (not isinstance(eff.get("id"), str) or not eff.get("id")):
            return "retire of a list entry needs an id"
    elif op in ("start", "end"):
        if is_list or "." in target:
            return "%s: span kind must be a bare name" % op
        if not isinstance(eff.get("id"), str) or not eff.get("id"):
            return "%s needs an id" % op
    elif op == "anchor":
        if not isinstance(eff.get("id"), str) or not eff.get("id"):
            return "anchor needs an id"
        aops = [a for a in ANCHOR_OPS if a in eff]
        if len(aops) != 1:
            return "anchor needs exactly one of at_least/at_most/is/has"
        a = aops[0]
        if a in ("at_least", "at_most") and (isinstance(eff[a], bool) or not is_number(eff[a])):
            return "anchor %s needs a number" % a
        if a == "has" and (not is_list or not isinstance(eff[a], str)):
            return "anchor has needs a list.NAME key and an entry id"
        if a != "has" and is_list:
            return "anchor on a list needs has"
    return None


def check_event(ev):
    """Structural problems of one event: ``(fatal_problem|None, [effect problems])``."""
    if not isinstance(ev, dict):
        return "event must be an object", []
    if not dates.is_valid(ev.get("date")):
        return "invalid or missing date %r" % (ev.get("date"),), []
    if not isinstance(ev.get("effects"), list):
        return "effects must be a list", []
    probs = []
    seq = ev.get("seq")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int)):
        probs.append("seq must be an integer")
    if ev.get("kind") not in (None, "creation"):
        probs.append("kind must be \"creation\" or absent")
    for f in ("when", "note", "satisfies", "source"):
        if ev.get(f) is not None and not isinstance(ev.get(f), str):
            probs.append("%s must be a string" % f)
    if ev.get("gm_only") not in (None, True, False):
        probs.append("gm_only must be a boolean")
    for i, eff in enumerate(ev["effects"]):
        p = check_effect(eff)
        if p:
            probs.append("effect %d: %s" % (i + 1, p))
    return None, probs


def collect_events(sheet, sink):
    """All events from the sheet's history files, validated; sorted."""
    out = []
    for hf in sheet.history:
        for i, raw in enumerate(hf.events):
            ref = "%s#%d" % (hf.stem, i + 1)
            fatal, probs = check_event(raw)
            if fatal:
                sink.warn("invalid-event", "%s: %s; event skipped" % (ref, fatal), ref=ref)
                continue
            effects = []
            for j, eff in enumerate(raw["effects"]):
                p = check_effect(eff)
                if p:
                    sink.warn("invalid-event", "%s effect %d: %s; skipped" % (ref, j + 1, p), ref=ref)
                else:
                    effects.append(eff)
            for p in probs:
                if not p.startswith("effect "):
                    sink.warn("invalid-event", "%s: %s" % (ref, p), ref=ref)
            e = Event()
            e.ref = ref
            e.date = raw["date"]
            e.key = dates.sort_key(raw["date"])
            seq = raw.get("seq")
            e.seq = seq if isinstance(seq, int) and not isinstance(seq, bool) else None
            e.file_index = hf.index
            e.event_index = i
            e.raw = raw
            e.effects = effects
            e.kind = raw.get("kind") if raw.get("kind") == "creation" else None
            e.gm_only = raw.get("gm_only") is True
            e.free = raw.get("free")
            e.satisfies = raw.get("satisfies") if isinstance(raw.get("satisfies"), str) else None
            e.when = raw.get("when")
            e.note = raw.get("note")
            e.source = raw.get("source")
            e.has_anchor = any("anchor" in x for x in effects)
            out.append(e)
    out.sort(key=lambda e: e.order())
    for i, e in enumerate(out):
        e.pos = i
    return out


# ------------------------------------------------------------------ fold

def _fmt(v):
    v = normalise(v)
    if isinstance(v, float):
        return ("%.2f" % v).rstrip("0").rstrip(".")
    return str(v)


class Folder:
    """Applies events to a state; emits per-event warnings to its sink."""

    def __init__(self, engine, first_creation_key=None):
        self.e = engine
        self.m = engine.model
        self.sink = engine.sink
        self.state = State()
        self.env = engine.env(self.state)
        self.first_creation_key = first_creation_key
        self.anchors = []
        self.expected = {}
        self.overcap_keys = set()
        self.list_overcap = set()
        self.satisfies = []
        self.inactive_events = []

    # -- helpers
    def _touch(self, key, ref):
        refs = self.state.refs.setdefault(key, [])
        if ref not in refs:
            refs.append(ref)

    def _current(self, key):
        st = self.state
        if key in st.values:
            return st.values[key]
        return self.e.default(self.env, key)

    def _apply_meta(self, key, eff):
        meta = {k: eff[k] for k in TRAIT_META if k in eff}
        if meta:
            m = self.state.meta.setdefault(key, {})
            for k, v in meta.items():
                if v is None:
                    m.pop(k, None)
                else:
                    m[k] = v

    def _check_known(self, key, ref):
        td = self.m.tdef(key)
        if not td.known:
            self.sink.warn("unknown-trait", "%s is not declared" % key, key=key, ref=ref)
            return
        ns = td.get("catalog")
        if td.cls and ns and td.type != "text":
            if td.id not in (self.m.catalog.get(ns) or {}):
                self.sink.warn("unknown-trait", "%s: %s not in catalog %s" % (key, td.id, ns),
                               key=key, ref=ref)

    def _store(self, key, value, ev):
        st = self.state
        created = key not in st.values
        if key in st.retired:
            st.retired.discard(key)
            st.meta.pop(key, None)
            st.gm_created.discard(key)
        if created:
            if ev.gm_only:
                st.gm_created.add(key)
            else:
                st.gm_created.discard(key)
        st.values[key] = value
        self._touch(key, ev.ref)
        st.bump()

    def _price(self, key, part, cur, new, expected):
        """Price steps cur→new (ints / enum indexes) against the running state."""
        td = self.m.tdef(key)
        d = (td.get("parts") or {}).get(part, {}) if part else td.d
        cost = d.get("cost")
        if not isinstance(cost, dict) or cur is None or new is None:
            return 0
        cur_c = cost.get("currency") or self.m.currency
        loc = self.e.tlocal(key)
        if part:
            loc["value"] = self.state.values.get(key, self.e.default(self.env, key))
        total = 0
        c = int(cur)
        if new - c > MAX_STEPS:
            self.sink.expr_error(self.e.site(td, "cost"), "%s: %s steps to price (more than %d)"
                                 % (key, _fmt(new - c), MAX_STEPS), ref=self.e.current_ref)
            return 0
        while c < new:
            use = "new" if (c == 0 and "new" in cost) else "raise"
            if use in cost:
                l2 = dict(loc, current=c, target=c + 1)
                amt = self.e.ev(self.env, cost[use], l2, self.e.site(td, "cost.%s" % use))
                if is_number(amt):
                    total += amt
            c += 1
        if total:
            expected[cur_c] = expected.get(cur_c, 0) + total
        return total

    # -- effects
    def apply_event(self, ev, creation_only=False):
        self.e.current_ref = ev.ref
        st = self.state
        creation = ev.kind == "creation"
        if (not creation and self.first_creation_key is not None
                and ev.order() < self.first_creation_key):
            self.sink.warn("before-creation", "%s is dated before character creation" % ev.ref,
                           ref=ev.ref)
        before = None if creation else self.active_sets()
        touched_r = []
        touched_n = []
        gained = []
        expected = {}
        costed_keys = []
        for eff in ev.effects:
            op = [o for o in OPS if o in eff][0]
            getattr(self, "_op_" + op)(eff, ev, expected, touched_r, touched_n, gained, costed_keys)
        if ev.satisfies:
            self.satisfies.append((ev.satisfies, ev.ref))
        if not creation:
            self._payment(ev, expected, costed_keys)
        self.expected[ev.ref] = {k: normalise(v) for k, v in expected.items()}
        # bounds, post-event, unanchored
        seen = set()
        for key, part in touched_r:
            if (key, part) in seen or key not in st.values:
                continue
            seen.add((key, part))
            self._check_bounds(key, part, ev.ref)
        for key in dict.fromkeys(touched_n):
            if key not in st.values:
                continue
            td = self.m.tdef(key)
            if "min" in td.d:
                lo = self.e.ev(self.env, td.d["min"], self.e.tlocal(key), self.e.site(td, "min"))
                v = st.values[key]
                if is_number(lo) and is_number(v) and v < lo:
                    self.sink.warn("negative-pool", "%s is %s, below %s" % (key, _fmt(v), _fmt(lo)),
                                   key=key, ref=ev.ref)
        for lname in dict.fromkeys(gained):
            ld = self.m.lists.get(lname) or {}
            if "cap" in ld:
                cap = self.e.ev(self.env, ld["cap"], {}, "lists.%s.cap" % lname)
                n = len(st.live_entries(lname))
                if is_number(cap) and n > cap:
                    self.list_overcap.add(lname)
                    self.sink.warn("over-cap", "list.%s has %d entries, cap %s" % (lname, n, _fmt(cap)),
                                   key="list.%s" % lname, ref=ev.ref)
        if not creation:
            after = self.active_sets()
            self._active_change(before, after, ev)
        self.e.current_ref = None

    def _check_bounds(self, key, part, ref):
        st = self.state
        td = self.m.tdef(key)
        if part:
            pd = (td.get("parts") or {}).get(part, {})
            if pd.get("type", "rating") != "rating":
                return
            v = (st.values.get(key) or {}).get(part)
            wkey = "%s.%s" % (key, part)
        else:
            if td.type != "rating":
                return
            v = st.values.get(key)
            wkey = key
        lo, hi = self.e.bounds(self.env, key, part)
        if not is_number(v):
            return
        if is_number(hi) and v > hi:
            self.overcap_keys.add(wkey)
            self.sink.warn("over-cap", "%s is %s, above max %s" % (wkey, _fmt(v), _fmt(hi)),
                           key=wkey, ref=ref)
        elif is_number(lo) and v < lo:
            self.overcap_keys.add(wkey)
            self.sink.warn("over-cap", "%s is %s, below min %s" % (wkey, _fmt(v), _fmt(lo)),
                           key=wkey, ref=ref)

    def _payment(self, ev, expected, costed_keys):
        currencies = self.m.currencies()
        paid = {}
        for eff in ev.effects:
            if "add" in eff and eff["add"] in currencies:
                by = eff.get("by", 1)
                if is_number(by) and by < 0:
                    paid[eff["add"]] = paid.get(eff["add"], 0) - by
        key = costed_keys[0] if len(set(costed_keys)) == 1 else None
        for c in list(dict.fromkeys(list(expected) + list(paid))):
            e = normalise(expected.get(c, 0))
            p = normalise(paid.get(c, 0))
            if e > 0 and p == 0:
                if not ev.free:
                    self.sink.warn("no-cost", "%s: nothing paid, quote %s %s"
                                   % (ev.ref, _fmt(e), c), key=key, ref=ev.ref)
            elif p > 0 and p != e:
                self.sink.warn("cost-mismatch", "paid %s %s, quote %s %s"
                               % (_fmt(p), c, _fmt(e), c), key=key, ref=ev.ref)

    def _target(self, eff, op, ev):
        target = eff[op]
        parsed = self.m.parse_target(target)
        if parsed is None:
            self.sink.warn("invalid-event", "%s: %s target %r is not a trait or compound part"
                           % (ev.ref, op, target), key=target, ref=ev.ref)
        return parsed

    def _op_set(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        parsed = self._target(eff, "set", ev)
        if not parsed:
            return
        key, part = parsed
        td = self.m.tdef(key)
        self._check_known(key, ev.ref)
        was_retired = key in self.state.retired
        cur = self.state.values[key] if key in self.state.values else self.e.default(self.env, key)
        if was_retired:
            cur = self.e.default(self.env, key)
        to = eff["to"]
        if part:
            pd = td.get("parts")[part]
            val, err = _coerce(pd.get("type", "rating"), pd, to)
            if err:
                return self._bad(ev, "set %s: %s" % (eff["set"], err), eff["set"])
            whole = dict(cur) if isinstance(cur, dict) else {}
            old = whole.get(part)
            self._maybe_price(key, part, pd, old, val, ev, expected, costed)
            whole[part] = val
            self._store(key, whole, ev)
            self._track_touch(key, part, pd.get("type", "rating"), touched_r, touched_n)
        elif td.type == "compound":
            if not isinstance(to, dict):
                return self._bad(ev, "set %s: compound needs an object of parts" % key, key)
            parts = td.get("parts") or {}
            whole = dict(cur) if isinstance(cur, dict) else {}
            newvals = {}
            for p, v in to.items():
                if p not in parts:
                    return self._bad(ev, "set %s: unknown part %r" % (key, p), key)
                val, err = _coerce(parts[p].get("type", "rating"), parts[p], v)
                if err:
                    return self._bad(ev, "set %s.%s: %s" % (key, p, err), key)
                newvals[p] = val
            for p, val in newvals.items():
                self._maybe_price(key, p, parts[p], whole.get(p), val, ev, expected, costed)
                whole[p] = val
            self._store(key, whole, ev)
            for p in newvals:
                self._track_touch(key, p, parts[p].get("type", "rating"), touched_r, touched_n)
        else:
            val, err = _coerce(td.type, td.d, to)
            if err:
                return self._bad(ev, "set %s: %s" % (key, err), key)
            self._maybe_price(key, None, td.d, cur, val, ev, expected, costed)
            self._store(key, val, ev)
            self._track_touch(key, None, td.type, touched_r, touched_n)
        self._apply_meta(key, eff)

    def _op_add(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        parsed = self._target(eff, "add", ev)
        if not parsed:
            return
        key, part = parsed
        td = self.m.tdef(key)
        by = eff.get("by", 1)
        d = (td.get("parts") or {}).get(part, {}) if part else td.d
        t = d.get("type", "rating") if part else td.type
        if t in ("text", "relation", "compound"):
            return self._bad(ev, "add on %s trait %s" % (t, eff["add"]), eff["add"])
        if t in ("rating", "enum") and (isinstance(by, float) and by != int(by)):
            return self._bad(ev, "add %s: by must be a whole number" % eff["add"], eff["add"])
        self._check_known(key, ev.ref)
        if key in self.state.retired:
            cur_whole = self.e.default(self.env, key)
        else:
            cur_whole = self._current(key)
        cur = (cur_whole or {}).get(part) if part else cur_whole
        if t == "enum":
            vals = d.get("values") or []
            idx = vals.index(cur) if cur in vals else 0
            new_idx = idx + int(by)
            if new_idx < 0 or new_idx >= len(vals):
                clamped = max(0, min(len(vals) - 1, new_idx))
                self.sink.warn("over-cap", "%s moved past the end of %s; clamped to %s"
                               % (eff["add"], vals, vals[clamped]), key=eff["add"], ref=ev.ref)
                if part:
                    self.overcap_keys.add(eff["add"])
                else:
                    self.overcap_keys.add(key)
                new_idx = clamped
            if new_idx > idx and not ev.kind:
                self._price(key, part, idx, new_idx, expected)
                costed.append(key)
            new = vals[new_idx]
        else:
            base = cur if is_number(cur) else 0
            new = base + by
            if t == "rating":
                new = int(new)
                if by > 0 and not ev.kind:
                    self._price(key, part, base, new, expected)
                    costed.append(key)
        if part:
            whole = dict(cur_whole) if isinstance(cur_whole, dict) else {}
            whole[part] = new
            self._store(key, whole, ev)
        else:
            self._store(key, new, ev)
        self._track_touch(key, part, t, touched_r, touched_n)
        self._apply_meta(key, eff)

    def _maybe_price(self, key, part, d, old, new, ev, expected, costed):
        if ev.kind == "creation":
            return
        t = d.get("type", "rating")
        if t == "rating" and is_number(old) and is_number(new) and new > old:
            self._price(key, part, old, new, expected)
            costed.append(key)
        elif t == "enum":
            vals = d.get("values") or []
            if old in vals and new in vals and vals.index(new) > vals.index(old):
                self._price(key, part, vals.index(old), vals.index(new), expected)
                costed.append(key)

    @staticmethod
    def _track_touch(key, part, t, touched_r, touched_n):
        if t == "rating":
            touched_r.append((key, part))
        elif t == "number" and not part:
            touched_n.append(key)

    def _bad(self, ev, msg, key=None):
        self.sink.warn("invalid-event", "%s: %s; effect skipped" % (ev.ref, msg), key=key, ref=ev.ref)

    def _op_gain(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        lname = eff["gain"].split(".", 1)[1]
        eid = eff["id"]
        if lname not in self.m.lists:
            self.sink.warn("unknown-trait", "list %s is not declared" % lname,
                           key=eff["gain"], ref=ev.ref)
        lst = self.state.lists.setdefault(lname, {})
        old = lst.get(eid)
        if old is not None and not old.retired:
            return self._bad(ev, "gain %s: entry %s is already live" % (eff["gain"], eid), eff["gain"])
        data = {"id": eid}
        for k, v in (eff.get("entry") or {}).items():
            if k != "id" and v is not None:
                data[k] = copy.deepcopy(v)
        refs = old.refs if old is not None else []
        if ev.ref not in refs:
            refs.append(ev.ref)
        entry = Entry(data, refs, ev.gm_only)
        if old is not None:
            del lst[eid]
        lst[eid] = entry
        self.state.bump()
        ld = self.m.lists.get(lname) or {}
        if "cost" in ld and ev.kind != "creation":
            amt = self.e.ev(self.env, ld["cost"], {"entry": dict(data)}, "lists.%s.cost" % lname)
            if is_number(amt) and amt:
                c = ld.get("currency") or self.m.currency
                expected[c] = expected.get(c, 0) + amt
                costed.append(eff["gain"])
        gained.append(lname)

    def _op_edit(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        target = eff["edit"]
        fields = eff["fields"]
        if target.startswith("list."):
            lname = target.split(".", 1)[1]
            e = (self.state.lists.get(lname) or {}).get(eff["id"])
            if e is None or e.retired:
                return self._bad(ev, "edit %s: no live entry %s" % (target, eff["id"]), target)
            for k, v in fields.items():
                if k == "id":
                    continue
                if v is None:
                    e.data.pop(k, None)
                else:
                    e.data[k] = copy.deepcopy(v)
            if ev.ref not in e.refs:
                e.refs.append(ev.ref)
            self.state.bump()
            return
        parsed = self._target(eff, "edit", ev)
        if not parsed:
            return
        key, part = parsed
        if part:
            return self._bad(ev, "edit targets a trait, not a part (%s)" % target, target)
        bad = [k for k in fields if k not in TRAIT_META]
        if bad:
            return self._bad(ev, "edit %s: only %s may be edited, not %s"
                             % (key, "/".join(TRAIT_META), ", ".join(bad)), key)
        if key not in self.state.values:
            return self._bad(ev, "edit %s: trait is %s" % (
                key, "retired" if key in self.state.retired else "not on the sheet"), key)
        self._apply_meta(key, fields)
        self._touch(key, ev.ref)
        self.state.bump()

    def _op_retire(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        target = eff["retire"]
        if target.startswith("list."):
            lname = target.split(".", 1)[1]
            e = (self.state.lists.get(lname) or {}).get(eff["id"])
            if e is None or e.retired:
                return self._bad(ev, "retire %s: no live entry %s" % (target, eff["id"]), target)
            e.retired = True
            if ev.ref not in e.refs:
                e.refs.append(ev.ref)
            self.state.bump()
            return
        parsed = self._target(eff, "retire", ev)
        if not parsed:
            return
        key, part = parsed
        if part:
            return self._bad(ev, "retire targets a trait, not a part (%s)" % target, target)
        if key not in self.state.values:
            return self._bad(ev, "retire %s: trait is %s" % (
                key, "already retired" if key in self.state.retired else "not on the sheet"), key)
        del self.state.values[key]
        self.state.retired.add(key)
        self._touch(key, ev.ref)
        self.state.bump()

    def _op_start(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        kind = eff["start"]
        sid = eff["id"]
        if sid in self.state.spans:
            return self._bad(ev, "start %s: span id %s already used" % (kind, sid), sid)
        if kind not in self.m.spans:
            self.sink.warn("unknown-trait", "span kind %s is not declared" % kind, key=kind, ref=ev.ref)
        sd = self.m.spans.get(kind) or {}
        name = eff.get("name") or sd.get("name") or kind.replace("_", " ").title()
        self.state.spans[sid] = Span(sid, kind, name, eff.get("note"), ev.date, [ev.ref], ev.gm_only)
        self.state.bump()

    def _op_end(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        sid = eff["id"]
        kind = eff["end"]
        if kind not in self.m.spans:
            self.sink.warn("unknown-trait", "span kind %s is not declared" % kind, key=kind, ref=ev.ref)
        sp = self.state.spans.get(sid)
        if sp is None or sp.end is not None:
            return self._bad(ev, "end %s: no open span %s" % (kind, sid), sid)
        if sp.kind != kind:
            return self._bad(ev, "end %s: span %s is a %s span" % (kind, sid, sp.kind), sid)
        sp.end = ev.date
        note = eff.get("note")
        if note:
            sp.note = note if not sp.note else "%s %s" % (sp.note, note)
        if ev.ref not in sp.refs:
            sp.refs.append(ev.ref)
        self.state.bump()

    def _op_anchor(self, eff, ev, expected, touched_r, touched_n, gained, costed):
        target = eff["anchor"]
        op = [a for a in ANCHOR_OPS if a in eff][0]
        rec = {"id": eff["id"], "key": target, op: eff[op], "date": ev.date, "ref": ev.ref,
               "satisfied": False, "folded": None, "satisfied_by": [], "_op": op,
               "_applies": False, "_pos": ev.pos, "_gm": bool(ev.gm_only)}
        self.anchors.append(rec)
        st = self.state
        if op == "has":
            lname = target.split(".", 1)[1]
            if lname not in self.m.lists:
                self.sink.warn("unknown-trait", "anchor %s: list %s is not declared"
                               % (eff["id"], lname), key=target, ref=ev.ref)
            e = (st.lists.get(lname) or {}).get(eff["has"])
            live = e is not None and not e.retired
            rec["folded"] = live
            rec["satisfied"] = live
            return
        parsed = self.m.parse_target(target)
        td = self.m.tdef(parsed[0]) if parsed and parsed[1] is None else None
        ok = td is not None and (
            (op in ("at_least", "at_most") and td.type in ("rating", "number", "enum"))
            or (op == "is" and td.type in ("text", "enum")))
        if not ok:
            self.sink.warn("unknown-trait", "anchor %s: %s cannot anchor %s"
                           % (eff["id"], op, target), key=target, ref=ev.ref)
            return
        if not td.known:
            self.sink.warn("unknown-trait", "anchor %s: %s is not declared" % (eff["id"], target),
                           key=target, ref=ev.ref)
        if op == "is" and td.type == "enum" and eff["is"] not in (td.get("values") or []):
            self.sink.warn("unknown-trait", "anchor %s: %r is not a value of %s"
                           % (eff["id"], eff["is"], target), key=target, ref=ev.ref)
            return
        rec["_applies"] = True
        folded = st.values[target] if target in st.values else self.e.default(self.env, target)
        rec["folded"] = folded
        cmp = folded
        if td.type == "enum" and op != "is":
            vals = td.get("values") or []
            cmp = vals.index(folded) if folded in vals else None
        if op == "at_least":
            rec["satisfied"] = is_number(cmp) and cmp >= eff[op]
        elif op == "at_most":
            rec["satisfied"] = is_number(cmp) and cmp <= eff[op]
        else:
            rec["satisfied"] = folded == eff["is"]

    # -- active sets
    def active_sets(self):
        out = {}
        st = self.state
        groups = {}
        for k in self.m.traits:
            groups.setdefault(self.m.class_of(k), []).append(k)
        for k in st.values:
            c = self.m.class_of(k)
            if k not in groups.setdefault(c, []):
                groups[c].append(k)
        for c, keys in groups.items():
            has = False
            act = set()
            for k in keys:
                a = self.e.active(self.env, k)
                if a is None:
                    continue
                has = True
                if a:
                    act.add(k)
            if has:
                out[c] = act
        return out

    def _active_change(self, before, after, ev):
        for c in list(dict.fromkeys(list(before) + list(after))):
            b = before.get(c, set())
            a = after.get(c, set())
            if a == b:
                continue
            gone = sorted(b - a, key=lambda k: self._decl_order(k))
            new = sorted(a - b, key=lambda k: self._decl_order(k))
            name = (self.m.classes.get(c) or {}).get("name") or (c or "traits")
            parts = []
            if gone:
                parts.append("%s now inactive" % ", ".join(k.split(".")[-1] for k in gone))
            need = [k for k in new if k not in self.state.values]
            have = [k for k in new if k in self.state.values]
            if need:
                parts.append("%s need explicit values" % ", ".join(k.split(".")[-1] for k in need))
            if have:
                parts.append("%s now active" % ", ".join(k.split(".")[-1] for k in have))
            self.sink.warn("inactive-trait", "%s active set changed: %s (nothing converted)"
                           % (name, "; ".join(parts)), ref=ev.ref)

    def _decl_order(self, k):
        keys = list(self.m.traits)
        return (keys.index(k) if k in keys else len(keys), k)


def _coerce(t, d, v):
    """Validate a ``set`` value for a type → (value, error|None)."""
    if t == "rating":
        if isinstance(v, bool) or not is_number(v) or v != int(v):
            return None, "rating needs a whole number, got %r" % (v,)
        return int(v), None
    if t == "number":
        if isinstance(v, bool) or not is_number(v):
            return None, "number needs a number, got %r" % (v,)
        return v, None
    if t == "enum":
        vals = d.get("values") or []
        if v not in vals:
            return None, "%r is not one of %s" % (v, vals)
        return v, None
    if t == "text":
        if v is not None and not isinstance(v, str):
            return None, "text needs a string, got %r" % (v,)
        return v, None
    if t == "relation":
        if isinstance(v, str):
            return {"ref": v, "name": v}, None
        if not isinstance(v, dict):
            return None, "relation needs {ref, name}, got %r" % (v,)
        return {"ref": v.get("ref"), "name": v.get("name")}, None
    return None, "cannot set a %s" % t


# ------------------------------------------------------------------ result

class FoldResult:
    pass


def span_years(span, at_end_key, latest_key):
    start = dates.years(span.start)
    if span.end is not None:
        end = dates.years(span.end)
    elif at_end_key is not None:
        end = dates.years_of_key(at_end_key)
    elif latest_key is not None:
        end = dates.years_of_key(latest_key)
    else:
        end = start
    return end - start


def run_fold(sheet, at=None, sink=None):
    """Fold the sheet's ledger (optionally up to ``at``) → FoldResult."""
    model = sheet.model
    sink = sink or Sink()
    for w in sheet.file_warnings:
        sink.warn(w["code"], w["message"])
    engine = Engine(model, sink)
    notices = []
    for rk in ("modifiers", "tallies"):
        if model.raw_rules.get(rk):
            notices.append({"code": "reserved-unimplemented",
                            "message": "rules.%s is reserved for a later layer and ignored" % rk})
    events = collect_events(sheet, sink)
    at_end_key = dates.at_end(at) if at is not None else None
    if at_end_key is not None:
        events = [e for e in events if e.key <= at_end_key]
    for i, e in enumerate(events):
        e.pos = i
    creation = [e for e in events if e.kind == "creation"]
    first_creation = creation[0].order() if creation else None

    # creation state (quiet)
    cstate = None
    if creation:
        cengine = Engine(model, NullSink())
        cf = Folder(cengine)
        for e in creation:
            cf.apply_event(e)
        cstate = cf.state

    folder = Folder(engine, first_creation)
    for e in events:
        folder.apply_event(e)
    state = folder.state

    # satisfies
    by_id = {}
    for a in folder.anchors:
        by_id.setdefault(a["id"], []).append(a)
    for aid, ref in folder.satisfies:
        for a in by_id.get(aid, []):
            if ref not in a["satisfied_by"]:
                a["satisfied_by"].append(ref)

    ref_pos = {e.ref: e.pos for e in events}
    astate = anchor_state(engine, state, folder.anchors, ref_pos)

    latest_key = events[-1].key if events else None
    res = FoldResult()
    res.sheet = sheet
    res.model = model
    res.engine = engine
    res.sink = sink
    res.at = at
    res.at_end = at_end_key
    res.latest_key = latest_key
    res.events = events
    res.state = state
    res.astate = astate
    res.cstate = cstate
    res.anchors = folder.anchors
    res.expected = folder.expected
    res.ref_pos = ref_pos
    res.gm_refs = {e.ref for e in events if e.gm_only}
    res.anchor_refs = {e.ref for e in events if e.has_anchor}
    res.notices = notices
    res.aenv = engine.env(astate)
    final_sweep(res, folder)
    res.warnings = sink.warnings
    return res


def anchor_state(engine, state, anchors, ref_pos):
    m = engine.model
    astate = state.copy()
    env = engine.env(state)
    per_key = {}
    for a in anchors:
        if a["_applies"]:
            per_key.setdefault(a["key"], []).append(a)
    for key, lst in per_key.items():
        td = m.tdef(key)
        present = key in state.values
        base = state.values[key] if present else engine.default(env, key)
        vals = td.get("values") or []
        is_enum = td.type == "enum"

        def to_n(v):
            if is_enum:
                return vals.index(v) if v in vals else None
            return v

        v = base
        lifted = []
        lo = [a for a in lst if a["_op"] == "at_least"]
        hi = [a for a in lst if a["_op"] == "at_most"]
        iss = [a for a in lst if a["_op"] == "is"]
        if lo or hi:
            n = to_n(base)
            n0 = n
            if lo:
                mx = max(a["at_least"] for a in lo)
                if not is_number(n) or mx > n:
                    n = mx
                    lifted = [a["ref"] for a in lo if a["at_least"] == mx]
            if hi:
                mn = min(a["at_most"] for a in hi)
                if not is_number(n) or mn < n:
                    n = mn
                    lifted = [a["ref"] for a in hi if a["at_most"] == mn]
            if n != n0:
                n = normalise(n)
                if is_enum:
                    v = vals[max(0, min(len(vals) - 1, int(n)))] if vals else None
                elif td.type == "rating":
                    v = int(n)
                else:
                    v = n
        if iss:
            last = iss[-1]
            if v != last["is"]:
                v = last["is"]
                lifted = [last["ref"]]
        if v != base:
            if not present:
                # The anchor makes the key present (S7.6). A retired trait comes back
                # fresh (S5): no stale name/note/gm_only meta. A key created only by
                # gm_only anchor events inherits gm_only (S8).
                astate.meta.pop(key, None)
                gm_refs = {a["ref"] for a in lst if a.get("_gm")}
                if lifted and all(r in gm_refs for r in lifted):
                    astate.gm_created.add(key)
                else:
                    astate.gm_created.discard(key)
            astate.values[key] = v
            astate.retired.discard(key)
            refs = astate.refs.setdefault(key, [])
            for r in lifted:
                if r not in refs:
                    refs.append(r)
            refs.sort(key=lambda r: ref_pos.get(r, 0))
    astate.bump()
    return astate


def final_sweep(res, folder):
    engine = res.engine
    m = res.model
    sink = res.sink
    st = res.astate
    env = res.aenv
    engine.current_ref = None
    # over-cap: ratings
    for key in list(st.values):
        td = m.tdef(key)
        if td.type == "rating":
            if key in folder.overcap_keys:
                continue
            v = st.values[key]
            lo, hi = engine.bounds(env, key)
            if is_number(v) and is_number(hi) and v > hi:
                sink.warn("over-cap", "%s is %s, above max %s" % (key, _fmt(v), _fmt(hi)), key=key)
            elif is_number(v) and is_number(lo) and v < lo:
                sink.warn("over-cap", "%s is %s, below min %s" % (key, _fmt(v), _fmt(lo)), key=key)
        elif td.type == "compound":
            for p, pd in (td.get("parts") or {}).items():
                wkey = "%s.%s" % (key, p)
                if pd.get("type", "rating") != "rating" or wkey in folder.overcap_keys:
                    continue
                v = (st.values[key] or {}).get(p)
                lo, hi = engine.bounds(env, key, p)
                if is_number(v) and is_number(hi) and v > hi:
                    sink.warn("over-cap", "%s is %s, above max %s" % (wkey, _fmt(v), _fmt(hi)), key=wkey)
                elif is_number(v) and is_number(lo) and v < lo:
                    sink.warn("over-cap", "%s is %s, below min %s" % (wkey, _fmt(v), _fmt(lo)), key=wkey)
    # over-cap: lists
    for lname, ld in m.lists.items():
        if "cap" not in ld or lname in folder.list_overcap:
            continue
        cap = engine.ev(env, ld["cap"], {}, "lists.%s.cap" % lname)
        n = len(st.live_entries(lname))
        if is_number(cap) and n > cap:
            sink.warn("over-cap", "list.%s has %d entries, cap %s" % (lname, n, _fmt(cap)),
                      key="list.%s" % lname)
    # inactive traits
    for key in list(st.values):
        a = engine.active(env, key)
        if a is False:
            sink.warn("inactive-trait", "%s is on the sheet but inactive" % key, key=key)
    # anchors
    for a in res.anchors:
        if not a["satisfied"]:
            what = a[a["_op"]]
            sink.warn("unsatisfied-anchor", "anchor %s: %s %s %s not reached by %s (folded %s)"
                      % (a["id"], a["key"], a["_op"], _fmt(what), a["date"], _fmt(a["folded"])),
                      key=a["key"], ref=a["ref"])
    # creation budgets
    if res.cstate is not None:
        creation_budgets(res)
    # notices
    for code, nd in m.notices.items():
        scope = nd.get("scope", "sheet")
        msg = nd.get("message", code)
        if scope == "sheet":
            if engine.ev(env, nd["when"], {}, "notices.%s.when" % code):
                res.notices.append({"code": code, "message": msg})
        else:
            kind = scope.split(":", 1)[1]
            for sp in st.spans.values():
                if sp.kind != kind:
                    continue
                loc = {"span_id": sp.id, "span_open": sp.end is None, "span_note": sp.note,
                       "span_years": round(span_years(sp, res.at_end, res.latest_key), 2)}
                if engine.ev(env, nd["when"], loc, "notices.%s.when" % code):
                    res.notices.append({"code": code, "message": msg, "span": sp.id,
                                        "ref": sp.refs[0]})


def _step_spend(engine, env, key, value_n, base_n, budget, site):
    if value_n >= base_n:
        if value_n - base_n > MAX_STEPS:
            engine.sink.expr_error(site, "%s: %d steps above base (more than %d)"
                                   % (key, value_n - base_n, MAX_STEPS))
            return 0
        total = 0
        c = base_n
        while c < value_n:
            if "step_cost" in budget:
                loc = dict(engine.tlocal(key), current=c, target=c + 1)
                sc = engine.ev(env, budget["step_cost"], loc, site + ".step_cost")
                total += sc if is_number(sc) else 0
            else:
                total += 1
            c += 1
        return total
    return -(base_n - value_n)


def trait_spend(engine, env, key, budget, site):
    m = engine.model
    td = m.tdef(key)
    v = env.state.values.get(key)
    if td.type not in ("rating", "number", "enum"):
        return 0
    loc = engine.tlocal(key)
    if "base" in budget:
        base = engine.ev(env, budget["base"], loc, site + ".base")
    elif "base" in td.d:
        base = engine.ev(env, td.d["base"], loc, engine.site(td, "base"))
    else:
        base = engine.default(env, key)
    if td.type == "enum":
        vals = td.get("values") or []
        v = vals.index(v) if v in vals else None
        if isinstance(base, str):
            base = vals.index(base) if base in vals else None
    if not is_number(v) or not is_number(base):
        return 0
    return _step_spend(engine, env, key, int(v), int(base), budget, site)


def creation_budgets(res):
    engine = res.engine
    m = res.model
    sink = res.sink
    env = engine.env(res.cstate)
    cst = res.cstate
    cr = m.creation
    budgets = cr.get("budgets") or {}
    fr = cr.get("freebies")
    fcost = (fr or {}).get("cost") or {}
    freebies = 0
    for bid, b in budgets.items():
        site = "creation.budgets.%s" % bid
        cls = b.get("class")
        slots = []  # (label, allowance, spend)
        spent_traits = []
        if cls:
            keys = [k for k in cst.values if m.class_of(k) == cls]
        elif "keys" in b:
            keys = [k for k in (b.get("keys") or []) if k in cst.values]
        else:
            keys = []
        per = {k: trait_spend(engine, env, k, b, site) for k in keys}
        spent_traits = [k for k in keys if per[k] > 0]
        if "list" in b:
            lname = b["list"]
            if "spend" in b:
                sp = engine.ev(env, b["spend"], {}, site + ".spend")
                sp = sp if is_number(sp) else 0
            else:
                sp = len(cst.live_entries(lname))
            total = engine.ev(env, b.get("total"), {}, site + ".total")
            slots.append((bid, total, sp))
        elif "priority" in b:
            groups = m.class_groups(cls)
            gs = {g: 0 for g in groups}
            for k in keys:
                g = m.trait_group(k, cst.meta.get(k))
                if g in gs:
                    gs[g] += per[k]
            spends = sorted(gs.items(), key=lambda kv: -kv[1])
            prios = sorted(b["priority"], reverse=True)
            for (g, sp), pr in zip(spends, prios):
                slots.append(("%s (%s)" % (bid, g), pr, sp))
        else:
            total = engine.ev(env, b.get("total"), {}, site + ".total")
            slots.append((bid, total, sum(per.values())))
        for label, allow, sp in slots:
            if not is_number(allow):
                continue
            sp = normalise(sp)
            if sp < allow:
                sink.warn("creation-budget", "budget %s: spent %s of %s (%s under)"
                          % (label, _fmt(sp), _fmt(allow), _fmt(allow - sp)))
            elif sp > allow:
                over = sp - allow
                c = fcost.get(bid, fcost.get(cls) if cls else None)
                if not is_number(c):
                    sink.warn("creation-budget", "budget %s: spent %s of %s (%s over, no freebie cost)"
                              % (label, _fmt(sp), _fmt(allow), _fmt(over)))
                else:
                    freebies += over * c
        if "where" in b:
            for k in spent_traits:
                if not engine.ev(env, b["where"], engine.tlocal(k), site + ".where"):
                    sink.warn("creation-budget", "budget %s: %s spent outside where" % (bid, k), key=k)
    total = 0
    if fr is not None and "total" in fr:
        total = engine.ev(env, fr["total"], {}, "creation.freebies.total")
        total = total if is_number(total) else 0
    if normalise(freebies) != normalise(total):
        sink.warn("creation-budget", "freebies: spent %s of %s" % (_fmt(freebies), _fmt(total)))
    for cid, ch in (cr.get("checks") or {}).items():
        if engine.ev(env, ch["when"], {}, "creation.checks.%s.when" % cid):
            sink.warn("creation-budget", "check %s: %s" % (cid, ch.get("message", cid)))
