#!/usr/bin/env python3
"""Event-sourced character sheets.

A character is resolved, not stored: a ledger of dated events
(``history/*.json``), folded up to a date, against a rules pack.

    sheet.py resolve SHEET [--at D] [--gm|--player] [--provenance on|off] [--compact]
    sheet.py export SHEET [--at D] [--provenance on|off] [--key NAME]
    sheet.py validate SHEET [--at D] [--strict] [--json]
    sheet.py quote SHEET KEY [--by N] [--at D] [--json]
    sheet.py add SHEET KEY [--by N] [--cost N | --no-cost] --date D --source S ...
    sheet.py gain SHEET list.NAME --id ID [--name S] [--text S] [--set k=v ...] --date D --source S ...
    sheet.py edit SHEET TARGET [--id ID] --set k=v ... [--unset k ...] --date D --source S ...
    sheet.py retire SHEET TARGET [--id ID] --date D --source S ...
    sheet.py event SHEET --file PATH|- --source S [--date D]
    sheet.py history SHEET [KEY] [--at D] [--json]
    sheet.py diff SHEET --from D --to D [--player] [--json]

SHEET is a sheet.json or its directory. stdout carries the artifact only;
warnings go to stderr. Exit 0 ok, 1 validate --strict with warnings, 2 fatal.
Guide: references/sheet-guide.md
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheetlib import (SheetError, export_js, load_sheet, quote, resolve_full,  # noqa: E402
                      run_fold, to_json)
from sheetlib import dates  # noqa: E402
from sheetlib.expr import normalise  # noqa: E402
from sheetlib.fold import NullSink, check_event  # noqa: E402
from sheetlib import writer  # noqa: E402


# ------------------------------------------------------------------ io

def out(text):
    if not text.endswith("\n"):
        text += "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def err(text):
    sys.stderr.buffer.write((text + "\n").encode("utf-8"))
    sys.stderr.buffer.flush()


def emit_warnings(warnings, quiet):
    if quiet:
        return
    for w in warnings:
        line = "sheet: warning [%s] %s" % (w["code"], w["message"])
        if w.get("ref"):
            line += " (%s)" % w["ref"]
        err(line)


def fmt(v):
    v = normalise(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return "-"
    return str(v)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        err("sheet: error: %s" % message)
        err(self.format_usage().rstrip())
        sys.exit(2)


def date_arg(value):
    if not dates.is_valid(value):
        raise argparse.ArgumentTypeError(
            "invalid date %r (use YYYY, YYYY-MM or YYYY-MM-DD; prose dates are not accepted)"
            % value)
    return value


def number_arg(value):
    try:
        v = json.loads(value)
    except ValueError:
        v = None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise argparse.ArgumentTypeError("not a number: %r" % value)
    return v


def kv_arg(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected k=v, got %r" % value)
    k, v = value.split("=", 1)
    try:
        v = json.loads(v)
    except ValueError:
        pass
    return k, v


def rel(path):
    try:
        return os.path.relpath(path).replace(os.sep, "/")
    except ValueError:
        return path


# ------------------------------------------------------------------ commands

def cmd_resolve(a):
    sheet = load_sheet(a.sheet)
    view = "player" if a.player else "gm"
    doc, res = resolve_full(sheet, at=a.at, view=view, provenance=a.provenance == "on")
    out(to_json(doc, compact=a.compact))
    emit_warnings(res.warnings, a.quiet)
    return 0


def cmd_export(a):
    sheet = load_sheet(a.sheet)
    doc, res = resolve_full(sheet, at=a.at, view="player", provenance=a.provenance == "on")
    out(export_js(doc, a.sheet, at=a.at, key=a.key))
    emit_warnings(res.warnings, a.quiet)
    return 0


def cmd_validate(a):
    sheet = load_sheet(a.sheet)
    doc, res = resolve_full(sheet, at=a.at, view="gm")
    anchors = doc["anchors"]
    if a.json:
        out(json.dumps({"at": a.at, "warnings": doc["warnings"], "anchors": anchors,
                        "notices": doc["notices"]}, ensure_ascii=False, indent=2))
    else:
        lines = ["%s at %s" % (sheet.id, a.at or "latest")]
        lines.append("warnings: %d" % len(doc["warnings"]))
        for w in doc["warnings"]:
            lines.append("  [%s] %s%s" % (w["code"], w["message"],
                                          " (%s)" % w["ref"] if w.get("ref") else ""))
        lines.append("anchors: %d" % len(anchors))
        for an in anchors:
            op = [k for k in ("at_least", "at_most", "is", "has") if k in an][0]
            lines.append("  [%s] %s %s %s %s (folded %s; %s %s)"
                         % ("ok" if an["satisfied"] else "UNSATISFIED", an["id"], an["key"], op,
                            fmt(an[op]), fmt(an["folded"]), an["date"],
                            (an.get("from") or [""])[0]))
        lines.append("notices: %d" % len(doc["notices"]))
        for n in doc["notices"]:
            lines.append("  [%s] %s%s" % (n["code"], n["message"],
                                          " (span %s)" % n["span"] if n.get("span") else ""))
        out("\n".join(lines))
    if a.strict and doc["warnings"]:
        return 1
    return 0


def cmd_quote(a):
    sheet = load_sheet(a.sheet)
    q = quote(sheet, a.key, by=a.by, at=a.at)
    if a.json:
        out(json.dumps(q, ensure_ascii=False, indent=2))
    elif not q["priced"]:
        out("%s %s→%s: no cost defined" % (q["key"], fmt(q["from"]), fmt(q["to"])))
    else:
        costs = [fmt(s["cost"]) for s in q["steps"]] or ["0"]
        out("%s %s→%s: %s = %s %s" % (q["key"], fmt(q["from"]), fmt(q["to"]),
                                       " + ".join(costs), fmt(q["total"]), q["currency"]))
    return 0


def _write(a, sheet, effects):
    path, _ = writer.glob_guard(sheet, a.source)
    ev = writer.make_event(a.date, a.source, effects, when=a.when, note=a.note, seq=a.seq,
                           gm_only=a.gm_only, free=a.free)
    fatal, probs = check_event(ev)
    if fatal or probs:
        raise SheetError("malformed event: %s" % "; ".join([fatal] if fatal else probs))
    if getattr(a, "autocost", True):
        ev = writer.autofill_cost(sheet, path, a.source, ev,
                                  cost=getattr(a, "cost", None),
                                  no_cost=getattr(a, "no_cost", False))
    return _finish(a, sheet, path, [ev])


def _finish(a, sheet, path, events):
    path, relpath, final = writer.append(sheet, a.source, events, dry_run=a.dry_run)
    head = ("DRY RUN " if a.dry_run else "") + rel(path)
    body = final[0] if len(final) == 1 else final
    out(head + "\n" + json.dumps(body, ensure_ascii=False, indent=2))
    after = writer.with_appended(sheet, path, final) if a.dry_run else load_sheet(a.sheet)
    res = run_fold(after)
    emit_warnings(res.warnings, a.quiet)
    return 0


def _meta(a):
    m = {}
    if getattr(a, "name", None):
        m["name"] = a.name
    if getattr(a, "group", None):
        m["group"] = a.group
    return m


def cmd_add(a):
    sheet = load_sheet(a.sheet)
    eff = {"add": a.key, "by": a.by}
    eff.update(_meta(a))
    return _write(a, sheet, [eff])


def cmd_gain(a):
    sheet = load_sheet(a.sheet)
    if not a.target.startswith("list."):
        raise SheetError("gain needs a list.NAME target")
    entry = {}
    if a.name:
        entry["name"] = a.name
    if a.text:
        entry["text"] = a.text
    for k, v in a.set or []:
        entry[k] = v
    return _write(a, sheet, [{"gain": a.target, "id": a.id, "entry": entry}])


def cmd_edit(a):
    sheet = load_sheet(a.sheet)
    fields = {k: v for k, v in (a.set or [])}
    for k in a.unset or []:
        fields[k] = None
    if not fields:
        raise SheetError("edit needs --set or --unset")
    eff = {"edit": a.target}
    if a.id:
        eff["id"] = a.id
    eff["fields"] = fields
    a.autocost = False
    return _write(a, sheet, [eff])


def cmd_retire(a):
    sheet = load_sheet(a.sheet)
    eff = {"retire": a.target}
    if a.id:
        eff["id"] = a.id
    a.autocost = False
    return _write(a, sheet, [eff])


def cmd_event(a):
    sheet = load_sheet(a.sheet)
    writer.glob_guard(sheet, a.source)
    try:
        if a.file == "-":
            text = sys.stdin.buffer.read().decode("utf-8")
        else:
            with open(a.file, encoding="utf-8") as fh:
                text = fh.read()
        data = json.loads(text)
    except (OSError, ValueError) as exc:
        raise SheetError("cannot read events from %s: %s" % (a.file, exc))
    if isinstance(data, dict) and "events" in data:
        events = data["events"]
    elif isinstance(data, list):
        events = data
    else:
        events = [data]
    if not isinstance(events, list) or not events:
        raise SheetError("no events in %s" % a.file)
    problems = []
    final = []
    for i, ev in enumerate(events):
        if isinstance(ev, dict):
            ev = dict(ev)
            if "date" not in ev and a.date:
                ev["date"] = a.date
            ev.setdefault("source", a.source)
            for flag, key in ((a.when, "when"), (a.note, "note")):
                if flag and key not in ev:
                    ev[key] = flag
            if a.gm_only and "gm_only" not in ev:
                ev["gm_only"] = True
            if a.free and "free" not in ev:
                ev["free"] = a.free
            if a.seq is not None and "seq" not in ev:
                ev["seq"] = a.seq
        fatal, probs = check_event(ev)
        for p in ([fatal] if fatal else probs):
            problems.append("event %d: %s" % (i + 1, p))
        final.append(ev)
    if problems:
        raise SheetError("malformed events, nothing written:\n  " + "\n  ".join(problems))
    path, _ = writer.target_path(sheet, a.source)
    return _finish(a, sheet, path, final)


def _touches(eff, key):
    for op in ("set", "add", "gain", "edit", "retire", "anchor"):
        t = eff.get(op)
        if isinstance(t, str) and (t == key or t.startswith(key + ".") or key.startswith(t + ".")):
            return True
    for op in ("start", "end"):
        if eff.get(op) == key or eff.get("id") == key and op in eff:
            return True
    return False


def cmd_history(a):
    sheet = load_sheet(a.sheet)
    res = run_fold(sheet, at=a.at, sink=NullSink())
    rows = []
    for e in res.events:
        effs = e.effects
        if a.key and not any(_touches(x, a.key) for x in effs):
            continue
        rows.append(e)
    if a.json:
        items = []
        for e in rows:
            item = {"ref": e.ref}
            item.update(e.raw)
            items.append(item)
        out(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        lines = []
        for e in rows:
            effs = "; ".join(json.dumps(x, ensure_ascii=False) for x in e.effects)
            lines.append("%s  %s  %s  %s" % (e.date, e.ref, e.when or "-", effs))
        out("\n".join(lines) if lines else "(no events)")
    return 0


def cmd_diff(a):
    sheet = load_sheet(a.sheet)
    view = "player" if a.player else "gm"
    d1, _ = resolve_full(sheet, at=a.from_, view=view)
    d2, _ = resolve_full(sheet, at=a.to, view=view)
    v1, v2 = d1["values"], d2["values"]
    changed = {k: [v1[k], v2[k]] for k in v2 if k in v1 and v1[k] != v2[k]}
    added = {k: v2[k] for k in v2 if k not in v1}
    removed = {k: v1[k] for k in v1 if k not in v2}
    dchanged = {k: [d1["derived"].get(k), v] for k, v in d2["derived"].items()
                if d1["derived"].get(k) != v}
    lists = {}
    for name in list(dict.fromkeys(list(d1["lists"]) + list(d2["lists"]))):
        ids1 = [e["id"] for e in d1["lists"].get(name, [])]
        ids2 = [e["id"] for e in d2["lists"].get(name, [])]
        g = [i for i in ids2 if i not in ids1]
        r = [i for i in ids1 if i not in ids2]
        if g or r:
            lists[name] = {"gained": g, "retired": r}
    s1 = {s["id"]: s for s in d1["spans"]}
    started = [s["id"] for s in d2["spans"] if s["id"] not in s1]
    ended = [s["id"] for s in d2["spans"] if not s["open"]
             and (s["id"] not in s1 or s1[s["id"]]["open"])]
    report = {"from": a.from_, "to": a.to, "view": view,
              "values": {"changed": changed, "added": added, "removed": removed},
              "derived": dchanged, "lists": lists,
              "spans": {"started": started, "ended": ended}}
    if a.json:
        out(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    lines = ["diff %s → %s (%s view)" % (a.from_, a.to, view)]
    if changed or added or removed:
        lines.append("values:")
        for k, (x, y) in changed.items():
            lines.append("  ~ %s: %s → %s" % (k, fmt(x), fmt(y)))
        for k, v in added.items():
            lines.append("  + %s: %s" % (k, fmt(v)))
        for k, v in removed.items():
            lines.append("  - %s (was %s)" % (k, fmt(v)))
    if dchanged:
        lines.append("derived:")
        for k, (x, y) in dchanged.items():
            lines.append("  ~ %s: %s → %s" % (k, fmt(x), fmt(y)))
    if lists:
        lines.append("lists:")
        for name, ch in lists.items():
            for i in ch["gained"]:
                lines.append("  + %s/%s" % (name, i))
            for i in ch["retired"]:
                lines.append("  - %s/%s" % (name, i))
    if started or ended:
        lines.append("spans:")
        for i in started:
            lines.append("  started %s" % i)
        for i in ended:
            lines.append("  ended %s" % i)
    if len(lines) == 1:
        lines.append("(no changes)")
    out("\n".join(lines))
    return 0


# ------------------------------------------------------------------ parser

def build_parser():
    p = Parser(prog="sheet.py", description="Event-sourced character sheets "
               "(guide: references/sheet-guide.md)")
    sub = p.add_subparsers(dest="cmd", parser_class=Parser)
    sub.required = True

    def base(name, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("sheet", metavar="SHEET", help="sheet.json or its directory")
        sp.add_argument("--quiet", action="store_true", help="suppress warnings on stderr")
        return sp

    def writer_flags(sp, date_required=True):
        sp.add_argument("--date", type=date_arg, required=date_required,
                        help="event date (YYYY[-MM[-DD]])")
        sp.add_argument("--source", required=True, help="history file stem (s03 → history/s03.json)")
        sp.add_argument("--when", help="freeform in-world label")
        sp.add_argument("--note")
        sp.add_argument("--seq", type=int)
        sp.add_argument("--gm-only", action="store_true")
        sp.add_argument("--free", metavar="REASON", help="reason no cost is paid")
        sp.add_argument("--dry-run", action="store_true")

    def cost_flags(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--cost", type=number_arg, help="override the auto-filled cost")
        g.add_argument("--no-cost", action="store_true", help="append no payment")

    sp = base("resolve", "resolved JSON to stdout")
    sp.add_argument("--at", type=date_arg)
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--gm", action="store_true", help="GM view (default)")
    g.add_argument("--player", action="store_true", help="player view (gm_only stripped)")
    sp.add_argument("--provenance", choices=("on", "off"), default="on")
    sp.add_argument("--compact", action="store_true")
    sp.set_defaults(func=cmd_resolve)

    sp = base("export", "player-view JS fragment (DATA.sheet = ...)")
    sp.add_argument("--at", type=date_arg)
    sp.add_argument("--provenance", choices=("on", "off"), default="on")
    sp.add_argument("--key", help="assign DATA.sheets[KEY] instead of DATA.sheet")
    sp.set_defaults(func=cmd_export)

    sp = base("validate", "warnings, anchors and notices")
    sp.add_argument("--at", type=date_arg)
    sp.add_argument("--strict", action="store_true", help="exit 1 if any warning")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_validate)

    sp = base("quote", "cost of raising a trait")
    sp.add_argument("key", metavar="KEY")
    sp.add_argument("--by", type=int, default=1)
    sp.add_argument("--at", type=date_arg)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_quote)

    sp = base("add", "append an add event (cost auto-filled)")
    sp.add_argument("key", metavar="KEY")
    sp.add_argument("--by", type=number_arg, default=1)
    sp.add_argument("--name")
    sp.add_argument("--group")
    cost_flags(sp)
    writer_flags(sp)
    sp.set_defaults(func=cmd_add)

    sp = base("gain", "append a list gain event")
    sp.add_argument("target", metavar="list.NAME")
    sp.add_argument("--id", required=True)
    sp.add_argument("--name")
    sp.add_argument("--text")
    sp.add_argument("--set", type=kv_arg, action="append", metavar="k=v")
    cost_flags(sp)
    writer_flags(sp)
    sp.set_defaults(func=cmd_gain)

    sp = base("edit", "append an edit event")
    sp.add_argument("target", metavar="TARGET")
    sp.add_argument("--id")
    sp.add_argument("--set", type=kv_arg, action="append", metavar="k=v")
    sp.add_argument("--unset", action="append", metavar="k")
    writer_flags(sp)
    sp.set_defaults(func=cmd_edit)

    sp = base("retire", "append a retire event")
    sp.add_argument("target", metavar="TARGET")
    sp.add_argument("--id")
    writer_flags(sp)
    sp.set_defaults(func=cmd_retire)

    sp = base("event", "append event(s) from a JSON file or stdin")
    sp.add_argument("--file", required=True, metavar="PATH|-")
    writer_flags(sp, date_required=False)
    sp.set_defaults(func=cmd_event)

    sp = base("history", "fold-ordered events")
    sp.add_argument("key", metavar="KEY", nargs="?")
    sp.add_argument("--at", type=date_arg)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_history)

    sp = base("diff", "changes between two dates")
    sp.add_argument("--from", dest="from_", type=date_arg, required=True)
    sp.add_argument("--to", type=date_arg, required=True)
    sp.add_argument("--player", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_diff)
    return p


def main(argv=None):
    parser = build_parser()
    a = parser.parse_args(argv)
    try:
        return a.func(a)
    except SheetError as exc:
        err("sheet: error: %s" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
