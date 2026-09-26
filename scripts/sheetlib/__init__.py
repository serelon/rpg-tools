"""Event-sourced character sheets: a ledger of dated events, folded up to a
date, against a rules pack. See ``references/sheet-guide.md``.

Public API::

    sheet = load_sheet("path/to/sheet.json")        # or its directory
    doc = resolve(sheet, at="1130-10", view="gm")   # resolved JSON (dict)
    q = quote(sheet, "class_alpha.one", by=2)       # cost of a raise
    js = export_js(resolve(sheet, view="player"), "path/to/sheet")
"""
from .expr import ExprError, SheetError
from .fold import NullSink, Sink, run_fold
from .loader import load_sheet
from .output import build, export_js, to_json

__all__ = ["SheetError", "ExprError", "load_sheet", "resolve", "resolve_full", "quote",
           "export_js", "to_json", "run_fold"]


def resolve_full(sheet, at=None, view="gm", provenance=True):
    """→ ``(doc, fold_result)``; the fold result carries all warnings."""
    res = run_fold(sheet, at=at)
    doc = build(res, view=view, provenance=provenance)
    return doc, res


def resolve(sheet, at=None, view="gm", provenance=True):
    return resolve_full(sheet, at, view, provenance)[0]


def quote(sheet, key, by=1, at=None):
    """Per-step and total cost of raising ``key`` by ``by`` at ``at``."""
    from .fold import Folder
    res = run_fold(sheet, at=at, sink=NullSink())
    m = sheet.model
    parsed = m.parse_target(key) if not key.startswith("list.") else None
    if parsed is None:
        raise SheetError("quote: %r is not a trait or compound part" % key)
    tkey, part = parsed
    td = m.tdef(tkey)
    folder = Folder(res.engine)
    folder.state = res.state
    folder.env = res.engine.env(res.state)
    cur_whole = res.state.values[tkey] if tkey in res.state.values \
        else res.engine.default(folder.env, tkey)
    d = (td.get("parts") or {}).get(part, {}) if part else td.d
    t = d.get("type", "rating")
    cur = (cur_whole or {}).get(part) if part else cur_whole
    cost = d.get("cost") if isinstance(d.get("cost"), dict) else None
    currency = (cost or {}).get("currency") or m.currency
    if t == "enum":
        vals = d.get("values") or []
        start = vals.index(cur) if cur in vals else 0
        end = max(0, min(len(vals) - 1, start + by))
        show = lambda i: vals[i]  # noqa: E731
    elif t == "rating":
        start = int(cur) if isinstance(cur, (int, float)) else 0
        end = start + by
        show = lambda i: i  # noqa: E731
    else:
        raise SheetError("quote: %s is a %s trait; only ratings and enums have costs" % (key, t))
    steps = []
    for c in range(start, end):
        exp = {}
        amt = folder._price(tkey, part, c, c + 1, exp) if cost else 0
        steps.append({"current": show(c), "target": show(c + 1), "cost": amt})
    total = sum(s["cost"] for s in steps)
    return {"key": key, "from": show(start), "to": show(end), "currency": currency,
            "priced": cost is not None, "steps": steps, "total": total}
