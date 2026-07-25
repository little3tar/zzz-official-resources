"""清单、报告、下载和本地完整性检查。"""


import csv
import hashlib
import time
from collections import defaultdict
from pathlib import Path

from .api import request_bytes
from .records import revision_fingerprint, stable_key


_WEBP_HEADER = bytes("RIFF", "ascii") + b"\x00" * 8 + bytes("WEBP", "ascii")


def _manifest_dir(dest):
    d = Path(dest) / ".manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(type_name, dest):
    return _manifest_dir(dest) / f"{type_name}_manifest.csv"


def _report_path(dest):
    return _manifest_dir(dest) / "last_check_report.csv"


def write_manifest(type_name, records, dest):
    fields = [
        "resource_type",
        "key",
        "category",
        "group",
        "entry_id",
        "module_id",
        "source_name",
        "filename",
        "relative_path",
        "url",
        "definition",
        "fingerprint",
        "bytes",
        "content_length",
        "etag",
        "last_modified",
        "sha256",
        "status",
    ]
    path = _manifest_path(type_name, dest)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            r["key"] = stable_key(r)
            r["fingerprint"] = revision_fingerprint(r)
            writer.writerow({field: r.get(field, "") for field in fields})


def read_manifest(type_name, dest):
    path = _manifest_path(type_name, dest)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_by_type(records):
    grouped = defaultdict(list)
    for r in records:
        grouped[r["resource_type"]].append(r)
    return grouped


def normalize_local_formats(records, dest):
    """按现有磁盘文件修正远端记录的扩展名，并返回原记录列表。"""
    dest = Path(dest)
    for r in records:
        target = dest / r["relative_path"]
        # 官方 URL 标为 .gif，但响应体可能实际是 WebP；优先复用已修正的本地文件。
        if not target.exists() and r["relative_path"].lower().endswith(".gif"):
            alt = dest / (r["relative_path"][:-4] + ".webp")
            if alt.exists():
                r["filename"] = r["filename"][:-4] + ".webp"
                r["relative_path"] = r["relative_path"][:-4] + ".webp"
                r["ext"] = ".webp"
    return records


def save_by_type(records, dest):
    """保存时自动修正清单中与实际磁盘格式不符的扩展名。"""
    dest = Path(dest)
    normalize_local_formats(records, dest)
    for t, rows in split_by_type(records).items():
        write_manifest(t, rows, dest)


def _fix_webp_gif(body, target, r):
    """如果文件体是 WebP 但扩展名是 .gif，修正为 .webp。"""
    if target.suffix.lower() != ".gif":
        return target
    if len(body) < 12 or body[:4] != _WEBP_HEADER[:4] or body[8:12] != _WEBP_HEADER[8:12]:
        return target
    new_target = target.with_suffix(".webp")
    r["filename"] = r["filename"].rsplit(".", 1)[0] + ".webp"
    r["relative_path"] = r["relative_path"].rsplit(".", 1)[0] + ".webp"
    r["ext"] = ".webp"
    return new_target


def download_records(records, dest, only_bad=False):
    dest = Path(dest)
    normalize_local_formats(records, dest)
    downloaded = skipped = 0
    for idx, r in enumerate(records, 1):
        target = dest / r["relative_path"]
        bad = (not target.exists()) or target.stat().st_size == 0
        if only_bad and not bad:
            r["bytes"] = target.stat().st_size
            r["status"] = "exists"
            skipped += 1
            continue
        if target.exists() and target.stat().st_size > 0 and not only_bad:
            r["bytes"] = target.stat().st_size
            r["status"] = "exists"
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # 跳过空 URL（API 获取失败的占位记录，待后续 repair 重试）
        if not r.get("url"):
            r["status"] = "pending"
            skipped += 1
            continue
        # 米游社视频 CDN 需要 Referer 头
        extra = None
        if "vod-sign.miyoushe.com" in r.get("url", ""):
            extra = {"Referer": "https://www.miyoushe.com/"}
        body, headers = request_bytes(r["url"], timeout=120, extra_headers=extra)
        # 修正伪装成 .gif 的 WebP，避免 Windows 照片应用无法打开
        target = _fix_webp_gif(body, target, r)
        target.write_bytes(body)
        r["bytes"] = len(body)
        r["content_length"] = headers.get("Content-Length") or ""
        r["etag"] = headers.get("ETag") or ""
        r["last_modified"] = headers.get("Last-Modified") or ""
        r["sha256"] = hashlib.sha256(body).hexdigest()
        r["status"] = "ok"
        downloaded += 1
        if idx % 50 == 0 or idx == len(records):
            print(f"processed {idx}/{len(records)}")
        time.sleep(0.03)
    return downloaded, skipped


def check_local_records(records, dest):
    dest = Path(dest)
    report = []
    for r in records:
        target = dest / r["relative_path"]
        if not target.exists():
            status = "missing"
            size = ""
        elif target.stat().st_size == 0:
            status = "zero"
            size = 0
        else:
            status = "ok"
            size = target.stat().st_size
            cl = r.get("content_length", "")
            if cl:
                try:
                    expected = int(cl)
                    if expected and size != expected:
                        status = "size_mismatch"
                except (ValueError, TypeError):
                    pass
        report.append({**r, "local_path": str(target), "local_size": size, "check_status": status})
    return report


def write_report(rows, dest):
    fields = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]
    path = _report_path(dest)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
