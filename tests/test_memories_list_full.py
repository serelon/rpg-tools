"""memories.py list --full prints every filtered memory whole, text included."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memories.py"

MEMORIES = [
    {"id": "anchor-one", "campaign": "toy", "type": "vivid-moment", "title": "Anchor One",
     "text": "The first anchor's words.", "session": "s01", "tags": ["core"]},
    {"id": "anchor-two", "campaign": "toy", "type": "relationship", "title": "Anchor Two",
     "text": "The second anchor's words.", "session": "s02", "tags": ["core", "bond"]},
    {"id": "passing", "campaign": "toy", "type": "sensory", "title": "Passing",
     "text": "Not an anchor.", "session": "s02", "tags": ["weather"]},
]


class ListFull(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "memories").mkdir()
        (root / "memories" / "toy.json").write_text(json.dumps(MEMORIES), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_list(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPT), "list", *args],
                              cwd=self.tmp.name, capture_output=True, text=True,
                              encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_full_prints_text_of_every_match(self):
        out = self.run_list("--tag", "core", "--full", "--campaign", "toy")
        self.assertIn("The first anchor's words.", out)
        self.assertIn("The second anchor's words.", out)
        self.assertNotIn("Not an anchor.", out)
        self.assertIn("Total: 2 memories", out)

    def test_full_keeps_session_order(self):
        out = self.run_list("--tag", "core", "--full")
        self.assertLess(out.index("Anchor One"), out.index("Anchor Two"))

    def test_plain_list_still_titles_only(self):
        out = self.run_list("--tag", "core")
        self.assertIn("Anchor One", out)
        self.assertNotIn("The first anchor's words.", out)

    def test_plain_list_shows_ids_for_get(self):
        out = self.run_list("--tag", "core")
        self.assertIn("anchor-one", out)

    def test_exclude_tag_leaves_the_rest(self):
        out = self.run_list("--exclude-tag", "core")
        self.assertIn("Passing", out)
        self.assertNotIn("Anchor One", out)
        self.assertIn("Total: 1 memories", out)

    def test_exclude_tag_is_exact_and_stacks(self):
        out = self.run_list("--exclude-tag", "cor")
        self.assertIn("Total: 3 memories", out)
        out = self.run_list("--exclude-tag", "bond", "--exclude-tag", "weather")
        self.assertIn("Anchor One", out)
        self.assertIn("Total: 1 memories", out)
        out = self.run_list("--exclude-tag", "bond,weather")
        self.assertIn("Total: 1 memories", out)


if __name__ == "__main__":
    unittest.main()
