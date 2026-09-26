"""Loading, merging and validating sheet inputs (spec S2, S3, S5).

Four inputs, all JSON: rules, shape, catalog (merged with ``extends`` +
globs, merge by key, later wins, ``null`` removes, arrays replace) and the
history ledger (one file per session, loaded in manifest glob order).

Everything malformed in rules/shape/catalog/manifest is fatal
(``SheetError``). Problems in history files become ``invalid-event``
warnings: nothing in a ledger is refused.
"""
import copy
import glob
import json
import os
import re

from .expr import (RESERVED, SheetError, compile_slot, valid_key, valid_segment)

TRAIT_TYPES = ("rating", "enum", "number", "text", "compound", "relation")
PART_TYPES = ("rating", "enum", "number", "text")
FIELD_KINDS = ("fixed", "catalog", "named", "nested", "choice", "scalar",
               "derived", "pool", "track", "relation")
CLASS_ONLY = ("name", "note", "groups", "default_group", "open", "per_trait")
RESERVED_RULES = ("modifiers", "tallies")


# ------------------------------------------------------------------ files

def read_json(path, what="file"):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise SheetError("missing %s: %s" % (what, path))
    except json.JSONDecodeError as exc:
        raise SheetError("malformed JSON in %s: %s (line %d col %d)"
                         % (path, exc.msg, exc.lineno, exc.colno))
    except OSError as exc:
        raise SheetError("cannot read %s: %s" % (path, exc))


def natural_key(text):
    """Digit runs compare numerically (s2 < s10)."""
    parts = re.split(r"(\d+)", text)
    return [int(p) if i % 2 else p for i, p in enumerate(parts)]


def _has_magic(p):
    return glob.has_magic(p)


def expand(pattern, base_dir, what="file", exclude=None, missing_ok=False):
    """Expand one path/glob relative to ``base_dir`` → list of absolute paths."""
    if not isinstance(pattern, str) or not pattern:
        raise SheetError("%s path must be a non-empty string, got %r" % (what, pattern))
    full = os.path.normpath(os.path.join(base_dir, pattern))
    if _has_magic(pattern):
        found = [os.path.normpath(os.path.abspath(p))
                 for p in glob.glob(full, recursive=True) if os.path.isfile(p)]
        found.sort(key=natural_key)
        if exclude:
            found = [p for p in found if p != exclude]
        return found
    full = os.path.abspath(full)
    if not os.path.isfile(full):
        if missing_ok:
            return []
        raise SheetError("missing %s: %s" % (what, full))
    return [full]


