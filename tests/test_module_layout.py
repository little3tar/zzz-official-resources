import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class ModuleLayoutTests(unittest.TestCase):
    def test_all_modules_import(self):
        from scripts.zzz_resources import api, cli, config, records, sources, storage

        self.assertTrue(callable(api.fetch_entry))
        self.assertTrue(callable(cli.main))
        self.assertTrue(config.BLACKBOARD.startswith("https://"))
        self.assertTrue(callable(records.compare_remote_records))
        self.assertTrue(callable(sources.build_records))
        self.assertTrue(callable(storage.read_manifest))

    def test_module_entrypoint_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.zzz_resources", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("check-remote", result.stdout)


if __name__ == "__main__":
    unittest.main()
