import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.zzz_resources import cli


class CliCommandTests(unittest.TestCase):
    def test_list_resources_includes_all_four_types(self):
        args = SimpleNamespace(dest="C:\\resources")
        output = io.StringIO()
        with (
            patch.object(cli, "read_manifest", return_value=[]),
            patch.object(cli, "_manifest_path", side_effect=lambda kind, dest: Path(dest) / f"{kind}.csv"),
            redirect_stdout(output),
        ):
            cli.cmd_list(args)

        text = output.getvalue()
        for kind in ("wallpapers", "cinema", "goodwill", "agent_videos"):
            self.assertIn(f"{kind}:", text)

    def test_remote_check_normalizes_before_comparison(self):
        args = SimpleNamespace(type="cinema", dest="C:\\resources")
        current = [{"relative_path": "动画.gif"}]

        def normalize(records, dest):
            records[0]["relative_path"] = "动画.webp"
            return records

        def compare(old, records):
            self.assertEqual(records[0]["relative_path"], "动画.webp")
            return ([{"remote_status": "unchanged"}], records)

        with (
            patch.object(cli, "build_records", return_value=current),
            patch.object(cli, "normalize_local_formats", side_effect=normalize) as normalize_mock,
            patch.object(cli, "read_manifest", return_value=[]),
            patch.object(cli, "compare_remote_records", side_effect=compare),
            patch.object(cli, "write_report"),
            patch.object(cli, "save_by_type"),
            patch.object(cli, "_report_path", return_value=Path("report.csv")),
            redirect_stdout(io.StringIO()),
        ):
            cli.cmd_check_remote(args)

        normalize_mock.assert_called_once_with(current, args.dest)


if __name__ == "__main__":
    unittest.main()
