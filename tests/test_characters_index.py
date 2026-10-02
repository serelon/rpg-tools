"""characters.py index / group: the cast index, built from each profile's `index` block
and a `kind: cast-groups` file beside the profiles."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "characters.py"

GROUPS = {"kind": "cast-groups", "groups": [
    {"id": "the-house", "name": "The house", "when": "When she's home."},
    {"id": "the-glen", "name": "The glen", "when": "Anywhere in the glen."},
]}


def profile(cid, name, index=None, role="r"):
    char = {"id": cid, "name": name, "minimal": {"role": role, "voice": f'"{name} speaks."'}}
    if index is not None:
        char["index"] = index
    return char


CAST = [
    profile("mother", "Mother", {"line": "Her mother, mortal", "groups": ["the-house", "the-glen"],
                                 "weight": "core"}),
    profile("father", "Father", {"line": "Her father", "groups": ["the-house"], "weight": "major",
                                 "status": "dead", "status_note": "killed by the rider"}),
    profile("neighbour", "Neighbour", {"line": "Down the glen", "groups": ["the-glen"],
                                       "weight": "minor"}),
    profile("stray", "Stray", role="Someone new"),
]


class CastIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cdir = Path(self.tmp.name) / "characters"
        cdir.mkdir()
        for c in CAST:
            (cdir / f"{c['id']}.json").write_text(json.dumps(c), encoding="utf-8")
        (cdir / "cast-groups.json").write_text(json.dumps(GROUPS), encoding="utf-8")
        # a resolved sheet beside the profiles is not a character
        (cdir / "mother-sheet.json").write_text(json.dumps({"format": "sheet/1", "groups": []}),
                                               encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.tmp.name,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout, proc.stderr

    def test_index_groups_people_under_their_first_group(self):
        out, _ = self.run_cli("index")
        house = out.index("## The house")
        glen = out.index("## The glen")
        self.assertTrue(house < out.index("**Mother** `mother`") < glen)
        self.assertIn("core: Her mother, mortal *(also: The glen)*", out)
        self.assertIn("major · dead (killed by the rider): Her father", out)
        self.assertEqual(out.count("**Mother**"), 1)

    def test_heaviest_first_within_a_group(self):
        out, _ = self.run_cli("index")
        self.assertLess(out.index("**Mother**"), out.index("**Father**"))

    def test_accented_names_sort_with_their_letter(self):
        cdir = Path(self.tmp.name) / "characters"
        for cid, name in (("e", "Étaín"), ("m", "Muirenn")):
            c = profile(cid, name, {"groups": ["the-glen"], "weight": "minor"})
            (cdir / f"{cid}.json").write_text(json.dumps(c), encoding="utf-8")
        out, _ = self.run_cli("index")
        self.assertLess(out.index("**Étaín**"), out.index("**Muirenn**"))

    def test_unindexed_profiles_are_listed_and_warned(self):
        out, err = self.run_cli("index")
        self.assertIn("## Not yet indexed", out)
        self.assertIn("**Stray** `stray`: Someone new", out)
        self.assertIn("1 profile(s) have no index block", err)

    def test_sheets_and_group_files_are_not_cast(self):
        out, _ = self.run_cli("index")
        self.assertIn("# The cast (4)", out)
        self.assertNotIn("Unknown", out)

    def test_group_loads_every_member_with_status(self):
        out, _ = self.run_cli("group", "the-glen")
        self.assertIn("# The glen (2)", out)
        self.assertIn("# Mother", out)
        self.assertIn("# Neighbour", out)
        out, _ = self.run_cli("group", "the-house")
        self.assertIn("[dead: killed by the rider]", out)

    def test_group_prefix_and_unknown(self):
        out, _ = self.run_cli("group", "the-gl")
        self.assertIn("# The glen", out)
        proc = subprocess.run([sys.executable, str(SCRIPT), "group", "nowhere"], cwd=self.tmp.name,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("the-house, the-glen", proc.stderr)

    def test_voice_already_quoted_is_not_quoted_twice(self):
        out, _ = self.run_cli("get", "mother")
        self.assertIn('**Voice:** "Mother speaks."', out)
        self.assertNotIn('""', out)


if __name__ == "__main__":
    unittest.main()
