"""Resolved JSON (spec S8) and the player JS fragment (spec S10)."""
import json

from .expr import is_number, normalise
from .fold import span_years


def _title(ident):
    return ident.replace("_", " ").title()


class Builder:
    def __init__(self, res, view="gm", provenance=True):
        self.res = res
        self.m = res.model
        self.e = res.engine
        self.env = res.aenv
        self.st = res.astate
        self.gm = view == "gm"
        self.view = view
        self.prov = provenance
        self.e.current_ref = None
        self.warn_by_key = {}
        for w in res.sink.warnings:
            k = w.get("key")
            if k:
                self.warn_by_key.setdefault(k, [])
                if w["code"] not in self.warn_by_key[k]:
                    self.warn_by_key[k].append(w["code"])

    # -- helpers
    def refs(self, refs):
        pos = self.res.ref_pos
        out = sorted(set(refs), key=lambda r: pos.get(r, 0))
        if not self.gm:
            out = [r for r in out if r not in self.res.gm_refs and r not in self.res.anchor_refs]
        return out

    def ev(self, slot, local, site):
        return self.e.ev(self.env, slot, local, site)

    def trait_name(self, key, spec_name=None):
        meta = self.st.meta.get(key) or {}
        if meta.get("name"):
            return meta["name"]
        if spec_name:
            return spec_name
        td = self.m.tdef(key)
        if td.get("name"):
            return td.get("name")
        ce = self.e.cat_entry(td)
        if isinstance(ce, dict) and ce.get("name"):
            return ce["name"]
        return _title(td.id)

    def trait_gm(self, key):
        return self.e.trait_gm_only(self.st, key)

    def trait_value(self, key):
        if key in self.st.values:
            return self.st.values[key]
        return self.e.default(self.env, key)

    # -- fields
    def field(self, spec, key, kind, computed_locals=None, per_trait=None):
        """One output field (or None when omitted)."""
        m = self.m
        if key is not None and key in m.derived:
            return self.derived_field(spec, key, kind)
        if kind in ("track", "nested") and key is None:
            return self.keyless_field(spec, kind)
        if spec.get("show") == "present" and key not in self.st.values:
            return None
        td = m.tdef(key)
        gm_only = bool(spec.get("gm_only")) or self.trait_gm(key)
        if gm_only and not self.gm:
            return None
        value = self.trait_value(key)
        f = {"key": key, "kind": kind, "type": td.type,
             "name": self.trait_name(key, spec.get("name")), "value": normalise(value)}
        t = td.type
        loc = self.e.tlocal(key)
        if t == "rating":
            lo, hi = self.e.bounds(self.env, key)
            if "max" in spec:
                hi = self.ev(spec["max"], loc, "shape.%s.max" % key)
            f["min"] = normalise(lo)
            f["max"] = normalise(hi)
        elif t == "enum":
            vals = td.get("values") or []
            f["values"] = list(vals)
            f["index"] = vals.index(value) if value in vals else None
        elif t == "compound":
            parts = []
            for p, pd in (td.get("parts") or {}).items():
                pt = pd.get("type", "rating")
                pv = (value or {}).get(p) if isinstance(value, dict) else None
                po = {"part": p, "type": pt, "value": normalise(pv)}
                if pt == "rating":
                    lo, hi = self.e.bounds(self.env, key, p)
                    po["min"] = normalise(lo)
                    po["max"] = normalise(hi)
                elif pt == "enum":
                    vals = pd.get("values") or []
                    po["values"] = list(vals)
                    po["index"] = vals.index(pv) if pv in vals else None
                parts.append(po)
            f["parts"] = parts
        # kind extras
        if kind == "catalog":
            ce = self.e.cat_entry(td) or {}
            f["text"] = ce.get("text")
            levels = []
            lv = ce.get("levels") or {}
            if isinstance(lv, dict) and is_number(value):
                for lk, ld in sorted(lv.items(), key=lambda kv: _int(kv[0])):
                    n = _int(lk)
                    if n is not None and n <= value and isinstance(ld, dict):
                        levels.append({"level": n, "name": ld.get("name"), "text": ld.get("text")})
            f["levels"] = levels
        elif kind == "choice":
            disp, text = self.choice(spec, td, value)
            f["display"] = disp
            f["text"] = text
        elif kind == "pool":
            f["value"] = normalise(value)
            f["max"] = normalise(value)
        elif kind == "track":
            self.track_extras(spec, f, value)
        elif kind == "nested":
            f["fields"] = self.fields(spec.get("fields") or [])
        note = (self.st.meta.get(key) or {}).get("note") or spec.get("note") or td.get("note")
        if note:
            f["note"] = note
        if gm_only and self.gm:
            f["gm_only"] = True
        if self.e.active(self.env, key) is False:
            f["inactive"] = True
        if per_trait:
            comp = {}
            idx = f.get("index") if t == "enum" else None
            cl = dict(loc, value=normalise(value), index=idx)
            for name, slot in per_trait.items():
                comp[name] = normalise(self.ev(slot, cl, "classes.%s.per_trait.%s" % (td.cls, name)))
            f["computed"] = comp
        if self.gm:
            codes = []
            for k2, cs in self.warn_by_key.items():
                if k2 == key or k2.startswith(key + "."):
                    for c in cs:
                        if c not in codes:
                            codes.append(c)
            if codes:
                f["warn"] = codes
        if self.prov:
            f["from"] = self.refs(self.st.refs.get(key, []))
        return f

    def choice(self, spec, td, value):
        opts = spec.get("options") or {}
        entry = None
        if "catalog" in opts:
            entry = (self.m.catalog.get(opts["catalog"]) or {}).get(value) if isinstance(value, str) else None
        elif "table" in opts:
            tab = self.m.tables.get(opts["table"]) or {}
            entry = (tab.get("rows") or {}).get(value) if isinstance(value, str) else None
        elif "values" not in opts and td.get("catalog") and isinstance(value, str):
            entry = (self.m.catalog.get(td.get("catalog")) or {}).get(value)
        if isinstance(entry, dict):
            return entry.get("name", value), entry.get("text")
        return value, None

    def track_extras(self, spec, f, value=None):
        if "levels" in spec:
            f["levels"] = list(spec["levels"])
        elif "max" in spec:
            f["max"] = normalise(self.ev(spec["max"], {}, "shape.track.max"))
        elif value is not None:
            f["max"] = normalise(value)

    def keyless_field(self, spec, kind):
        if spec.get("gm_only") and not self.gm:
            return None
        f = {"key": None, "kind": kind, "name": spec.get("name"), "value": None}
        if kind == "track":
            self.track_extras(spec, f)
        else:
            f["fields"] = self.fields(spec.get("fields") or [])
        if spec.get("note"):
            f["note"] = spec["note"]
        if spec.get("gm_only") and self.gm:
            f["gm_only"] = True
        return f

    def derived_field(self, spec, key, kind):
        dd = self.m.derived[key]
        gm_only = bool(spec.get("gm_only") or dd.get("gm_only"))
        if gm_only and not self.gm:
            return None
        value = normalise(self.env.derived(key))
        f = {"key": key, "kind": kind,
             "name": spec.get("name") or dd.get("name") or _title(key.split(".")[-1]),
             "value": value}
        if kind == "pool":
            f["max"] = value
        elif kind == "track":
            self.track_extras(spec, f, value)
        elif kind == "nested":
            f["fields"] = self.fields(spec.get("fields") or [])
        if spec.get("note"):
            f["note"] = spec["note"]
        if gm_only and self.gm:
            f["gm_only"] = True
        if self.gm and key in self.warn_by_key:
            f["warn"] = list(self.warn_by_key[key])
        return f

    def fields(self, specs):
        out = []
        for spec in specs:
            kind = spec.get("kind", "fixed")
            f = self.field(spec, spec.get("key"), kind)
            if f is not None:
                out.append(f)
        return out

    def class_fields(self, sec):
        m = self.m
        st = self.st
        cls = sec["class"]
        cd = m.classes[cls]
        show = sec.get("show", "present")
        declared = m.class_traits(cls)
        present = [k for k in st.values if m.class_of(k) == cls]
        undeclared = sorted([k for k in present if k not in m.traits],
                            key=lambda k: self.trait_name(k).lower())
        if show == "present":
            keys = [k for k in declared if k in st.values] + undeclared
        elif show == "active":
            keys = [k for k in declared
                    if k in st.values or self.e.active(self.env, k) is not False] + undeclared
        else:
            keys = declared + undeclared
        where = sec.get("where") or {}
        if "group" in where:
            keys = [k for k in keys if m.trait_group(k, st.meta.get(k)) == where["group"]]
        kind = sec.get("kind") or ("catalog" if cd.get("catalog") else
                                   ("named" if cd.get("open") else "fixed"))
        per_trait = cd.get("per_trait") or None
        out = []
        for k in keys:
            f = self.field({}, k, kind, per_trait=per_trait)
            if f is not None:
                out.append(f)
        return out

    # -- lists / spans
    def list_entries(self, lname):
        ld = self.m.lists.get(lname) or {}
        if ld.get("gm_only") and not self.gm:
            return None
        rows = (self.env.list_view() or {}).get(lname, [])
        live = self.st.live_entries(lname)
        ns = ld.get("catalog")
        out = []
        for e, flat in zip(live, rows):
            gm_only = bool(e.data.get("gm_only")) or e.gm_created
            if gm_only and not self.gm:
                continue
            ce = None
            if ns and isinstance(e.data.get("ref"), str):
                ce = (self.m.catalog.get(ns) or {}).get(e.data["ref"])
            ce = ce if isinstance(ce, dict) else {}
            o = {"id": e.data["id"],
                 "name": e.data.get("name") or ce.get("name") or e.data["id"],
                 "text": e.data.get("text") if e.data.get("text") is not None else ce.get("text")}
            if "ref" in e.data:
                o["ref"] = e.data["ref"]
            if isinstance(ce.get("levels"), dict):
                o["levels"] = [{"level": _int(k), "name": v.get("name"), "text": v.get("text")}
                               for k, v in sorted(ce["levels"].items(), key=lambda kv: _int(kv[0]))
                               if isinstance(v, dict)]
            o["fields"] = {k: normalise(v) for k, v in flat.items()
                           if k not in ("id", "name", "text", "ref", "gm_only")}
            if gm_only and self.gm:
                o["gm_only"] = True
            if self.prov:
                o["from"] = self.refs(e.refs)
            out.append(o)
        return out

    def span_out(self, sp):
        sd = self.m.spans.get(sp.kind) or {}
        gm_only = bool(sd.get("gm_only")) or sp.gm_created
        if gm_only and not self.gm:
            return None
        o = {"id": sp.id, "kind": sp.kind, "name": sp.name, "start": sp.start, "end": sp.end,
             "open": sp.end is None,
             "years": round(span_years(sp, self.res.at_end, self.res.latest_key), 2),
             "note": sp.note}
        if gm_only and self.gm:
            o["gm_only"] = True
        if self.prov:
            o["from"] = self.refs(sp.refs)
        return o

    # -- top level
    def build(self):
        m = self.m
        sheet = self.res.sheet
        doc = {"format": "sheet/1", "view": self.view, "at": self.res.at,
               "character": {"id": sheet.id, "name": sheet.name, "meta": sheet.meta},
               "system": {"rules": m.id, "shape": m.shape.get("id")}}
        groups = []
        gdefs = (m.shape.get("groups") or {})
        for gid, g in sorted(gdefs.items(), key=lambda kv: (_order(kv[1]), kv[0])):
            if g.get("gm_only") and not self.gm:
                continue
            go = {"id": gid, "name": g.get("name")}
            if g.get("gm_only") and self.gm:
                go["gm_only"] = True
            secs = []
            for sid, sec in sorted((g.get("sections") or {}).items(),
                                   key=lambda kv: (_order(kv[1]), kv[0])):
                if sec.get("gm_only") and not self.gm:
                    continue
                so = {"id": sid, "name": sec.get("name")}
                if "list" in sec:
                    ents = self.list_entries(sec["list"])
                    if ents is None:
                        continue
                    ld = m.lists.get(sec["list"]) or {}
                    cap = self.ev(ld["cap"], {}, "lists.%s.cap" % sec["list"]) if "cap" in ld else None
                    so.update({"kind": "list", "list": sec["list"], "count": len(ents),
                               "cap": normalise(cap), "entries": ents})
                elif "spans" in sec:
                    kind = sec["spans"]
                    sps = [self.span_out(sp) for sp in self.st.spans.values()
                           if kind == "*" or sp.kind == kind]
                    so.update({"kind": "spans", "spans": [s for s in sps if s is not None]})
                elif "class" in sec:
                    so.update({"kind": "fields", "fields": self.class_fields(sec)})
                else:
                    so.update({"kind": "fields", "fields": self.fields(sec.get("fields") or [])})
                if sec.get("note"):
                    so["note"] = sec["note"]
                if sec.get("gm_only") and self.gm:
                    so["gm_only"] = True
                secs.append(so)
            go["sections"] = secs
            groups.append(go)
        doc["groups"] = groups
        lists = {}
        for lname in list(m.lists) + [n for n in self.st.lists if n not in m.lists]:
            ents = self.list_entries(lname)
            if ents is not None:
                lists[lname] = ents
        doc["lists"] = lists
        doc["spans"] = [s for s in (self.span_out(sp) for sp in self.st.spans.values())
                        if s is not None]
        values = {}
        for k, v in self.st.values.items():
            if not self.gm and self.trait_gm(k):
                continue
            values[k] = normalise(v)
        doc["values"] = values
        derived = {}
        for k, dd in m.derived.items():
            if not self.gm and dd.get("gm_only"):
                continue
            derived[k] = normalise(self.env.derived(k))
        doc["derived"] = derived
        if self.gm:
            anchors = []
            for a in self.res.anchors:
                o = {"id": a["id"], "key": a["key"], a["_op"]: a[a["_op"]], "date": a["date"],
                     "satisfied": bool(a["satisfied"]), "folded": normalise(a["folded"])}
                if self.prov:
                    o["satisfied_by"] = self.refs(a["satisfied_by"])
                    o["from"] = [a["ref"]]
                anchors.append(o)
            doc["anchors"] = anchors
            doc["warnings"] = [dict(w) for w in self.res.sink.warnings]
            doc["notices"] = [dict(n) for n in self.res.notices]
        return doc


