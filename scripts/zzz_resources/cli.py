"""命令行参数和各操作的编排入口。"""


import argparse
import shutil
from collections import Counter
from pathlib import Path

from .records import compare_remote_records
from .sources import build_records, expand_types
from .storage import (
    _manifest_path,
    _report_path,
    check_local_records,
    download_records,
    normalize_local_formats,
    read_manifest,
    save_by_type,
    write_report,
)


def cmd_list(args):
    dest = args.dest
    for t in expand_types("all"):
        rows = read_manifest(t, dest)
        print(f"{t}: manifest={_manifest_path(t, dest)} rows={len(rows)}")


def cmd_download(args):
    records = build_records(args.type)
    downloaded, skipped = download_records(records, args.dest, only_bad=False)
    save_by_type(records, args.dest)
    report = check_local_records(records, args.dest)
    write_report(report, args.dest)
    counts = Counter(row["check_status"] for row in report)
    print(f"records={len(records)} downloaded={downloaded} skipped={skipped} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def cmd_repair(args):
    records = build_records(args.type)
    downloaded, skipped = download_records(records, args.dest, only_bad=True)
    save_by_type(records, args.dest)
    report = check_local_records(records, args.dest)
    write_report(report, args.dest)
    counts = Counter(row["check_status"] for row in report)
    print(f"records={len(records)} repaired={downloaded} ok={skipped} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def cmd_check_local(args):
    records = []
    for t in expand_types(args.type):
        records.extend(read_manifest(t, args.dest))
    if not records:
        print("没有本地清单可检查，请先运行 download 或 check-remote")
        return
    report = check_local_records(records, args.dest)
    write_report(report, args.dest)
    counts = Counter(row["check_status"] for row in report)
    print(f"records={len(report)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"report={_report_path(args.dest)}")


def cmd_check_remote(args):
    current = build_records(args.type)
    normalize_local_formats(current, args.dest)
    old = []
    for t in expand_types(args.type):
        old.extend(read_manifest(t, args.dest))
    rows, manifest_records = compare_remote_records(old, current)
    write_report(rows, args.dest)
    save_by_type(manifest_records, args.dest)
    counts = Counter(row["remote_status"] for row in rows)
    print(f"records={len(rows)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"report={_report_path(args.dest)}")


def cmd_export(args):
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for t in expand_types(args.type):
        src = _manifest_path(t, args.manifest_src)
        if src.exists():
            shutil.copy2(src, dest / src.name)
            copied += 1
    report_src = _report_path(args.manifest_src)
    if report_src.exists():
        shutil.copy2(report_src, dest / report_src.name)
        copied += 1
    print(f"exported={copied} dest={dest}")


def main():
    parser = argparse.ArgumentParser(description="Download and check official ZZZ Wiki resources.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list-resources")
    p.add_argument("--dest", required=True)
    for name in ("download", "repair", "check-local"):
        p = sub.add_parser(name)
        p.add_argument("--type", choices=["wallpapers", "cinema", "goodwill", "agent_videos", "all"], required=True)
        p.add_argument("--dest", required=True)
    p = sub.add_parser("check-remote")
    p.add_argument("--type", choices=["wallpapers", "cinema", "goodwill", "agent_videos", "all"], required=True)
    p.add_argument("--dest", required=True)
    p = sub.add_parser("export-manifest")
    p.add_argument("--type", choices=["wallpapers", "cinema", "goodwill", "agent_videos", "all"], required=True)
    p.add_argument("--manifest-src", required=True)
    p.add_argument("--dest", required=True)
    args = parser.parse_args()
    {
        "list-resources": cmd_list,
        "download": cmd_download,
        "repair": cmd_repair,
        "check-local": cmd_check_local,
        "check-remote": cmd_check_remote,
        "export-manifest": cmd_export,
    }[args.command](args)
