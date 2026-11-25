"""The tick: advance a sheet (and its mounted subtree) through time, day by
day, and write what the flows produced as ordinary ledger events (record
``docs/plans/2026-11-25-sheet-ticks-flows.md``).

Doctrine:
* **Stored as paid.** The written numbers stand; later ledger edits never
  rewrite an old tick.
* **The tick never rolls.** It reports rolls that came due and keeps going.
* **One file per tick per ledger** (``history/tick-<id>.json``); retracting a
  tick is deleting those files.

One day, for the whole tree:
  1. ledger events dated that day are applied (children first);
  2. dawn: capacities reset, providers offer their hours;
  3. occurrences fire (root only), then flows by priority (children's flows
     first). Rates are read from the dawn state; availability from working
     balances, so earlier priorities are served first;
  4. balances are written back; stocks over their ``max`` overflow;
  5. transitions fire where an entry field crossed its threshold;
  6. rolls whose ``when`` turned true are flagged;
  7. on checkpoint days the difference between the simulation and the ledger
     (a shadow fold of the ledger plus everything this tick wrote) is written.

``shortcut: daily stepping only; event-driven jumps (solve for the next change)
are unbuilt. Add them when a benchmark says the stepper is too slow, and keep
the stepper as the reference they must match.``
``shortcut: the simulation folds without anchors (the unanchored state).``
"""
import copy
import math
import os
import re

from .expr import ExprError, SheetError, is_number, normalise
from .flows import Diet
from .fold import Engine, Event, Folder, NullSink, Sink, StateEnv, check_event, collect_events
from .mounts import MountContext, live_mounts, namespace_of

EPS = 1e-9
CHECKPOINTS = ("day", "week", "month", "skip")
_TPL = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class TickError(SheetError):
    pass


def _num(v):
    return v if is_number(v) and not isinstance(v, bool) else 0


class Report:
    def __init__(self):
        self.flows = {}       # sheet -> flow -> {runs, short_days}
        self.overflow = {}    # sheet -> stock -> amount
        self.transitions = []
        self.owed = []
        self.hours = {}       # sheet -> cap -> provider -> flow -> hours
        self.assignments = []
        self.warnings = []
        self.stocks = {}      # sheet -> key -> [start, end]
        self.files = []


# ------------------------------------------------------------------ sim

