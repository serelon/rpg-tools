"""Shared helpers for the sheet tests: build synthetic packs in temp dirs.

All content here is synthetic and canon-free (generic ids only).
"""
import json
import os
import sys
import tempfile

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from sheetlib import load_sheet, resolve_full, run_fold  # noqa: E402

SHEET_PY = os.path.normpath(os.path.join(SCRIPTS, "sheet.py"))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures-sheet")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def ev(date, *effects, **kw):
    """Event shorthand: ev("1100", {"set": "a", "to": 1}, kind="creation")."""
    e = {"date": date, "effects": list(effects)}
    e.update(kw)
    return e


class SheetDir:
    """A throwaway pack + character on disk."""

    def __init__(self, rules, shape=None, catalog=None, history=None, patterns=None,
                 manifest=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.pack = os.path.join(self.root, "pack")
        self.dir = os.path.join(self.root, "char")
        write_json(os.path.join(self.pack, "rules.json"), rules)
        write_json(os.path.join(self.pack, "shape.json"), shape or {"id": "shape", "groups": {}})
        write_json(os.path.join(self.pack, "catalog.json"), catalog or {})
        m = {"id": "test-char", "name": "Test Character",
             "rules": "../pack/rules.json", "shape": "../pack/shape.json",
             "catalog": "../pack/catalog.json",
             "history": patterns or ["history/creation.json", "history/s*.json",
                                     "history/branch-*.json"],
             "meta": {"concept": "synthetic"}}
        m.update(manifest or {})
        write_json(os.path.join(self.dir, "sheet.json"), m)
        for stem, events in (history or {}).items():
            self.write_history(stem, events)

    def write_history(self, stem, events):
        data = events if isinstance(events, dict) else {"source": stem, "events": events}
        write_json(os.path.join(self.dir, "history", stem + ".json"), data)

    def read_history(self, stem):
        with open(os.path.join(self.dir, "history", stem + ".json"), encoding="utf-8") as fh:
            return json.load(fh)

    def load(self):
        return load_sheet(self.dir)

    def fold(self, at=None):
        return run_fold(self.load(), at=at)

    def resolve(self, at=None, view="gm", provenance=True):
        return resolve_full(self.load(), at=at, view=view, provenance=provenance)

    def cleanup(self):
        self._tmp.cleanup()


def codes(res_or_doc):
    ws = res_or_doc["warnings"] if isinstance(res_or_doc, dict) else res_or_doc.warnings
    return [w["code"] for w in ws]


def warnings_of(res, code):
    return [w for w in res.warnings if w["code"] == code]


# A small generic rules pack used across fold/cost/output tests.
BASE_RULES = {
    "id": "gen",
    "currency": "xp",
    "classes": {
        "attr": {"name": "Attributes", "min": 1, "max": 5, "groups": ["body", "mind"],
                 "cost": {"raise": "current * 4"}},
        "power": {"name": "Powers", "min": 0, "max": "cap", "catalog": "power",
                  "cost": {"new": 10, "raise": "if(id in catalog('kind', kind).powers, current * 5, current * 7)"}},
        "knack": {"name": "Knacks", "open": True, "min": 0, "max": 5, "default_group": "misc",
                  "cost": {"new": 3, "raise": "current * 2"}},
        "virtue": {"name": "Virtues", "min": 1, "max": 5, "base": 1,
                   "active": "id in table('path', path).virtues", "cost": {"raise": "current * 2"}},
    },
    "traits": {
        "attr.one": {"group": "body"},
        "attr.two": {"group": "body"},
        "attr.three": {"group": "mind"},
        "kind": {"type": "text", "catalog": "kind"},
        "path": {"type": "text"},
        "level": {"type": "number"},
        "xp": {"type": "number", "min": 0},
        "tier": {"type": "enum", "values": ["low", "mid", "high"],
                 "cost": {"raise": "target * 3"}},
        "bond": {"type": "compound", "parts": {
            "who": {"type": "text"},
            "grip": {"type": "rating", "min": 0, "max": 3, "cost": {"raise": "target"}},
            "mood": {"type": "enum", "values": ["cold", "warm"]}}},
        "mentor": {"type": "relation", "gm_only": True},
        "virtue.alpha": {}, "virtue.beta": {}, "virtue.gamma": {}, "virtue.delta": {},
    },
    "tables": {
        "level": {"rows": {"1": {"cap": 3}, "2": {"cap": 4}, "3": {"cap": 5}}},
        "path": {"rows": {"first": {"name": "First Path", "virtues": ["alpha", "beta"]},
                          "second": {"name": "Second Path", "virtues": ["gamma", "delta"]}}},
    },
    "derived": {"cap": "table('level', level).cap",
                "pool": {"expr": "cap * 2", "name": "Pool"}},
    "lists": {"marks": {"name": "Marks"},
              "items": {"name": "Items", "cap": "if(cap == None, None, cap - 1)"}},
    "spans": {"sleep": {"name": "Sleep"}},
}

BASE_CATALOG = {
    "kind": {"k1": {"name": "Kind One", "powers": ["glow", "hum"], "text": "First kind."},
             "k2": {"name": "Kind Two", "powers": ["drift"]}},
    "power": {"glow": {"name": "Glow", "text": "Gives light.",
                       "levels": {"1": {"name": "Spark", "text": "A spark."},
                                  "2": {"name": "Lamp", "text": "A lamp."},
                                  "3": {"name": "Sun", "text": "A sun."}}},
              "hum": {"name": "Hum"}, "drift": {"name": "Drift"}},
}


def creation_event(date="1100", **kw):
    return ev(date,
              {"set": "kind", "to": "k1"},
              {"set": "path", "to": "first"},
              {"set": "level", "to": 1},
              {"set": "xp", "to": 0},
              {"set": "attr.one", "to": 2},
              {"set": "virtue.alpha", "to": 2},
              {"set": "virtue.beta", "to": 1},
              kind="creation", **kw)
