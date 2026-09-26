"""Appending events to ``history/<source>.json`` (spec S9 writers).

Writers only append: existing events are never modified (fixing an old event
is a deliberate hand-edit — errata doctrine). The target file must be matched
by the manifest's history globs, else nothing is written: an unloaded write
would be silently lost.
"""
import json
import os
import re

from .expr import SheetError, is_number
from .fold import NullSink, check_event, run_fold
from .loader import HistoryFile, expand_history, history_matches

SOURCE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
EVENT_ORDER = ("date", "when", "source", "seq", "kind", "effects", "note", "gm_only",
               "free", "satisfies")


def target_path(sheet, source):
    if not isinstance(source, str) or not SOURCE_RE.match(source) or source.endswith(".json"):
        raise SheetError("invalid --source %r (a file stem like s03)" % (source,))
    rel = "history/%s.json" % source
    return os.path.join(sheet.dir, "history", source + ".json"), rel


def glob_guard(sheet, source):
    path, rel = target_path(sheet, source)
    if not any(history_matches(path, p, sheet.dir) for p in sheet.history_patterns):
        raise SheetError("%s is not matched by sheet.json history globs (%s)"
                         % (rel, ", ".join(sheet.history_patterns)))
    return path, rel


def make_event(date, source, effects, when=None, note=None, seq=None, gm_only=False,
               free=None):
    ev = {"date": date}
    if when:
        ev["when"] = when
    ev["source"] = source
    if seq is not None:
        ev["seq"] = seq
    ev["effects"] = effects
    if note:
        ev["note"] = note
    if gm_only:
        ev["gm_only"] = True
    if free:
        ev["free"] = free
    return ev


def order_event(ev):
    out = {k: ev[k] for k in EVENT_ORDER if k in ev}
    for k, v in ev.items():
        if k not in out:
            out[k] = v
    return out


def with_appended(sheet, path, new_events):
    """A copy of the sheet whose history has ``new_events`` appended to ``path``."""
    path = os.path.normpath(os.path.abspath(path))
    existing = {hf.path: hf for hf in sheet.history}
    files = expand_history(sheet.history_patterns, sheet.dir, extra=[path])
    history = []
    for i, p in enumerate(files):
        hf = existing.get(p)
        events = list(hf.events) if hf is not None else []
        if p == path:
            events = events + list(new_events)
        stem = os.path.splitext(os.path.basename(p))[0]
        history.append(HistoryFile(p, stem, i, events,
                                   hf.rel if hf is not None else os.path.relpath(p, sheet.dir)))
    return sheet.with_history(history)


def _existing_count(sheet, path):
    path = os.path.normpath(os.path.abspath(path))
    for hf in sheet.history:
        if hf.path == path:
            return len(hf.events)
    return 0


def autofill_cost(sheet, path, source, event, cost=None, no_cost=False):
    """Fold with the event tentatively inserted; append the payment effect(s)."""
    if no_cost:
        return event
    tentative = with_appended(sheet, path, [event])
    res = run_fold(tentative, sink=NullSink())
    ref = "%s#%d" % (source, _existing_count(sheet, path) + 1)
    expected = res.expected.get(ref, {})
    effects = list(event["effects"])
    if cost is not None:
        cur = next(iter(expected), None) or sheet.model.currency
        if cost:
            effects.append({"add": cur, "by": -cost})
    else:
        for cur, amt in expected.items():
            if is_number(amt) and amt > 0:
                effects.append({"add": cur, "by": -amt})
    out = dict(event)
    out["effects"] = effects
    return out


def read_history_raw(path, source):
    if not os.path.exists(path):
        return {"source": source, "events": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise SheetError("cannot append to %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise SheetError("cannot append to %s: not an object with an events array" % path)
    return data


def write_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)


def append(sheet, source, events, dry_run=False):
    """Append already-final events. Returns ``(path, rel, events)``."""
    path, rel = glob_guard(sheet, source)
    for ev in events:
        fatal, probs = check_event(ev)
        if fatal or probs:
            raise SheetError("malformed event: %s" % "; ".join([fatal] if fatal else probs))
    data = read_history_raw(path, source)
    if not dry_run:
        data["events"] = list(data["events"]) + [order_event(e) for e in events]
        write_atomic(path, data)
    return path, rel, [order_event(e) for e in events]
