"""Tick rules: flows, capacities, transitions, rolls, occurrences (record
``docs/plans/2026-11-25-sheet-ticks-flows.md``). Load-time validation and
compilation only; the simulation lives in ``tick.py``.

Rules keys (all optional; a pack without them never ticks)::

    "capacities": {
      "labour": {"amount": EXPR},                                  # pooled, resets daily
      "care":   {"providers": LIST, "amount": EXPR, "keys": EXPR}},# per provider entry
    "flows": {ID: FLOW},
    "occurrences": {NAME: {"flows": {ID: FLOW}}},                  # impulses, once per firing
    "transitions": {LIST: {ID: {"field": "progress", "at": EXPR,
                                "effects": [EFFECT...], "roll": TEXT}}},
    "rolls": {ID: {"when": EXPR, "message": TEXT, "scope": "sheet" | "list:NAME"}}

    FLOW = {"priority": N, "active": EXPR,
            "for_each": LIST | "mounts.KIND", "where": EXPR, "order": EXPR,
            "consume": {TARGET: EXPR | {"need": EXPR, "from": [[SOURCE, RATIO, {"above": EXPR}]]}},
            "needs":   {CAPACITY: {"amount": EXPR, "key": EXPR, "assign": "sticky" | "daily",
                                   "field": NAME}},
            "produce": {TARGET: EXPR},
            "short": TARGET, "substituted": TARGET}

A TARGET is a trait key, ``entry.FIELD`` (a list ``for_each``), ``child.KEY``
(a ``mounts.KIND`` for_each), ``mount.KIND.ID.KEY``, or (consume only) a
pooled capacity id.
"""
from .expr import RESERVED, SheetError, compile_slot, valid_key, valid_segment

FLOW_KEYS = ("priority", "active", "for_each", "where", "order", "consume", "needs",
             "produce", "short", "substituted", "note", "name")


class Target:
    """Where a flow reads or writes a quantity."""
    __slots__ = ("kind", "key", "mount", "src")

    def __init__(self, kind, key, mount=None, src=""):
        self.kind = kind    # trait | entry | child | mount | capacity
        self.key = key      # trait key / entry field / capacity id
        self.mount = mount  # (kind, id) for mount targets
        self.src = src

    def __repr__(self):
        return "Target(%s)" % self.src


def parse_target(src, site, model, each, caps, allow_cap):
    if not isinstance(src, str) or not valid_key(src):
        raise SheetError("%s: invalid target %r" % (site, src))
    segs = src.split(".")
    if segs[0] == "entry":
        if each is None or each[0] != "list" or len(segs) != 2:
            raise SheetError("%s: entry.FIELD needs a list for_each (%r)" % (site, src))
        return Target("entry", segs[1], src=src)
    if segs[0] == "child":
        if each is None or each[0] != "mounts" or len(segs) < 2:
            raise SheetError("%s: child.KEY needs a mounts.KIND for_each (%r)" % (site, src))
        chain, key = _chain(segs[1:], site, src)
        return Target("child", key, chain, src=src)
    if segs[0] == "mount":
        chain, key = _chain(segs, site, src)
        return Target("mount", key, chain, src=src)
    if src in caps:
        if not allow_cap:
            raise SheetError("%s: capacity %s can only be consumed" % (site, src))
        if "providers" in caps[src]:
            raise SheetError("%s: %s has providers; ask for it under needs" % (site, src))
        return Target("capacity", src, src=src)
    if segs[0] in RESERVED or segs[0] == "list":
        raise SheetError("%s: %r is not a stock" % (site, src))
    return Target("trait", src, src=src)


def _chain(segs, site, src):
    """``mount.K.I.mount.K2.I2.key`` → ``([(K, I), (K2, I2)], "key")`` (any depth)."""
    chain = []
    while segs and segs[0] == "mount":
        if len(segs) < 4:
            raise SheetError("%s: mount target needs mount.KIND.ID.KEY (%r)" % (site, src))
        chain.append((segs[1], segs[2]))
        segs = segs[3:]
    if not segs or segs[0] in RESERVED:
        raise SheetError("%s: %r does not end in a stock" % (site, src))
    return chain, ".".join(segs)