class Sim:
    """One sheet of the tick tree: a simulated fold and a shadow of the ledger."""

    def __init__(self, sheet, tick, path_stack):
        if tick.ignore:
            sheet = sheet.with_history([hf for hf in sheet.history if hf.stem not in tick.ignore])
        self.sheet = sheet
        self.tick = tick
        self.model = sheet.model
        self.rules = sheet.model.tick
        self.cal = sheet.calendar
        self.name = sheet.id or os.path.basename(sheet.dir)
        quiet = Engine(self.model, NullSink(), self.cal)
        self.loud = Engine(self.model, tick.sink, self.cal)
        events = collect_events(sheet, NullSink())
        creation = [e for e in events if e.kind == "creation"]
        first = creation[0].order() if creation else None
        self.folder = Folder(quiet, first)
        self.shadow = Folder(Engine(self.model, NullSink(), self.cal), first)
        self.env = StateEnv(self.loud, self.folder.state)
        ctx = MountContext(sheet, None, provider=self.child_ns)
        for eng in (quiet, self.loud, self.shadow.e):
            eng.mount_ctx = ctx
        self.events = [(self.cal.day_of_key(e.key), e) for e in events]
        self.ev_i = 0
        self.children = {}  # path -> Sim
        self.out = []
        self.n_out = 0
        stack = path_stack + [sheet.path]
        for path in self.mount_paths(tick.end):
            if path in stack:
                raise TickError("mount cycle: %s" % " -> ".join(stack + [path]))
            from .loader import load_sheet
            self.children[path] = Sim(load_sheet(path), tick, stack)

    def mount_paths(self, end):
        out = []
        for day, e in self.events:
            if day > end:
                break
            for eff in e.effects:
                if "mount" in eff:
                    p = self.path_of(eff["ref"])
                    if p not in out:
                        out.append(p)
        return out

    def path_of(self, ref):
        p = os.path.normpath(os.path.join(self.sheet.dir, ref))
        if os.path.isdir(p):
            p = os.path.join(p, "sheet.json")
        return os.path.abspath(p)

    def walk(self):
        """Post-order: children before parents."""
        for c in self.children.values():
            yield from c.walk()
        yield self

    def child_of(self, mt):
        return self.children.get(self.path_of(mt.ref))

    def child_ns(self, mt):
        c = self.child_of(mt)
        if c is None:
            return None
        st = c.folder.state
        if c._ns is None or c._ns[0] != st.version:
            c._ns = (st.version, namespace_of(c.env, c.model, c.sheet.name, mt.id))
        return c._ns[1]

    _ns = None

    # -- ledger
    def apply_until(self, day, both=True):
        while self.ev_i < len(self.events) and self.events[self.ev_i][0] <= day:
            e = self.events[self.ev_i][1]
            self.folder.apply_event(e)
            if both:
                self.shadow.apply_event(e)
            self.ev_i += 1

    def set_today(self, day):
        for eng in (self.folder.e, self.loud, self.shadow.e):
            eng.today = day

    # -- balances
    def dawn(self):
        self.bal = {}
        self.dawn_vals = {}
        self.caps = {}
        self.providers = {}
        for cid, c in self.rules.capacities.items():
            site = "capacities.%s" % cid
            if "providers" not in c:
                self.caps[cid] = max(0, _num(self.ev(c["amount"], {}, site + ".amount")))
                continue
            offers = {}
            for row in self.env.list_view().get(c["providers"], []):
                loc = {"entry": row}
                budget = max(0, _num(self.ev(c["amount"], loc, site + ".amount")))
                keys = self.ev(c["keys"], loc, site + ".keys") if c.get("keys") else None
                if isinstance(keys, list):
                    keys = {k: 1 for k in keys if isinstance(k, str)}
                elif isinstance(keys, dict):
                    keys = {k: v for k, v in keys.items() if is_number(v) and v > 0}
                else:
                    keys = {}
                offers[row["id"]] = [budget, keys]
            self.providers[cid] = offers

    def ev(self, slot, local, site):
        return self.loud.ev(self.env, slot, local, site)

    def _read(self, bk):
        st = self.folder.state
        if bk[0] == "t":
            v = st.values.get(bk[1])
            if v is None:
                v = self.folder.e.default(self.folder.env, bk[1])
            return v
        e = (st.lists.get(bk[1]) or {}).get(bk[2])
        return None if e is None else e.data.get(bk[3])

    def get(self, bk):
        if bk not in self.bal:
            v = self._read(bk)
            self.bal[bk] = v
            self.dawn_vals[bk] = v
        return self.bal[bk]

    def add(self, bk, d):
        self.bal[bk] = _num(self.get(bk)) + d

    def write_back(self):
        st = self.folder.state
        for bk, v in self.bal.items():
            if v == self.dawn_vals.get(bk) and bk in self.dawn_vals:
                continue
            if bk[0] == "t":
                st.values[bk[1]] = v
                st.retired.discard(bk[1])
            else:
                e = (st.lists.get(bk[1]) or {}).get(bk[2])
                if e is not None and not e.retired:
                    e.data[bk[3]] = v
        st.bump()

    def overflow(self, report):
        for bk in list(self.bal):
            if bk[0] != "t":
                continue
            td = self.model.tdef(bk[1])
            if "max" not in td.d:
                continue
            lo, hi = self.folder.e.bounds(self.folder.env, bk[1])
            v = self.bal[bk]
            if not is_number(hi) or not is_number(v) or v <= hi + EPS:
                continue
            excess = v - hi
            self.bal[bk] = hi
            ov = report.overflow.setdefault(self.name, {})
            ov[bk[1]] = ov.get(bk[1], 0) + excess
            dest = td.get("overflow", "lost")
            if dest != "lost":
                self.add(("t", dest), excess)
                td2 = self.model.tdef(dest)
                if "max" in td2.d:
                    _, hi2 = self.folder.e.bounds(self.folder.env, dest)
                    if is_number(hi2) and self.bal[("t", dest)] > hi2:
                        spill = self.bal[("t", dest)] - hi2
                        self.bal[("t", dest)] = hi2
                        ov[dest] = ov.get(dest, 0) + spill

    # -- synthetic events
    def write_event(self, raw, apply_sim=True):
        fatal, probs = check_event(raw)
        if fatal or probs:
            self.tick.sink.warn("invalid-event", "%s: tick event skipped: %s"
                                % (self.name, "; ".join([fatal] if fatal else probs)))
            return False
        self.n_out += 1
        e = _event(raw, "tick-%s#%d" % (self.tick.id, self.n_out), 10 ** 6, self.n_out)
        if apply_sim:
            self.folder.apply_event(e)
        self.shadow.apply_event(e)
        self.out.append(raw)
        return True


