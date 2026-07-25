import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.zzz_resources import records as zzz_resources


def video_record(**overrides):
    record = {
        "resource_type": "agent_videos",
        "entry_id": "2091",
        "module_id": "",
        "category": "不可售影像",
        "group": "诺姆·霍洛维尔",
        "source_name": "不可售影像丨诺姆·霍洛维尔",
        "filename": "不可售影像.mp4",
        "relative_path": "代理档案\\诺姆·霍洛维尔\\不可售影像.mp4",
        "url": "https://prod-vod-sign.miyoushe.com/video-a?auth_key=old-token",
        "definition": "2K",
        "content_length": "100",
        "status": "ok",
    }
    record.update(overrides)
    return record


class RemoteCompareTests(unittest.TestCase):
    def compare_one(self, old, current):
        report, manifest = zzz_resources.compare_remote_records([old], [current])
        self.assertEqual(len(report), 1)
        self.assertEqual(len(manifest), 1)
        return report[0], manifest[0]

    def test_signed_url_rotation_is_unchanged(self):
        old = video_record()
        current = video_record(url="https://prod-vod-sign.miyoushe.com/video-a?auth_key=new-token")
        report, _ = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "unchanged")

    def test_blank_url_becoming_available_is_resolved(self):
        old = video_record(url="", definition="", content_length="", key="legacy-key-with-empty-url")
        current = video_record()
        report, manifest = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "resolved")
        self.assertEqual(manifest["url"], current["url"])

    def test_fetch_failure_is_unknown_and_preserves_old_url(self):
        old = video_record(bytes="123", sha256="abc")
        current = video_record(
            url="",
            definition="",
            content_length="",
            status="bbs_fetch_failed",
        )
        report, manifest = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "unknown")
        self.assertEqual(manifest["url"], old["url"])
        self.assertEqual(manifest["definition"], old["definition"])
        self.assertEqual(manifest["sha256"], old["sha256"])
        self.assertEqual(manifest["status"], "stale_remote_metadata")

    def test_same_name_and_path_with_new_remote_object_is_changed(self):
        old = video_record()
        current = video_record(url="https://prod-vod-sign.miyoushe.com/video-b?auth_key=new-token")
        report, _ = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "changed")

    def test_same_url_with_different_comparable_size_is_changed(self):
        old = video_record(content_length="100")
        current = video_record(content_length="101")
        report, _ = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "changed")

    def test_missing_optional_metadata_does_not_create_false_change(self):
        old = video_record(definition="", content_length="")
        current = video_record(definition="2K", content_length="100")
        report, _ = self.compare_one(old, current)
        self.assertEqual(report["remote_status"], "unchanged")


if __name__ == "__main__":
    unittest.main()