class Flow:
    def __init__(self, fid, d, site, model, caps):
        if not isinstance(d, dict):
            raise SheetError("%s must be an object" % site)
        bad = [k for k in d if k not in FLOW_KEYS]
        if bad:
            raise SheetError("%s: unknown key(s) %s" % (site, ", ".join(sorted(bad))))
        self.id = fid
        self.site = site
        pr = d.get("priority", 100)
        if isinstance(pr, bool) or not isinstance(pr, (int, float)):
            raise SheetError("%s.priority must be a number" % site)
        self.priority = pr
        self.active = compile_slot(d["active"], site + ".active") if "active" in d else None
        fe = d.get("for_each")
        self.each = None
        if fe is not None:
            if not isinstance(fe, str):
                raise SheetError("%s.for_each must be a string" % site)
            if fe.startswith("mounts."):
                kind = fe.split(".", 1)[1]
                if kind not in model.mounts:
                    raise SheetError("%s.for_each: unknown mount kind %r" % (site, kind))
                self.each = ("mounts", kind)
            else:
                if fe not in model.lists:
                    raise SheetError("%s.for_each: unknown list %r" % (site, fe))
                self.each = ("list", fe)
        for k in ("where", "order"):
            if k in d and self.each is None:
                raise SheetError("%s.%s needs for_each" % (site, k))
        self.where = compile_slot(d["where"], site + ".where") if "where" in d else None
        self.order = compile_slot(d["order"], site + ".order") if "order" in d else None
        self.consume = []  # (Target, amount) or (None, Diet)
        for t, v in _obj(d, "consume", site).items():
            s2 = "%s.consume.%s" % (site, t)
            if isinstance(v, dict):
                self.consume.append(Diet(t, v, s2, model, self.each, caps))
            else:
                self.consume.append(Simple(parse_target(t, s2, model, self.each, caps, True),
                                           compile_slot(v, s2)))
        self.needs = []
        for cid, v in _obj(d, "needs", site).items():
            s2 = "%s.needs.%s" % (site, cid)
            if cid not in caps or "providers" not in caps[cid]:
                raise SheetError("%s: needs must name a capacity with providers" % s2)
            if not isinstance(v, dict) or "amount" not in v:
                raise SheetError("%s needs amount" % s2)
            assign = v.get("assign", "sticky")
            if assign not in ("sticky", "daily"):
                raise SheetError("%s.assign must be sticky or daily" % s2)
            if assign == "sticky" and (self.each is None or self.each[0] != "list"):
                raise SheetError("%s: sticky assignment needs a list for_each "
                                 "(the pairing is kept on the entry)" % s2)
            field = v.get("field", "assigned_%s" % cid)
            if not isinstance(field, str) or not valid_segment(field):
                raise SheetError("%s.field must be a field name" % s2)
            self.needs.append(Need(cid, compile_slot(v["amount"], s2 + ".amount"),
                                   compile_slot(v["key"], s2 + ".key") if "key" in v else None,
                                   assign, field))
        self.produce = []
        for t, v in _obj(d, "produce", site).items():
            s2 = "%s.produce.%s" % (site, t)
            self.produce.append(Simple(parse_target(t, s2, model, self.each, caps, False),
                                       compile_slot(v, s2)))
        self.short = parse_target(d["short"], site + ".short", model, self.each, caps, False) \
            if "short" in d else None
        self.substituted = parse_target(d["substituted"], site + ".substituted", model,
                                        self.each, caps, False) if "substituted" in d else None
        if self.substituted is not None and not any(isinstance(c, Diet) for c in self.consume):
            raise SheetError("%s.substituted needs a diet (need/from) under consume" % site)


class Simple:
    __slots__ = ("target", "amount")

    def __init__(self, target, amount):
        self.target = target
        self.amount = amount


class Need:
    __slots__ = ("cap", "amount", "key", "assign", "field")

    def __init__(self, cap, amount, key, assign, field):
        self.cap = cap
        self.amount = amount
        self.key = key
        self.assign = assign
        self.field = field


class Diet:
    """A need filled from ranked sources: ``[[source, ratio, {"above": expr}], ...]``."""

    def __init__(self, label, d, site, model, each, caps):
        if "need" not in d or not isinstance(d.get("from"), list) or not d["from"]:
            raise SheetError("%s needs need and a non-empty from list" % site)
        self.label = label
        self.need = compile_slot(d["need"], site + ".need")
        self.sources = []
        for i, src in enumerate(d["from"]):
            s2 = "%s.from[%d]" % (site, i)
            if isinstance(src, str):
                src = [src]
            if not isinstance(src, list) or not 1 <= len(src) <= 3:
                raise SheetError("%s must be [source, ratio?, {above?}]" % s2)
            t = parse_target(src[0], s2, model, each, caps, True)
            ratio = compile_slot(src[1] if len(src) > 1 else 1, s2 + ".ratio")
            opts = src[2] if len(src) > 2 else {}
            if not isinstance(opts, dict) or any(k != "above" for k in opts):
                raise SheetError("%s options may only hold above" % s2)
            above = compile_slot(opts["above"], s2 + ".above") if "above" in opts else None
            self.sources.append((t, ratio, above))