def _event(raw, ref, file_index, idx):
    from . import dates
    e = Event()
    e.ref = ref
    e.date = raw["date"]
    e.key = dates.sort_key(raw["date"])
    e.seq = None
    e.file_index = file_index
    e.event_index = idx
    e.raw = raw
    e.effects = list(raw["effects"])
    e.kind = None
    e.gm_only = bool(raw.get("gm_only"))
    e.free = raw.get("free")
    e.satisfies = None
    e.when = raw.get("when")
    e.note = raw.get("note")
    e.source = raw.get("source")
    e.has_anchor = False
    e.pos = 0
    return e


# ------------------------------------------------------------------ the tick

class Tick:
    def __init__(self, sheet, tick_id, end, start=None, occurrences=(), checkpoint="month",
                 ignore=()):
        if not isinstance(tick_id, str) or not re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$", tick_id):
            raise TickError("invalid tick id %r" % (tick_id,))
        if checkpoint not in CHECKPOINTS:
            raise TickError("checkpoint must be one of %s" % ", ".join(CHECKPOINTS))
        self.id = tick_id
        self.cal = sheet.calendar
        self.end = self.cal.day(end, end=True)
        self.checkpoint = checkpoint
        self.ignore = set(ignore)  # history stems left out (re-running a tick for drift)
        self.occ_raw = [[n, d, dict(p or {})] for n, d, p in occurrences]
        self.sink = Sink()
        self.report = Report()
        self.root = Sim(sheet, self, [])
        self.sims = list(self.root.walk())
        last = self._guard()
        if start is None:
            if last is None:
                raise TickError("first tick of this sheet: give --from")
            self.start = last + 1
        else:
            self.start = self.cal.day(start)
        if self.start > self.end:
            raise TickError("nothing to tick: starts %s, after %s"
                            % (self.cal.date(self.start), self.cal.date(self.end)))
        if last is not None and self.start <= last:
            raise TickError("overlaps an earlier tick (ticked through %s)" % self.cal.date(last))
        self.occ = {}
        for name, date, params in occurrences:
            if name not in self.root.rules.occurrences:
                raise TickError("unknown occurrence %r" % name)
            d = self.cal.day(date)
            if not self.start <= d <= self.end:
                raise TickError("occurrence %s@%s is outside the tick" % (name, date))
            self.occ.setdefault(d, []).append((name, dict(params or {})))

    def _guard(self):
        """Latest ticked-through day across the tree; refuses a reused id."""
        last = None
        for sim in self.sims:
            for hf in sim.sheet.history:
                if hf.stem == "tick-%s" % self.id:
                    raise TickError("%s already has history/tick-%s.json (retract it by "
                                    "deleting the file)" % (sim.name, self.id))
                for raw in hf.events:
                    t = raw.get("tick") if isinstance(raw, dict) else None
                    if isinstance(t, dict) and isinstance(t.get("through"), str):
                        from . import dates
                        if dates.is_valid(t["through"]):
                            d = self.cal.day(t["through"])
                            last = d if last is None else max(last, d)
        return last

    # -- run
    def run(self):
        for sim in self.sims:
            sim.set_today(self.start - 1)
            sim.apply_until(self.start - 1)
            self._carry_in(sim)
            sim.start_vals = {}
        self.prev_rolls = {}
        for sim in self.sims:
            sim.set_today(self.start)
            self._rolls(sim, self.start, baseline=True)
        for day in range(self.start, self.end + 1):
            self._day(day)
        self._finish()
        return self.report

    def _carry_in(self, sim):
        best = None
        for hf in sim.sheet.history:
            for raw in hf.events:
                t = raw.get("tick") if isinstance(raw, dict) else None
                if isinstance(t, dict) and t.get("end") and isinstance(t.get("carry"), dict):
                    if best is None or str(t.get("through")) > str(best.get("through")):
                        best = t
        if best:
            st = sim.folder.state
            for k, v in best["carry"].items():
                if is_number(v) and is_number(st.values.get(k)):
                    st.values[k] = st.values[k] + v
            st.bump()

    def _day(self, day):
        for sim in self.sims:
            sim.set_today(day)
            sim.apply_until(day)
        for sim in self.sims:
            sim.dawn()
        for name, params in self.occ.get(day, []):
            od = self.root.rules.occurrences[name]
            for flow in od["flows"]:
                self._flow(self.root, flow, {"occ": params})
            if od.get("roll"):
                self._owe(self.root, day, "occurrence:%s" % name, od["roll"], None)
        for sim in self.sims:
            for flow in sim.rules.flows:
                self._flow(sim, flow, {})
        for sim in self.sims:
            sim.overflow(self.report)
            fields = self._watched(sim)
            sim.write_back()
            self._transitions(sim, day, fields)
            self._rolls(sim, day)
            if self._is_checkpoint(day):
                self._checkpoint(sim, day, final=day == self.end)

    def _is_checkpoint(self, day):
        if day == self.end or self.checkpoint == "day":
            return True
        if self.checkpoint == "week":
            return (day - self.start + 1) % 7 == 0
        if self.checkpoint == "month":
            return self.cal.date(day)[:-3] != self.cal.date(day + 1)[:-3]
        return False

    # -- flows
    def _flow(self, sim, flow, base_local):
        if flow.each is None:
            insts = [(dict(base_local), None)]
        elif flow.each[0] == "list":
            rows = sim.env.list_view().get(flow.each[1], [])
            insts = [(dict(base_local, entry=r), r["id"]) for r in rows]
        else:
            insts = []
            for mt in live_mounts(sim.folder.state, flow.each[1]):
                ns = sim.child_ns(mt)
                if ns is not None:
                    insts.append((dict(base_local, entry=ns), mt))
        if flow.where is not None:
            insts = [i for i in insts if sim.ev(flow.where, i[0], flow.site + ".where")]
        if flow.order is not None:
            keyed = []
            for i in insts:
                k = sim.ev(flow.order, i[0], flow.site + ".order")
                keyed.append(((0, k) if is_number(k) else (1, str(k)), _iid(i[1]), i))
            keyed.sort(key=lambda t: (t[0], t[1]))
            insts = [t[2] for t in keyed]
        for local, inst in insts:
            self._instance(sim, flow, local, inst)

    def _bk(self, sim, t, inst, flow):
        """Target → (sim, balance key) or None."""
        if t.kind == "trait":
            return sim, ("t", t.key)
        if t.kind == "entry":
            return sim, ("e", flow.each[1], inst, t.key)
        if t.kind == "capacity":
            return sim, ("c", t.key)
        if t.kind == "child":
            c = sim.child_of(inst)
            return (c, ("t", t.key)) if c is not None else None
        mt = (sim.folder.state.mounts.get(t.mount[0]) or {}).get(t.mount[1])
        if mt is None or mt.retired:
            return None
        c = sim.child_of(mt)
        return (c, ("t", t.key)) if c is not None else None

    def _avail(self, sim, t, inst, flow):
        loc = self._bk(sim, t, inst, flow)
        if loc is None:
            return 0
        s, bk = loc
        if bk[0] == "c":
            return s.caps.get(bk[1], 0)
        return max(0, _num(s.get(bk)))

    def _take(self, sim, t, inst, flow, amount):
        loc = self._bk(sim, t, inst, flow)
        if loc is None:
            return
        s, bk = loc
        if bk[0] == "c":
            s.caps[bk[1]] = s.caps.get(bk[1], 0) - amount
        else:
            s.add(bk, -amount)

    def _put(self, sim, t, inst, flow, amount):
        loc = self._bk(sim, t, inst, flow)
        if loc is None:
            self.sink.warn("tick", "%s: %s has no live target %s" % (sim.name, flow.site, t.src))
            return
        s, bk = loc
        s.add(bk, amount)

    def _instance(self, sim, flow, local, inst):
        site = flow.site
        if flow.active is not None and not sim.ev(flow.active, local, site + ".active"):
            return
        achs = []
        simple = []
        diets = []
        for c in flow.consume:
            if isinstance(c, Diet):
                need = max(0, _num(sim.ev(c.need, local, site + ".consume.%s.need" % c.label)))
                srcs = []
                fill = 0
                for t, ratio, above in c.sources:
                    r = _num(sim.ev(ratio, local, site + ".ratio")) if not is_number(ratio) else ratio
                    if r <= 0:
                        continue
                    floor_ = _num(sim.ev(above, local, site + ".above")) if above is not None else 0
                    av = max(0, self._avail(sim, t, inst, flow) - floor_)
                    srcs.append((t, r, av))
                    fill += av / r
                diets.append((need, srcs))
                if need > EPS:
                    achs.append(min(1, fill / need))
            else:
                amt = max(0, _num(sim.ev(c.amount, local, site + ".consume.%s" % c.target.src)))
                simple.append((c.target, amt))
                if amt > EPS:
                    achs.append(min(1, self._avail(sim, c.target, inst, flow) / amt))
        plans = []
        for nd in flow.needs:
            amt = max(0, _num(sim.ev(nd.amount, local, site + ".needs.%s.amount" % nd.cap)))
            key = sim.ev(nd.key, local, site + ".needs.%s.key" % nd.cap) if nd.key else None
            plan, work, chosen = self._plan(sim, nd, key, amt, local)
            plans.append((nd, amt, plan, chosen))
            if amt > EPS:
                achs.append(min(1, work / amt))
        f = min(achs) if achs else 1
        f = max(0, f)
        for t, amt in simple:
            self._take(sim, t, inst, flow, f * amt)
        sub = 0
        need_total = 0
        for need, srcs in diets:
            remaining = f * need
            need_total += need
            for i, (t, r, av) in enumerate(srcs):
                take = min(remaining, av / r)
                if take <= 0:
                    continue
                self._take(sim, t, inst, flow, take * r)
                remaining -= take
                if i > 0:
                    sub += take
        for nd, amt, plan, chosen in plans:
            self._spend(sim, nd, plan, f * amt, flow, inst, chosen, local)
        for p in flow.produce:
            amt = _num(sim.ev(p.amount, local, site + ".produce.%s" % p.target.src))
            if amt:
                self._put(sim, p.target, inst, flow, f * amt)
        if flow.short is not None and f < 1 - EPS:
            self._put(sim, flow.short, inst, flow, 1 - f)
        if flow.substituted is not None and need_total > EPS and sub > EPS:
            self._put(sim, flow.substituted, inst, flow, sub / need_total)
        st = self.report.flows.setdefault(sim.name, {}).setdefault(
            flow.id, {"runs": 0, "short_days": 0})
        st["runs"] += 1
        st["short_days"] += 1 - f

    # -- providers
    def _plan(self, sim, nd, key, amount, local):
        offers = sim.providers.get(nd.cap, {})

        def rate(pid):
            return offers[pid][1].get(key, 0) if key is not None else 1

        def flex(pid):
            return (len(offers[pid][1]), -offers[pid][0], pid)
        cands = [p for p in offers if rate(p) > 0]
        if nd.assign == "sticky":
            cur = (local.get("entry") or {}).get(nd.field)
            chosen = cur if cur in offers and rate(cur) > 0 else None
            if chosen is None:
                free = [p for p in cands if offers[p][0] > EPS]
                # shortcut: greedy least-flexible-first; switch to max-flow if a pack shows a
                # wrong starve (every shortfall is reported, so a misallocation is visible)
                chosen = min(free, key=flex) if free else None
            if chosen is None:
                return [], 0, None
            work = min(amount, offers[chosen][0] * rate(chosen))
            return [(chosen, rate(chosen))], work, chosen
        plan, work = [], 0
        for p in sorted(cands, key=flex):
            if work >= amount - EPS:
                break
            w = min(amount - work, offers[p][0] * rate(p))
            if w > EPS:
                plan.append((p, rate(p)))
                work += w
        return plan, work, None

    def _spend(self, sim, nd, plan, work, flow, inst, chosen, local):
        offers = sim.providers.get(nd.cap, {})
        hours = self.report.hours.setdefault(sim.name, {}).setdefault(nd.cap, {})
        for pid, r in plan:
            if work <= EPS:
                break
            w = min(work, offers[pid][0] * r)
            h = w / r
            offers[pid][0] -= h
            work -= w
            per = hours.setdefault(pid, {})
            per[flow.id] = per.get(flow.id, 0) + h
        if nd.assign == "sticky" and chosen is not None:
            cur = (local.get("entry") or {}).get(nd.field)
            if cur != chosen:
                bk = ("e", flow.each[1], inst, nd.field)
                sim.get(bk)
                sim.bal[bk] = chosen
                self.report.assignments.append({"sheet": sim.name, "date": self.cal.date(
                    sim.folder.e.today), "entry": inst, "capacity": nd.cap,
                    "from": cur, "to": chosen})

    # -- transitions, rolls
    def _watched(self, sim):
        out = {}
        for lname, ts in sim.rules.transitions.items():
            fields = {t["field"] for t in ts}
            for bk, v in sim.bal.items():
                if bk[0] == "e" and bk[1] == lname and bk[3] in fields:
                    out[bk] = sim.dawn_vals.get(bk)
        return out

    def _transitions(self, sim, day, watched):
        for (_, lname, eid, field), before in watched.items():
            e = (sim.folder.state.lists.get(lname) or {}).get(eid)
            if e is None or e.retired:
                continue
            after = e.data.get(field)
            for t in sim.rules.transitions[lname]:
                if t["field"] != field:
                    continue
                row = dict(e.data)
                at = sim.ev(t["at"], {"entry": row}, "transitions.%s.%s.at" % (lname, t["id"]))
                if not (is_number(at) and _num(before) < at <= _num(after) + EPS):
                    continue
                effects = [self._template(sim, x, row, lname, t["id"]) for x in t["effects"]]
                raw = {"date": self.cal.date(day),
                       "when": "tick %s: %s %s" % (self.id, t["id"], eid),
                       "source": "tick-%s" % self.id, "effects": effects, "free": "tick",
                       "tick": {"id": self.id, "kind": "transition"}}
                if sim.write_event(raw):
                    self.report.transitions.append({"sheet": sim.name, "date": raw["date"],
                                                    "list": lname, "entry": eid,
                                                    "transition": t["id"]})
                if t.get("roll"):
                    self._owe(sim, day, "transition:%s" % t["id"], t["roll"], eid)

    def _template(self, sim, eff, row, lname, tid):
        out = {}
        for k, v in eff.items():
            if k in ("by_expr", "to_expr"):
                val = sim.ev(v, {"entry": row}, "transitions.%s.%s.%s" % (lname, tid, k))
                out["by" if k == "by_expr" else "to"] = normalise(val)
            else:
                out[k] = _subst(v, row)
        return out

    def _owe(self, sim, day, rid, message, entry):
        o = {"sheet": sim.name, "date": self.cal.date(day), "roll": rid, "message": message}
        if entry is not None:
            o["entry"] = entry
        self.report.owed.append(o)

    def _rolls(self, sim, day, baseline=False):
        for rid, rd in sim.rules.rolls.items():
            if rd["scope"] == "sheet":
                items = [(None, {})]
            else:
                items = [(r["id"], {"entry": r})
                         for r in sim.env.list_view().get(rd["scope"][5:], [])]
            for eid, loc in items:
                now = bool(sim.ev(rd["when"], loc, "rolls.%s.when" % rid))
                k = (sim.name, rid, eid)
                if not baseline and now and not self.prev_rolls.get(k):
                    self._owe(sim, day, rid, rd["message"], eid)
                self.prev_rolls[k] = now

    # -- checkpoints
    def _checkpoint(self, sim, day, final):
        effects = _diff(sim)
        if not effects and not final:
            return
        t = {"id": self.id, "kind": "checkpoint", "from": self.cal.date(self.start),
             "through": self.cal.date(day)}
        if final:
            t["end"] = True
            t["checkpoint"] = self.checkpoint
            if self.occ_raw:
                t["occur"] = self.occ_raw
            carry = {}
            for k, v in sim.folder.state.values.items():
                if _integer(sim.model, k) and is_number(v):
                    c = v - _round(v)
                    if abs(c) > EPS:
                        carry[k] = round(c, 6)
            if carry:
                t["carry"] = carry
            owed = [o for o in self.report.owed if o["sheet"] == sim.name]
            if owed:
                t["owed"] = owed
        raw = {"date": self.cal.date(day), "when": "tick %s: %s" % (
            self.id, "end" if final else "checkpoint"), "source": "tick-%s" % self.id,
            "effects": effects, "free": "tick", "tick": t}
        sim.write_event(raw, apply_sim=False)

    def _finish(self):
        self.report.warnings = list(self.sink.warnings)
        for sim in self.sims:
            stocks = {}
            for k, v in sim.folder.state.values.items():
                if is_number(v):
                    stocks[k] = normalise(round(v, 6))
            self.report.stocks[sim.name] = stocks

    # -- writing
    def plan_writes(self):
        from . import writer
        out = []
        for sim in self.sims:
            if not sim.out:
                continue
            path, rel = writer.glob_guard(sim.sheet, "tick-%s" % self.id)
            out.append((sim, path, rel))
        return out

    def write(self):
        from . import writer
        plans = self.plan_writes()  # guards every ledger before touching any
        for sim, path, rel in plans:
            writer.write_atomic(path, {"source": "tick-%s" % self.id,
                                       "events": [writer.order_event(e) for e in sim.out]})
            self.report.files.append(path)
        return plans