def merge(base, over):
    """Deep merge: dict∩dict recurse; else later wins; None removes; arrays replace."""
    result = dict(base)
    for k, v in over.items():
        if v is None:
            result.pop(k, None)
        elif isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = merge(result[k], v)
        elif isinstance(v, dict):
            result[k] = merge({}, v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def _display(path, root_dir):
    try:
        return os.path.relpath(path, root_dir).replace(os.sep, "/")
    except ValueError:
        return path


def linearise(paths, what="file"):
    """Resolve ``extends`` depth-first → ordered list of ``(path, data)``.

    Diamond linearisation: within one top-level resolution a file already
    merged is skipped on later encounters (first occurrence keeps position).
    """
    out = []
    seen = set()
    stack = []
    cache = {}
    root_dir = os.path.dirname(paths[0]) if paths else os.getcwd()

    def visit(p):
        if p in stack:
            chain = stack[stack.index(p):] + [p]
            raise SheetError("Circular extends detected: "
                             + " -> ".join(_display(c, root_dir) for c in chain))
        if p in seen:
            return
        if p not in cache:
            cache[p] = read_json(p, what)
        data = cache[p]
        if not isinstance(data, dict):
            raise SheetError("%s must be a JSON object: %s" % (what, p))
        ext = data.get("extends")
        parents = []
        if ext is not None:
            items = [ext] if isinstance(ext, str) else ext
            if not isinstance(items, list):
                raise SheetError("%s: extends must be a string or list" % p)
            for item in items:
                parents.extend(expand(item, os.path.dirname(p), what, exclude=p))
        stack.append(p)
        for parent in parents:
            visit(parent)
        stack.pop()
        seen.add(p)
        out.append((p, data))

    for p in paths:
        visit(p)
    return out


def load_merged(spec, base_dir, what):
    """Manifest field (path or list of paths/globs) → merged dict + file list."""
    items = [spec] if isinstance(spec, str) else spec
    if not isinstance(items, list) or not items:
        raise SheetError("sheet.json %s must be a path or a non-empty list" % what)
    paths = []
    for item in items:
        paths.extend(expand(item, base_dir, what))
    files = linearise(paths, what)
    merged = {}
    for _, data in files:
        merged = merge(merged, data)
    merged.pop("extends", None)
    return merged, [p for p, _ in files]


def expand_history(patterns, base_dir, extra=()):
    """History globs in listed order, each sorted naturally, duplicates kept
    at first position. ``extra`` = not-yet-existing paths to place too."""
    out = []
    extra = [os.path.normpath(os.path.abspath(e)) for e in extra]
    for pat in patterns:
        found = expand(pat, base_dir, "history file", missing_ok=True)
        for e in extra:
            if history_matches(e, pat, base_dir) and e not in found:
                found.append(e)
        found.sort(key=natural_key)
        for f in found:
            if f not in out:
                out.append(f)
    return out


def history_matches(path, pattern, base_dir):
    """Does ``path`` match a manifest history pattern (glob semantics)?

    Matched against the *pattern*, not its expansion, so a file that does not
    exist yet can be checked (writer glob guard)."""
    full = os.path.normpath(os.path.abspath(os.path.join(base_dir, pattern)))
    path = os.path.normpath(os.path.abspath(path))
    if not _has_magic(pattern):
        return path == full
    # '*' must not cross directories; '**' may.
    rx = _glob_to_re(full.replace(os.sep, "/"))
    return re.fullmatch(rx, path.replace(os.sep, "/")) is not None


def _glob_to_re(pat):
    i, out = 0, []
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pat.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
            else:
                body = pat[i + 1:j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


# ------------------------------------------------------------------ model

class TraitDef:
    """Effective definition of one trait key (class fields, then trait)."""

    __slots__ = ("key", "cls", "id", "d", "declared", "known", "type")

    def __init__(self, key, cls, d, declared, known):
        self.key = key
        self.cls = cls
        self.id = key.split(".")[-1]
        self.d = d
        self.declared = declared
        self.known = known
        self.type = d.get("type", "rating")

    def get(self, k, default=None):
        return self.d.get(k, default)


class Model:
    """Merged + compiled rules, shape and catalog."""

    def __init__(self, rules, shape, catalog):
        self.raw_rules = rules
        self.shape = shape
        self.catalog = catalog
        self.rules = copy.deepcopy(rules)
        r = self.rules
        self.id = r.get("id")
        self.currency = r.get("currency", "xp")
        self.classes = _obj(r, "classes", "rules")
        self.traits = _obj(r, "traits", "rules")
        self.lists = _obj(r, "lists", "rules")
        self.spans = _obj(r, "spans", "rules")
        self.tables = _obj(r, "tables", "rules")
        self.derived = {}
        self.creation = _obj(r, "creation", "rules")
        self.notices = _obj(r, "notices", "rules")
        self._tdefs = {}
        self._validate_and_compile()

    # -- validation -------------------------------------------------------
    def _validate_and_compile(self):
        r = self.rules
        for name in self.classes:
            _check_name(name, "class")
            cd = self.classes[name]
            if not isinstance(cd, dict):
                raise SheetError("rules: class %s must be an object" % name)
            self._check_tdef(cd, "classes.%s" % name, is_class=True)
        for key, td in self.traits.items():
            if not valid_key(key):
                raise SheetError("rules: invalid trait key %r" % key)
            segs = key.split(".")
            if segs[0] in RESERVED:
                raise SheetError("rules: trait key %r uses reserved name %r" % (key, segs[0]))
            if len(segs) > 2 or (len(segs) == 2 and segs[0] not in self.classes):
                raise SheetError("rules: trait key %r must be a bare key or class.id "
                                 "(class %r not declared)" % (key, segs[0]))
            if not isinstance(td, dict):
                raise SheetError("rules: trait %s must be an object" % key)
            cls = self.classes.get(segs[0]) if len(segs) == 2 else None
            self._check_tdef(td, "traits.%s" % key, is_class=False, inherited=cls)
            eff_type = td.get("type", (cls or {}).get("type", "rating"))
            if eff_type == "compound" and not (td.get("parts") or (cls or {}).get("parts")):
                raise SheetError("traits.%s: compound needs parts" % key)
        for name, ld in self.lists.items():
            _check_name(name, "list")
            if not isinstance(ld, dict):
                raise SheetError("rules: list %s must be an object" % name)
            site = "lists.%s" % name
            for f in ("cap", "cost"):
                if f in ld:
                    ld[f] = compile_slot(ld[f], "%s.%s" % (site, f))
            flds = ld.get("fields") or {}
            if not isinstance(flds, dict):
                raise SheetError("%s.fields must be an object" % site)
            for fk in list(flds):
                flds[fk] = compile_slot(flds[fk], "%s.fields.%s" % (site, fk))
        for name, sd in self.spans.items():
            _check_name(name, "span kind")
        for name, tab in self.tables.items():
            if not valid_key(name):
                raise SheetError("rules: invalid table name %r" % name)
            if not isinstance(tab, dict) or not ("rows" in tab or "steps" in tab):
                raise SheetError("rules: table %s needs rows or steps" % name)
        for ns in self.catalog:
            if not valid_key(ns):
                raise SheetError("catalog: invalid namespace %r" % ns)
            if not isinstance(self.catalog[ns], dict):
                raise SheetError("catalog: namespace %s must be an object" % ns)
        for key, dv in _obj(r, "derived", "rules").items():
            if not valid_key(key):
                raise SheetError("rules: invalid derived key %r" % key)
            if key.split(".")[0] in RESERVED:
                raise SheetError("rules: derived key %r uses a reserved name" % key)
            if key in self.traits or key in self.classes or key in self.lists:
                raise SheetError("rules: derived key %r collides with a trait/class/list" % key)
            if isinstance(dv, dict):
                d = dict(dv)
                d["expr"] = compile_slot(dv.get("expr"), "derived.%s" % key)
            else:
                d = {"expr": compile_slot(dv, "derived.%s" % key)}
            self.derived[key] = d
        # creation
        budgets = self.creation.get("budgets") or {}
        if not isinstance(budgets, dict):
            raise SheetError("rules: creation.budgets must be an object")
        for bid, b in budgets.items():
            site = "creation.budgets.%s" % bid
            if not isinstance(b, dict):
                raise SheetError("%s must be an object" % site)
            kinds = [k for k in ("class", "keys", "list") if k in b]
            if len(kinds) != 1:
                raise SheetError("%s needs exactly one of class/keys/list" % site)
            if "class" in b and b["class"] not in self.classes:
                raise SheetError("%s: unknown class %r" % (site, b["class"]))
            if "priority" in b:
                if "class" not in b or b.get("by") != "group":
                    raise SheetError("%s: priority needs class + by: group" % site)
                groups = self.class_groups(b["class"])
                if not isinstance(b["priority"], list) or len(groups) != len(b["priority"]):
                    raise SheetError("%s: priority has %d slots but class %s has %d groups (%s)"
                                     % (site, len(b["priority"]) if isinstance(b["priority"], list) else 0,
                                        b["class"], len(groups), ", ".join(groups)))
            elif "total" not in b:
                raise SheetError("%s needs total or by: group + priority" % site)
            for f in ("where", "base", "step_cost", "spend", "total"):
                if f in b:
                    b[f] = compile_slot(b[f], "%s.%s" % (site, f))
        fr = self.creation.get("freebies")
        if fr is not None:
            if not isinstance(fr, dict):
                raise SheetError("rules: creation.freebies must be an object")
            if "total" in fr:
                fr["total"] = compile_slot(fr["total"], "creation.freebies.total")
        for cid, ch in (self.creation.get("checks") or {}).items():
            if not isinstance(ch, dict) or "when" not in ch:
                raise SheetError("creation.checks.%s needs when" % cid)
            ch["when"] = compile_slot(ch["when"], "creation.checks.%s.when" % cid)
        for code, nd in self.notices.items():
            if not isinstance(nd, dict) or "when" not in nd:
                raise SheetError("notices.%s needs when" % code)
            scope = nd.get("scope", "sheet")
            if scope != "sheet" and not (isinstance(scope, str) and scope.startswith("span:")):
                raise SheetError("notices.%s: scope must be sheet or span:KIND" % code)
            nd["when"] = compile_slot(nd["when"], "notices.%s.when" % code)
        self._validate_shape()

    def _check_tdef(self, d, site, is_class, inherited=None):
        inherited = inherited or {}
        t = d.get("type", inherited.get("type", "rating"))
        if t not in TRAIT_TYPES:
            raise SheetError("%s: unknown type %r" % (site, t))
        if t == "enum" and not isinstance(d.get("values", inherited.get("values")), list):
            raise SheetError("%s: enum needs a values list" % site)
        if t == "compound" and is_class and "parts" not in d:
            raise SheetError("%s: compound needs parts" % site)
        if t == "compound" and "parts" in d:
            parts = d.get("parts")
            if not isinstance(parts, dict) or not parts:
                raise SheetError("%s: compound needs parts" % site)
            for pname, pd in parts.items():
                if not valid_segment(pname):
                    raise SheetError("%s: invalid compound part name %r" % (site, pname))
                if not isinstance(pd, dict):
                    raise SheetError("%s.parts.%s must be an object" % (site, pname))
                pt = pd.get("type", "rating")
                if pt not in PART_TYPES:
                    raise SheetError("%s.parts.%s: type %r not allowed" % (site, pname, pt))
                if pt == "enum" and not isinstance(pd.get("values"), list):
                    raise SheetError("%s.parts.%s: enum needs values" % (site, pname))
                self._compile_tdef(pd, "%s.parts.%s" % (site, pname))
        if is_class:
            if "groups" in d and not isinstance(d["groups"], list):
                raise SheetError("%s.groups must be a list" % site)
            pt = d.get("per_trait") or {}
            if not isinstance(pt, dict):
                raise SheetError("%s.per_trait must be an object" % site)
            for k in list(pt):
                pt[k] = compile_slot(pt[k], "%s.per_trait.%s" % (site, k))
        self._compile_tdef(d, site)

    @staticmethod
    def _compile_tdef(d, site):
        for f in ("min", "max", "base", "active"):
            if f in d:
                d[f] = compile_slot(d[f], "%s.%s" % (site, f))
        cost = d.get("cost")
        if cost is not None:
            if not isinstance(cost, dict):
                raise SheetError("%s.cost must be an object" % site)
            for f in ("new", "raise"):
                if f in cost:
                    cost[f] = compile_slot(cost[f], "%s.cost.%s" % (site, f))

    def _validate_shape(self):
        s = self.shape
        groups = s.get("groups", {})
        if not isinstance(groups, dict):
            raise SheetError("shape: groups must be an object")
        for gid, g in groups.items():
            if not isinstance(g, dict):
                raise SheetError("shape: group %s must be an object" % gid)
            secs = g.get("sections", {})
            if not isinstance(secs, dict):
                raise SheetError("shape: group %s sections must be an object" % gid)
            for sid, sec in secs.items():
                site = "shape.groups.%s.sections.%s" % (gid, sid)
                if not isinstance(sec, dict):
                    raise SheetError("%s must be an object" % site)
                kinds = [k for k in ("fields", "class", "list", "spans") if k in sec]
                if len(kinds) != 1:
                    raise SheetError("%s needs exactly one of fields/class/list/spans" % site)
                if "fields" in sec:
                    self._validate_fields(sec["fields"], site + ".fields")
                if "class" in sec and sec["class"] not in self.classes:
                    raise SheetError("%s: unknown class %r" % (site, sec["class"]))
                if sec.get("show", "present") not in ("present", "active", "all"):
                    raise SheetError("%s: show must be present/active/all" % site)

    def _validate_fields(self, fields, site):
        if not isinstance(fields, list):
            raise SheetError("%s must be an array" % site)
        for i, f in enumerate(fields):
            fs = "%s[%d]" % (site, i)
            if not isinstance(f, dict):
                raise SheetError("%s must be an object" % fs)
            kind = f.get("kind", "fixed")
            if kind not in FIELD_KINDS:
                raise SheetError("%s: unknown field kind %r" % (fs, kind))
            if kind not in ("track", "nested") and not isinstance(f.get("key"), str):
                raise SheetError("%s: key required for kind %s" % (fs, kind))
            if "max" in f:
                f["max"] = compile_slot(f["max"], fs + ".max")
            if kind == "nested":
                self._validate_fields(f.get("fields", []), fs + ".fields")

    # -- lookups ----------------------------------------------------------
    def class_of(self, key):
        segs = key.split(".")
        if len(segs) == 2 and segs[0] in self.classes:
            return segs[0]
        return None

    def tdef(self, key):
        td = self._tdefs.get(key)
        if td is not None:
            return td
        cls = self.class_of(key)
        d = {}
        if cls:
            d = {k: v for k, v in self.classes[cls].items() if k not in CLASS_ONLY}
        declared = key in self.traits
        if declared:
            d.update(self.traits[key])
        if not declared and not cls:
            d = {"type": "rating", "min": 0}
        known = declared or bool(cls and self.classes[cls].get("open"))
        if not known and cls and self.classes[cls].get("catalog"):
            # a catalog class's valid ids are its catalog entries (S7 unknown-trait)
            ns = self.classes[cls]["catalog"]
            known = key.split(".")[1] in (self.catalog.get(ns) or {})
        td = TraitDef(key, cls, d, declared, known)
        self._tdefs[key] = td
        return td

    def class_traits(self, cls):
        return [k for k in self.traits if self.class_of(k) == cls]

    def trait_group(self, key, meta=None):
        if meta and meta.get("group"):
            return meta["group"]
        td = self.tdef(key)
        if td.get("group"):
            return td.get("group")
        if td.cls:
            return self.classes[td.cls].get("default_group")
        return None

    def class_groups(self, cls):
        cd = self.classes[cls]
        if isinstance(cd.get("groups"), list):
            return list(cd["groups"])
        out = []
        for k in self.class_traits(cls):
            g = self.trait_group(k)
            if g is not None and g not in out:
                out.append(g)
        return out

    def parse_target(self, key):
        """Effect target → ``(trait_key, part|None)``; None if structurally invalid."""
        if not valid_key(key):
            return None
        segs = key.split(".")
        if segs[0] == "list":
            return None
        if len(segs) == 3:
            base = ".".join(segs[:2])
            if self.class_of(base) or base in self.traits:
                td = self.tdef(base)
                if td.type == "compound" and segs[2] in (td.get("parts") or {}):
                    return base, segs[2]
            return None
        if len(segs) == 2:
            if segs[0] in self.classes:
                return key, None
            if segs[0] in self.traits:
                td = self.tdef(segs[0])
                if td.type == "compound" and segs[1] in (td.get("parts") or {}):
                    return segs[0], segs[1]
                return None
            return key, None
        if len(segs) == 1:
            return key, None
        return None

    def currencies(self):
        out = [self.currency]
        for d in list(self.classes.values()) + list(self.traits.values()):
            _collect_cur(d, self.currency, out)
        for ld in self.lists.values():
            c = ld.get("currency")
            if c and c not in out:
                out.append(c)
        return out

    def cost_currency(self, tdd):
        cost = tdd.get("cost") or {}
        return cost.get("currency") or self.currency


def _collect_cur(d, default, out):
    cost = d.get("cost")
    if isinstance(cost, dict):
        c = cost.get("currency") or default
        if c not in out:
            out.append(c)
    for pd in (d.get("parts") or {}).values():
        if isinstance(pd, dict):
            _collect_cur(pd, default, out)


def _obj(d, key, what):
    v = d.get(key)
    if v is None:
        v = {}
        d[key] = v
    if not isinstance(v, dict):
        raise SheetError("%s: %s must be an object" % (what, key))
    return v


def _check_name(name, what):
    if not valid_segment(name):
        raise SheetError("rules: invalid %s name %r" % (what, name))
    if name in RESERVED:
        raise SheetError("rules: %s name %r is reserved" % (what, name))


# ------------------------------------------------------------------ sheet

class HistoryFile:
    __slots__ = ("path", "stem", "index", "events", "rel")

    def __init__(self, path, stem, index, events, rel):
        self.path = path
        self.stem = stem
        self.index = index
        self.events = events
        self.rel = rel


class Sheet:
    """A loaded character: manifest + model + history files."""

    def __init__(self, path, manifest, model, history_patterns, history, file_warnings):
        self.path = path
        self.dir = os.path.dirname(path)
        self.manifest = manifest
        self.model = model
        self.id = manifest.get("id")
        self.name = manifest.get("name")
        self.meta = manifest.get("meta") or {}
        self.history_patterns = history_patterns
        self.history = history
        self.file_warnings = file_warnings

    def with_history(self, history):
        return Sheet(self.path, self.manifest, self.model, self.history_patterns,
                     history, self.file_warnings)


def manifest_path(path):
    if os.path.isdir(path):
        path = os.path.join(path, "sheet.json")
    return os.path.abspath(path)


def load_history_file(path, index, base_dir):
    """→ (HistoryFile, [warnings])."""
    stem = os.path.splitext(os.path.basename(path))[0]
    rel = _display(path, base_dir)
    warnings = []
    events = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append({"code": "invalid-event",
                         "message": "%s: unreadable history file (%s); skipped" % (rel, exc)})
        data = None
    if data is not None:
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            events = data["events"]
        else:
            warnings.append({"code": "invalid-event",
                             "message": "%s: history file must be an object with an "
                                        "events array; skipped" % rel})
    return HistoryFile(path, stem, index, events, rel), warnings


def load_sheet(path):
    """Load ``sheet.json`` (or its directory). Raises SheetError on fatal input."""
    mpath = manifest_path(path)
    manifest = read_json(mpath, "sheet.json")
    if not isinstance(manifest, dict):
        raise SheetError("sheet.json must be a JSON object: %s" % mpath)
    for f in ("id", "name", "rules", "shape", "catalog", "history"):
        if f not in manifest:
            raise SheetError("sheet.json missing required field %r: %s" % (f, mpath))
    base = os.path.dirname(mpath)
    rules, _ = load_merged(manifest["rules"], base, "rules")
    shape, _ = load_merged(manifest["shape"], base, "shape")
    catalog, _ = load_merged(manifest["catalog"], base, "catalog")
    model = Model(rules, shape, catalog)
    patterns = manifest["history"]
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise SheetError("sheet.json history must be a list of paths/globs")
    files = expand_history(patterns, base)
    history = []
    warnings = []
    for i, p in enumerate(files):
        hf, w = load_history_file(p, i, base)
        history.append(hf)
        warnings.extend(w)
    return Sheet(mpath, manifest, model, patterns, history, warnings)