def _order(d):
    o = d.get("order", 0) if isinstance(d, dict) else 0
    return o if is_number(o) else 0


def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def build(res, view="gm", provenance=True):
    return Builder(res, view, provenance).build()


def to_json(doc, compact=False):
    if compact:
        return json.dumps(doc, ensure_ascii=False)
    return json.dumps(doc, ensure_ascii=False, indent=2)


def export_js(doc, source, at=None, key=None):
    """Player-view JS fragment: assigns ``DATA.sheet`` (or ``DATA.sheets[key]``)."""
    body = _js_safe(json.dumps(doc, ensure_ascii=False, indent=1))
    regen = "python rpg-tools/scripts/sheet.py export %s" % source
    if at:
        regen += " --at %s" % at
    if key:
        regen += " --key %s" % key
    head = ("/* GENERATED — do not hand-edit.\n"
            "   Source: %s (player view, at %s)\n"
            "   Regenerate: %s */\n" % (_comment_safe(source), _comment_safe(at or "latest"),
                                        _comment_safe(regen)))
    if key:
        return head + "(DATA.sheets = DATA.sheets || {})[%s] = %s;\n" % (
            _js_safe(json.dumps(key)), body)
    return head + "DATA.sheet = %s;\n" % body


def _js_safe(text):
    """Defuse ``</script>`` / ``<!--`` inside a JS literal (S10)."""
    return text.replace("<", "\\u003c")


def _comment_safe(text):
    """Keep a string inside a ``/* */`` comment: no ``*/``, no ``<``, one line."""
    return (str(text).replace("*/", "* /").replace("<", "&lt;")
            .replace("\r", " ").replace("\n", " "))