class TickRules:
    def __init__(self, model):
        r = model.rules
        self.capacities = {}
        for cid, c in _obj(r, "capacities", "rules").items():
            site = "capacities.%s" % cid
            if not valid_segment(cid) or cid in RESERVED:
                raise SheetError("rules: invalid capacity id %r" % cid)
            if cid in model.traits or cid in model.derived:
                raise SheetError("%s collides with a trait or derived key" % site)
            if not isinstance(c, dict) or "amount" not in c:
                raise SheetError("%s needs amount" % site)
            cc = {"amount": compile_slot(c["amount"], site + ".amount")}
            if "providers" in c:
                if c["providers"] not in model.lists:
                    raise SheetError("%s.providers: unknown list %r" % (site, c["providers"]))
                cc["providers"] = c["providers"]
                cc["keys"] = compile_slot(c["keys"], site + ".keys") if "keys" in c else None
            elif "keys" in c:
                raise SheetError("%s.keys needs providers" % site)
            self.capacities[cid] = cc
        self.flows = [Flow(fid, d, "flows.%s" % fid, model, self.capacities)
                      for fid, d in _obj(r, "flows", "rules").items()]
        self.flows.sort(key=lambda f: (f.priority, f.id))
        self.occurrences = {}
        for name, od in _obj(r, "occurrences", "rules").items():
            site = "occurrences.%s" % name
            if not valid_segment(name) or not isinstance(od, dict):
                raise SheetError("rules: invalid occurrence %r" % name)
            fl = [Flow(fid, d, "%s.flows.%s" % (site, fid), model, self.capacities)
                  for fid, d in _obj(od, "flows", site).items()]
            fl.sort(key=lambda f: (f.priority, f.id))
            roll = od.get("roll")
            if roll is not None and not isinstance(roll, str):
                raise SheetError("%s.roll must be text" % site)
            self.occurrences[name] = {"flows": fl, "roll": roll}
        self.transitions = {}
        for lname, ts in _obj(r, "transitions", "rules").items():
            if lname not in model.lists or not isinstance(ts, dict):
                raise SheetError("transitions.%s: unknown list" % lname)
            out = []
            for tid, t in ts.items():
                site = "transitions.%s.%s" % (lname, tid)
                if not isinstance(t, dict) or "at" not in t:
                    raise SheetError("%s needs at" % site)
                effs = t.get("effects", [])
                if not isinstance(effs, list) or not all(isinstance(e, dict) for e in effs):
                    raise SheetError("%s.effects must be a list of effects" % site)
                for e in effs:
                    for k in ("by_expr", "to_expr"):
                        if k in e:
                            e[k] = compile_slot(e[k], "%s.effects.%s" % (site, k))
                roll = t.get("roll")
                if roll is not None and not isinstance(roll, str):
                    raise SheetError("%s.roll must be text" % site)
                out.append({"id": tid, "field": t.get("field", "progress"),
                            "at": compile_slot(t["at"], site + ".at"),
                            "effects": effs, "roll": roll})
            self.transitions[lname] = out
        self.rolls = {}
        for rid, rd in _obj(r, "rolls", "rules").items():
            site = "rolls.%s" % rid
            if not isinstance(rd, dict) or "when" not in rd:
                raise SheetError("%s needs when" % site)
            scope = rd.get("scope", "sheet")
            if scope != "sheet" and not (isinstance(scope, str) and scope.startswith("list:")
                                         and scope[5:] in model.lists):
                raise SheetError("%s.scope must be sheet or list:NAME" % site)
            self.rolls[rid] = {"when": compile_slot(rd["when"], site + ".when"),
                               "message": str(rd.get("message", rid)), "scope": scope}

    @property
    def empty(self):
        return not (self.flows or self.occurrences or self.transitions or self.rolls)


def _obj(d, key, site):
    v = d.get(key)
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise SheetError("%s: %s must be an object" % (site, key))
    return v