def check_ticks(sheet):
    """Re-run every tick of ``sheet`` (and its subtree) → ``tick-drift`` warnings.

    Each tick is replayed from its recorded start, occurrences and checkpoint mode
    over the ledger without its own file and without any later tick, and its
    written events are compared with what the flows give now."""
    ends = []
    for hf in sheet.history:
        for raw in hf.events:
            t = raw.get("tick") if isinstance(raw, dict) else None
            if isinstance(t, dict) and t.get("end") and hf.stem == "tick-%s" % t.get("id"):
                ends.append((sheet.calendar.day(t["through"]), t))
    ends.sort(key=lambda x: x[0])
    stems = ["tick-%s" % t["id"] for _, t in ends]
    out = []
    for i, (_, t) in enumerate(ends):
        try:
            tk = Tick(sheet, t["id"], t["through"], start=t["from"],
                      occurrences=[tuple(o) for o in t.get("occur") or []],
                      checkpoint=t.get("checkpoint", "month"), ignore=stems[i:])
            tk.run()
        except SheetError as exc:
            out.append({"code": "tick-drift", "message": "tick %s cannot be replayed: %s"
                        % (t["id"], exc)})
            continue
        for sim in tk.sims:
            stored = _stored(sim.sheet.path, stems[i])
            now = [_comparable(e) for e in sim.out]
            if [_comparable(e) for e in stored] != now:
                out.append({"code": "tick-drift", "message": "tick %s on %s: the flows now give "
                            "different results than were written (re-tick, or let it stand)"
                            % (t["id"], sim.name), "ref": stems[i]})
    return out


