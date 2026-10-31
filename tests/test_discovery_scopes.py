"""Opt-in discovery scopes (campaign.json "discover") and only_dir / memories.py --dir."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from lib.discovery import discover_data  # noqa: E402


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class CampaignScopes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        c = self.root / "campaigns"
        write(c / "opted" / "characters" / "base.json", {"id": "base"})
        write(c / "opted" / "subsettings" / "1130-era" / "characters" / "era.json", {"id": "era"})
        write(c / "opted" / "branches" / "pov" / "characters" / "pov.json", {"id": "pov"})
        write(c / "opted" / "campaign.json", {"discover": ["subsettings/*", "branches/*"]})
        write(c / "plain" / "branches" / "au" / "characters" / "hidden.json", {"id": "hidden"})
        self.warnings = []

    def tearDown(self):
        self.tmp.cleanup()

    def found(self):
        return set(discover_data("characters", self.root, on_warning=self.warnings.append))

    def test_opted_in_campaign_exposes_its_scopes(self):
        self.assertTrue({"base", "era", "pov"} <= self.found())

    def test_campaign_without_config_is_unchanged(self):
        self.assertNotIn("hidden", self.found())

    def test_bad_config_warns_and_keeps_the_root_folder(self):
        (self.root / "campaigns" / "opted" / "campaign.json").write_text("{nope", encoding="utf-8")
        found = self.found()
        self.assertIn("base", found)
        self.assertNotIn("era", found)
        self.assertTrue(any("campaign.json" in w for w in self.warnings))

    def test_only_dir_loads_that_folder_alone(self):
        only = self.root / "campaigns" / "opted" / "branches" / "pov" / "characters"
        found = set(discover_data("characters", self.root, on_warning=self.warnings.append,
                                  only_dir=only))
        self.assertEqual(found, {"pov"})


class MemoriesDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        write(root / "memories" / "a.json",
              [{"id": "here", "campaign": "toy", "title": "Here", "text": "x", "tags": ["core"]}])
        write(root / "other" / "b.json",
              [{"id": "there", "campaign": "toy", "title": "There", "text": "y", "tags": ["core"]}])

    def tearDown(self):
        self.tmp.cleanup()

    def run_list(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "memories.py"), "list", *args],
                              cwd=self.tmp.name, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_dir_reads_only_that_folder(self):
        out = self.run_list("--tag", "core", "--dir", "other")
        self.assertIn("There", out)
        self.assertNotIn("Here", out)

    def test_without_dir_discovery_is_unchanged(self):
        out = self.run_list("--tag", "core")
        self.assertIn("Here", out)
        self.assertNotIn("There", out)


if __name__ == "__main__":
    unittest.main()
