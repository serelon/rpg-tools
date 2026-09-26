"""Subprocess tests for scripts/sheet.py (spec S9)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheet_helpers import SHEET_PY  # noqa: E402

TOY = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                    "examples", "sheet", "d20-lite"))
NAME = "Éowa Ñí Łark 雪"  # synthetic non-ASCII name


def run(*args, env_encoding="unset", stdin=None, cwd=None):
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONUTF8", None)
    if env_encoding != "unset":
        env["PYTHONIOENCODING"] = env_encoding
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
    p = subprocess.run([sys.executable, SHEET_PY] + list(args), capture_output=True, env=env,
                       input=stdin, cwd=cwd, timeout=60)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pack = os.path.join(self.tmp, "d20-lite")
        shutil.copytree(TOY, self.pack)
        self.char = os.path.join(self.pack, "wren")
        mpath = os.path.join(self.char, "sheet.json")
        with open(mpath, encoding="utf-8") as fh:
            m = json.load(fh)
        m["name"] = NAME
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False)

    def hist(self, stem):
        path = os.path.join(self.char, "history", stem + ".json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def snapshot(self):
        out = {}
        hdir = os.path.join(self.char, "history")
        for n in sorted(os.listdir(hdir)):
            with open(os.path.join(hdir, n), "rb") as fh:
                out[n] = fh.read()
        return out


class TestReadCommands(CliCase):
    def test_resolve_stdout_is_json_warnings_on_stderr(self):
        code, out, err = run("resolve", self.char)
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["format"], "sheet/1")
        self.assertEqual(err, "")
        # add a warning: an unpaid raise
        with open(os.path.join(self.char, "history", "s03.json"), "w", encoding="utf-8") as fh:
            json.dump({"source": "s03", "events": [
                {"date": "413", "effects": [{"add": "skill.climb"}]}]}, fh)
        code, out, err = run("resolve", self.char)
        self.assertEqual(code, 0)
        json.loads(out)
        self.assertIn("sheet: warning [no-cost] s03#1: nothing paid, quote 1 training (s03#1)", err)
        code, out, err = run("resolve", self.char, "--quiet")
        self.assertEqual(err, "")

    def test_utf8_output_regardless_of_locale(self):
        for enc in ("unset", "ascii"):
            code, out, err = run("resolve", self.char, "--compact", env_encoding=enc)
            self.assertEqual(code, 0, err)
            self.assertIn(NAME, out)
            self.assertEqual(json.loads(out)["character"]["name"], NAME)
            code, out, err = run("export", self.char, env_encoding=enc)
            self.assertIn(NAME, out)

    def test_player_view_and_provenance(self):
        code, out, _ = run("resolve", self.char, "--player", "--provenance", "off")
        doc = json.loads(out)
        self.assertEqual(doc["view"], "player")
        self.assertNotIn("warnings", doc)
        self.assertNotIn('"from"', out)

    def test_prose_at_is_usage_error(self):
        for cmd in (["resolve", self.char, "--at", "~10th Thirdmonth, 2853 IC"],
                    ["export", self.char, "--at", "spring"],
                    ["diff", self.char, "--from", "412", "--to", "later"],
                    ["add", self.char, "xp", "--date", "someday", "--source", "s03"]):
            code, out, err = run(*cmd)
            self.assertEqual(code, 2, cmd)
            self.assertEqual(out, "")
            self.assertIn("invalid date", err)

    def test_fatal_input_exit_2(self):
        code, out, err = run("resolve", os.path.join(self.tmp, "nope"))
        self.assertEqual(code, 2)
        self.assertIn("sheet: error:", err)
        with open(os.path.join(self.pack, "rules.json"), "w", encoding="utf-8") as fh:
            fh.write("{broken")
        code, out, err = run("resolve", self.char)
        self.assertEqual((code, out), (2, ""))

    def test_usage_error_exit_2(self):
        code, _, _ = run("frobnicate", self.char)
        self.assertEqual(code, 2)
        code, _, _ = run("add", self.char, "xp")  # missing --date/--source
        self.assertEqual(code, 2)

    def test_validate_strict(self):
        code, out, _ = run("validate", self.char, "--strict")
        self.assertEqual(code, 0)
        self.assertIn("warnings: 0", out)
        self.assertIn("[overloaded]", out)
        with open(os.path.join(self.char, "history", "s03.json"), "w", encoding="utf-8") as fh:
            json.dump({"source": "s03", "events": [
                {"date": "413", "effects": [{"add": "skill.climb"}]}]}, fh)
        code, out, _ = run("validate", self.char)
        self.assertEqual(code, 0)
        code, out, _ = run("validate", self.char, "--strict", "--json")
        self.assertEqual(code, 1)
        rep = json.loads(out)
        self.assertEqual([w["code"] for w in rep["warnings"]], ["no-cost"])

    def test_quote(self):
        code, out, _ = run("quote", self.char, "bond.strength", "--by", "2")
        self.assertEqual(code, 0)
        self.assertEqual(out, "bond.strength 2→4: 3 + 4 = 7 training\n")
        code, out, _ = run("quote", self.char, "skill.climb", "--json")
        q = json.loads(out)
        self.assertEqual((q["from"], q["to"], q["total"]), ("none", "proficient", 1))
        code, out, _ = run("quote", self.char, "xp")
        self.assertEqual(code, 2)

    def test_history_and_diff(self):
        code, out, _ = run("history", self.char, "skill.sneak")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual([ln.split("  ")[1] for ln in lines], ["creation#1", "s01#2"])
        code, out, _ = run("history", self.char, "--json", "--at", "412-06")
        self.assertEqual([e["ref"] for e in json.loads(out)], ["creation#1", "s01#1", "s01#2"])
        code, out, _ = run("diff", self.char, "--from", "412-03", "--to", "412-10", "--json")
        rep = json.loads(out)
        self.assertEqual(rep["values"]["changed"]["skill.sneak"], ["proficient", "expert"])
        self.assertIn("patron", rep["values"]["added"])
        self.assertEqual(rep["lists"]["gear"]["gained"], ["anvil"])
        self.assertEqual(rep["spans"]["started"], ["north-road"])
        code, out, _ = run("diff", self.char, "--from", "412-03", "--to", "412-10")
        self.assertIn("~ skill.sneak: proficient → expert", out)

    def test_export(self):
        code, out, _ = run("export", self.char, "--at", "412-06", "--key", "wren")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("/* GENERATED — do not hand-edit.\n"))
        self.assertIn('(DATA.sheets = DATA.sheets || {})["wren"] = ', out)


class TestWriters(CliCase):
    W = ["--date", "413-02", "--source", "s03"]

    def test_add_appends_with_auto_cost(self):
        code, out, err = run("add", self.char, "skill.climb", *self.W, "--when", "on the cliffs")
        self.assertEqual(code, 0, err)
        self.assertTrue(out.splitlines()[0].endswith("history/s03.json"))
        data = self.hist("s03")
        self.assertEqual(data["source"], "s03")
        self.assertEqual(data["events"], [{
            "date": "413-02", "when": "on the cliffs", "source": "s03",
            "effects": [{"add": "skill.climb", "by": 1}, {"add": "training", "by": -1}]}])
        # appending again never modifies existing events
        code, out, err = run("add", self.char, "ability.wit", "--by", "1", "--no-cost",
                             "--free", "gift", *self.W)
        self.assertEqual(code, 0)
        data = self.hist("s03")
        self.assertEqual(len(data["events"]), 2)
        self.assertEqual(data["events"][1]["effects"], [{"add": "ability.wit", "by": 1}])
        self.assertEqual(data["events"][1]["free"], "gift")
        with open(os.path.join(self.char, "history", "s03.json"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith('{\n  "source": "s03",\n'))
        self.assertNotIn("\r", text)

    def test_cost_override_and_warning_after_append(self):
        code, out, err = run("add", self.char, "bond.strength", "--cost", "1", *self.W)
        self.assertEqual(code, 0)
        eff = self.hist("s03")["events"][0]["effects"]
        self.assertEqual(eff[1], {"add": "training", "by": -1})
        self.assertIn("[cost-mismatch] paid 1 training, quote 3 training", err)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        code, out, err = run("add", self.char, "skill.climb", *self.W, "--dry-run")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("DRY RUN "))
        ev = json.loads(out.split("\n", 1)[1])
        self.assertEqual(ev["effects"][1], {"add": "training", "by": -1})
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.hist("s03"))

    def test_glob_guard(self):
        before = self.snapshot()
        for extra in ([], ["--dry-run"]):
            code, out, err = run("add", self.char, "skill.climb", "--date", "413",
                                 "--source", "notes", *extra)
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertIn("history/notes.json is not matched by sheet.json history globs", err)
        self.assertEqual(self.snapshot(), before)

    def test_gain_edit_retire(self):
        code, _, err = run("gain", self.char, "list.gear", "--id", "lamp", "--name", "Lamp",
                           "--set", "weight=1", "--set", "qty=2", "--set", "tag=brass", *self.W)
        self.assertEqual(code, 0, err)
        code, _, err = run("edit", self.char, "list.gear", "--id", "lamp", "--set", "qty=3",
                           "--unset", "tag", *self.W)
        self.assertEqual(code, 0, err)
        code, _, err = run("retire", self.char, "list.gear", "--id", "anvil", *self.W)
        self.assertEqual(code, 0, err)
        evs = self.hist("s03")["events"]
        self.assertEqual(evs[0]["effects"], [{"gain": "list.gear", "id": "lamp", "entry": {
            "name": "Lamp", "weight": 1, "qty": 2, "tag": "brass"}}])
        self.assertEqual(evs[1]["effects"], [{"edit": "list.gear", "id": "lamp",
                                              "fields": {"qty": 3, "tag": None}}])
        self.assertEqual(evs[2]["effects"], [{"retire": "list.gear", "id": "anvil"}])
        code, out, _ = run("resolve", self.char)
        doc = json.loads(out)
        gear = {e["id"]: e for e in doc["lists"]["gear"]}
        self.assertNotIn("anvil", gear)
        self.assertEqual(gear["lamp"]["fields"], {"weight": 1, "qty": 3, "load": 3})
        self.assertEqual(doc["notices"], [])

    def test_event_file(self):
        path = os.path.join(self.tmp, "events.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"events": [
                {"date": "413-05", "effects": [{"start": "journey", "id": "east"}]},
                {"effects": [{"end": "journey", "id": "east"}], "date": "413-08"}]}, fh)
        code, out, err = run("event", self.char, "--file", path, "--source", "s03")
        self.assertEqual(code, 0, err)
        evs = self.hist("s03")["events"]
        self.assertEqual([e["date"] for e in evs], ["413-05", "413-08"])
        self.assertEqual(evs[0]["source"], "s03")
        # stdin, single event, --date as default
        code, out, err = run("event", self.char, "--file", "-", "--source", "s03", "--date", "414",
                             stdin=json.dumps({"effects": [{"add": "xp", "by": 10}]}).encode())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.hist("s03")["events"][2]["date"], "414")

    def test_event_file_rejection(self):
        before = self.snapshot()
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"date": "413", "effects": [{"add": "xp"}]},
                       {"date": "spring", "effects": []},
                       {"date": "413", "effects": [{"set": "xp"}]}], fh)
        code, out, err = run("event", self.char, "--file", path, "--source", "s03")
        self.assertEqual(code, 2)
        self.assertIn("event 2", err)
        self.assertIn("event 3", err)
        self.assertEqual(self.snapshot(), before)
        code, _, _ = run("event", self.char, "--file", "-", "--source", "s03", stdin=b"{nope")
        self.assertEqual(code, 2)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
