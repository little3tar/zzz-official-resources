import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.zzz_resources import storage


def gif_record():
    return {
        "resource_type": "cinema",
        "filename": "待机动画.gif",
        "relative_path": "代理档案\\测试代理人\\角色展示\\待机动画.gif",
        "ext": ".gif",
        "url": "https://example.invalid/animation.gif",
    }


def only_webp_exists(path):
    return str(path).lower().endswith(".webp")


class StorageFormatTests(unittest.TestCase):
    def test_existing_webp_normalizes_remote_gif_record(self):
        record = gif_record()
        with patch.object(storage.Path, "exists", autospec=True, side_effect=only_webp_exists):
            result = storage.normalize_local_formats([record], "C:\\resources")

        self.assertIs(result[0], record)
        self.assertEqual(record["filename"], "待机动画.webp")
        self.assertTrue(record["relative_path"].endswith("待机动画.webp"))
        self.assertEqual(record["ext"], ".webp")

    def test_download_reuses_existing_webp_without_request(self):
        record = gif_record()
        with (
            patch.object(storage.Path, "exists", autospec=True, side_effect=only_webp_exists),
            patch.object(storage.Path, "stat", autospec=True, return_value=SimpleNamespace(st_size=123)),
            patch.object(storage, "request_bytes") as request_bytes,
        ):
            downloaded, skipped = storage.download_records([record], "C:\\resources")

        self.assertEqual((downloaded, skipped), (0, 1))
        self.assertEqual(record["status"], "exists")
        self.assertEqual(record["bytes"], 123)
        request_bytes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