def _stored(sheet_path, stem):
    """The events a tick wrote into one ledger (none if it wrote nothing there)."""
    from .loader import json_load
    p = os.path.join(os.path.dirname(sheet_path), "history", stem + ".json")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return json_load(fh).get("events", [])


def _comparable(e):
    t = dict(e.get("tick") or {})
    t.pop("owed", None)
    return (e.get("date"), normalise(e.get("effects")), t.get("kind"), t.get("carry"))


def _iid(inst):
    if inst is None:
        return ""
    return inst if isinstance(inst, str) else inst.id


def _subst(v, row):
    if isinstance(v, str):
        return _TPL.sub(lambda m: str(normalise(row.get(m.group(1), ""))), v)
    if isinstance(v, dict):
        return {k: _subst(x, row) for k, x in v.items()}
    if isinstance(v, list):
        return [_subst(x, row) for x in v]
    return copy.deepcopy(v)


def _integer(model, key):
    td = model.tdef(key)
    return bool(td.get("integer")) or td.type == "rating"


def _round(v):
    return math.floor(v + 0.5)


def _diff(sim):
    """Effects that bring the shadow (the ledger) to the simulation."""
    m = sim.model
    a = sim.folder.state
    b = sim.shadow.state
    effects = []
    for k, v in a.values.items():
        s = b.values.get(k)
        if is_number(v) and not isinstance(v, bool):
            target = _round(v) if _integer(m, k) else round(v, 6)
            base = s if is_number(s) else 0
            d = target - base
            if abs(d) > EPS:
                effects.append({"add": k, "by": normalise(round(d, 6))})
        elif v != s and k in b.values:
            effects.append({"set": k, "to": copy.deepcopy(v)})
    for lname, entries in a.lists.items():
        for eid, e in entries.items():
            if e.retired:
                continue
            se = (b.lists.get(lname) or {}).get(eid)
            if se is None or se.retired:
                continue
            adds, sets = {}, {}
            for f, v in e.data.items():
                s = se.data.get(f)
                if is_number(v) and not isinstance(v, bool) and (s is None or is_number(s)):
                    d = round(v, 6) - (s or 0)
                    if abs(d) > EPS:
                        adds[f] = normalise(round(d, 6))
                elif v != s:
                    sets[f] = copy.deepcopy(v)
            if adds or sets:
                eff = {"edit": "list.%s" % lname, "id": eid}
                if sets:
                    eff["fields"] = sets
                if adds:
                    eff["by"] = adds
                effects.append(eff)
    return effects


def parse_occur(text):
    """``name@DATE[:k=v,k=v]`` → (name, date, params)."""
    from .loader import json_loads
    m = re.match(r"^([a-z_][a-z0-9_]*)@([^:]+)(?::(.*))?$", text or "")
    if not m:
        raise TickError("bad --occur %r (use name@DATE[:k=v,...])" % text)
    params = {}
    for kv in filter(None, (m.group(3) or "").split(",")):
        if "=" not in kv:
            raise TickError("bad --occur parameter %r" % kv)
        k, v = kv.split("=", 1)
        try:
            v = json_loads(v)
        except ValueError:
            pass
        params[k.strip()] = v
    return m.group(1), m.group(2), params
