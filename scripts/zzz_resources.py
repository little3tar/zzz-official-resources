import argparse
import csv
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = SKILL_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

BLACKBOARD = "https://act-api-takumi-static.mihoyo.com/common/blackboard/zzz_wiki"
ENTRY_API = "https://act-api-takumi-static.mihoyo.com/hoyowiki/zzz/wapi/entry_page"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Rpc-Wiki_app": "zzz",
}

MANIFESTS = {
    "calendar": STATE_DIR / "calendar_manifest.csv",
    "wallpapers": STATE_DIR / "wallpapers_manifest.csv",
    "cinema": STATE_DIR / "cinema_manifest.csv",
}
REPORT = STATE_DIR / "last_check_report.csv"
WALLPAPER_ROOT = "壁纸合集"
CALENDAR_COLLECTION = "月历壁纸合集"
CINEMA_ROOT = "意象影画"

WALLPAPER_COLLECTIONS = [
    ("EP短片壁纸合集", 1864),
    ("EP短片壁纸合集", 1599),
    ("动态壁纸合集", 1127),
    ("EP短片壁纸合集", 1085),
    ("影像档案壁纸合集", 1084),
    ("过塑手账壁纸合集", 718),
    ("丽都放大镜壁纸合集", 717),
    ("阵营壁纸合集", 689),
    ("节日壁纸合集", 688),
    ("活动壁纸合集", 685),
    ("生日贺图壁纸合集", 775),
]
FLATTEN_WALLPAPER_CATEGORIES = {"动态壁纸合集", "过塑手账壁纸合集", "丽都放大镜壁纸合集"}


def request_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(), response.headers


def load_json(url, timeout=60):
    body, _ = request_bytes(url, timeout)
    return json.loads(body.decode("utf-8"))


def fetch_entry(entry_id):
    query = urllib.parse.urlencode({"app_sn": "zzz_wiki", "entry_page_id": entry_id, "lang": "zh-cn"})
    root = load_json(f"{ENTRY_API}?{query}", timeout=30)
    if root.get("retcode") != 0:
        raise RuntimeError(f"entry {entry_id} failed: {root.get('message')}")
    return root["data"]["page"]


def sanitize(value, fallback):
    value = str(value or "").strip()
    value = re.sub(r'[<>:"/\\|?*]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .-_")
    return (value or fallback)[:120]


def ext_from_url(url, fallback=".png"):
    return Path(urllib.parse.urlparse(url).path).suffix.lower() or fallback


def path_join(*parts):
    return str(Path(*[p for p in parts if p]))


def module_group_names(page):
    names = {}
    for tab in page.get("template_layout", {}).get("tab", []):
        for group in tab.get("module_group", []):
            group_name = (group.get("name") or "").strip()
            for module in group.get("module", []):
                module_id = str(module.get("id") or "")
                if module_id:
                    names[module_id] = group_name
    return names


def image_items(component):
    try:
        data = json.loads(component.get("data") or "{}")
    except json.JSONDecodeError:
        return []
    return [item for item in data.get("list", []) if isinstance(item, dict) and item.get("image")]


def video_urls(component):
    data = component.get("data") or ""
    matches = re.findall(r'(?:data-video-url|src)=\\?"([^"\\]+?\.mp4)\\?"', data)
    seen = []
    for url in matches:
        if url not in seen:
            seen.append(url)
    return seen


def add_targets(records):
    used = set()
    counts = Counter()
    for r in records:
        folder = Path(r["relative_dir"])
        base = sanitize(r["base"], "resource")
        ext = r["ext"]
        key = (str(folder).lower(), base.lower(), ext.lower())
        counts[key] += 1
        filename = f"{base}{ext}" if counts[key] == 1 else f"{base}-{counts[key]:02d}{ext}"
        rel = folder / filename
        bump = counts[key]
        while str(rel).lower() in used:
            bump += 1
            rel = folder / f"{base}-{bump:02d}{ext}"
        used.add(str(rel).lower())
        r["filename"] = rel.name
        r["relative_path"] = str(rel)
        r["key"] = stable_key(r)
    return records


def stable_key(r):
    return "|".join(
        [
            r.get("resource_type", ""),
            str(r.get("entry_id", "")),
            str(r.get("module_id", "")),
            r.get("source_name", ""),
            r.get("url", ""),
        ]
    )


def build_calendar():
    page = fetch_entry(684)
    group_names = module_group_names(page)
    records = []
    for module in page.get("modules", []):
        module_id = str(module.get("id") or "")
        group_name = group_names.get(module_id, "")
        year_match = re.search(r"(\d{4})", group_name)
        if not year_match or ("PC" not in group_name and "手机" not in group_name):
            continue
        year = int(year_match.group(1))
        suffix = "p" if "PC" in group_name else "m"
        calendar_group = sanitize(group_name, f"{year}{suffix}")
        for comp in module.get("components", []):
            items = image_items(comp)
            for item in items:
                source_name = str(item.get("tab_name", "")).strip()
                month_match = re.search(r"(\d{1,2})月", source_name)
                if not month_match:
                    continue
                month = int(month_match.group(1))
                url = item["image"]
                ext = ext_from_url(url, ".jpg")
                base = source_name or f"{year}{month:02d}{suffix}"
                records.append(
                    {
                        "resource_type": "calendar",
                        "category": CALENDAR_COLLECTION,
                        "group": calendar_group,
                        "entry_id": "684",
                        "module_id": "",
                        "source_name": source_name,
                        "url": url,
                        "ext": ext,
                        "base": base,
                        "relative_dir": path_join(WALLPAPER_ROOT, CALENDAR_COLLECTION, calendar_group),
                    }
                )
    return add_targets(records)


def build_wallpapers():
    records = []
    for category, entry_id in WALLPAPER_COLLECTIONS:
        page = fetch_entry(entry_id)
        group_names = module_group_names(page)
        for module in page.get("modules", []):
            module_id = str(module.get("id") or "")
            group = group_names.get(module_id, "") or page.get("name") or category
            use_group_dir = category not in FLATTEN_WALLPAPER_CATEGORIES
            relative_dir = path_join(WALLPAPER_ROOT, category, sanitize(group, f"{entry_id}-{module_id}") if use_group_dir else "")
            img_seq = 0
            vid_seq = 0
            for comp in module.get("components", []):
                for item in image_items(comp):
                    img_seq += 1
                    name = str(item.get("tab_name") or "").strip()
                    base = sanitize(name, "壁纸")
                    records.append(
                        {
                            "resource_type": "wallpapers",
                            "category": category,
                            "group": group if use_group_dir else "",
                            "entry_id": str(entry_id),
                            "module_id": module_id,
                            "source_name": name,
                            "url": item["image"],
                            "ext": ext_from_url(item["image"], ".jpg"),
                            "base": base,
                            "relative_dir": relative_dir,
                        }
                    )
                for url in video_urls(comp):
                    vid_seq += 1
                    base = sanitize(group, f"{entry_id}-{module_id}-{vid_seq:03d}")
                    records.append(
                        {
                            "resource_type": "wallpapers",
                            "category": category,
                            "group": group if use_group_dir else "",
                            "entry_id": str(entry_id),
                            "module_id": module_id,
                            "source_name": group,
                            "url": url,
                            "ext": ext_from_url(url, ".mp4"),
                            "base": base,
                            "relative_dir": relative_dir,
                        }
                    )
    return add_targets(records)


def find_channel(node, channel_id):
    if isinstance(node, dict):
        if node.get("id") == channel_id or node.get("channel_id") == channel_id:
            return node
        for key in ("children", "list"):
            for child in node.get(key, []) if isinstance(node.get(key), list) else []:
                found = find_channel(child, channel_id)
                if found:
                    return found
    return None


def agent_entries():
    url = f"{BLACKBOARD}/v1/home/content/list?app_sn=zzz_wiki&channel_id=43&page_num=1&page_size=100"
    data = load_json(url, timeout=30)["data"]
    channel = find_channel({"children": data["list"]}, 43)
    if not channel:
        raise RuntimeError("agent channel 43 not found")
    return [
        {
            "entry_id": int(item["content_id"]),
            "title": item.get("title") or "",
            "role": item.get("alias_name") or item.get("title") or str(item["content_id"]),
        }
        for item in channel.get("list", [])
    ]


def build_cinema():
    records = []
    for entry in agent_entries():
        page = fetch_entry(entry["entry_id"])
        role = entry["role"] or page.get("name") or str(entry["entry_id"])
        for module in page.get("modules", []):
            module_id = str(module.get("id") or "")
            for comp in module.get("components", []):
                cinema = [
                    item
                    for item in image_items(comp)
                    if re.fullmatch(r"影画展示[123]", str(item.get("tab_name") or ""))
                ]
                if len(cinema) == 3:
                    for item in cinema:
                        name = str(item.get("tab_name") or "").strip()
                        records.append(
                            {
                                "resource_type": "cinema",
                                "category": CINEMA_ROOT,
                                "group": role,
                                "entry_id": str(entry["entry_id"]),
                                "module_id": module_id,
                                "source_name": name,
                                "url": item["image"],
                                "ext": ext_from_url(item["image"], ".png"),
                                "base": name,
                                "relative_dir": path_join(CINEMA_ROOT, sanitize(role, str(entry["entry_id"]))),
                            }
                        )
                    break
    return add_targets(records)


def expand_types(type_name):
    return ["calendar", "wallpapers", "cinema"] if type_name == "all" else [type_name]


def build_records(type_name):
    builders = {"calendar": build_calendar, "wallpapers": build_wallpapers, "cinema": build_cinema}
    records = []
    for t in expand_types(type_name):
        records.extend(builders[t]())
    return records


def manifest_path(type_name):
    return MANIFESTS[type_name]


def write_manifest(type_name, records):
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
        "bytes",
        "content_length",
        "status",
    ]
    path = manifest_path(type_name)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({field: r.get(field, "") for field in fields})


def read_manifest(type_name):
    path = manifest_path(type_name)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_by_type(records):
    grouped = defaultdict(list)
    for r in records:
        grouped[r["resource_type"]].append(r)
    return grouped


def save_by_type(records):
    for t, rows in split_by_type(records).items():
        write_manifest(t, rows)


def download_records(records, dest, only_bad=False):
    dest = Path(dest)
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
        body, headers = request_bytes(r["url"], timeout=120)
        target.write_bytes(body)
        r["bytes"] = len(body)
        r["content_length"] = headers.get("Content-Length") or ""
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
        report.append({**r, "local_path": str(target), "local_size": size, "check_status": status})
    return report


def write_report(rows):
    fields = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]
    with REPORT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def cmd_list(_args):
    for t in ("calendar", "wallpapers", "cinema"):
        rows = read_manifest(t)
        print(f"{t}: manifest={manifest_path(t)} rows={len(rows)}")


def cmd_download(args):
    records = build_records(args.type)
    downloaded, skipped = download_records(records, args.dest, only_bad=False)
    save_by_type(records)
    print(f"records={len(records)} downloaded={downloaded} skipped={skipped}")


def cmd_repair(args):
    records = build_records(args.type)
    downloaded, skipped = download_records(records, args.dest, only_bad=True)
    save_by_type(records)
    print(f"records={len(records)} repaired={downloaded} ok={skipped}")


def cmd_check_local(args):
    records = build_records(args.type)
    save_by_type(records)
    report = check_local_records(records, args.dest)
    write_report(report)
    counts = Counter(row["check_status"] for row in report)
    print(f"records={len(report)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"report={REPORT}")


def cmd_check_remote(args):
    current = build_records(args.type)
    old = []
    for t in expand_types(args.type):
        old.extend(read_manifest(t))
    old_by_key = {r.get("key") or stable_key(r): r for r in old}
    cur_by_key = {r["key"]: r for r in current}
    rows = []
    for key, r in cur_by_key.items():
        rows.append({**r, "remote_status": "new" if key not in old_by_key else "unchanged"})
    for key, r in old_by_key.items():
        if key not in cur_by_key:
            rows.append({**r, "remote_status": "removed_or_changed"})
    write_report(rows)
    save_by_type(current)
    counts = Counter(row["remote_status"] for row in rows)
    print(f"records={len(rows)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"report={REPORT}")


def cmd_export(args):
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for t in expand_types(args.type):
        src = manifest_path(t)
        if src.exists():
            shutil.copy2(src, dest / src.name)
            copied += 1
    if REPORT.exists():
        shutil.copy2(REPORT, dest / REPORT.name)
        copied += 1
    print(f"exported={copied} dest={dest}")


def main():
    parser = argparse.ArgumentParser(description="Download and check official ZZZ Wiki resources.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-resources")
    for name in ("download", "repair", "check-local"):
        p = sub.add_parser(name)
        p.add_argument("--type", choices=["calendar", "wallpapers", "cinema", "all"], required=True)
        p.add_argument("--dest", required=True)
    p = sub.add_parser("check-remote")
    p.add_argument("--type", choices=["calendar", "wallpapers", "cinema", "all"], required=True)
    p = sub.add_parser("export-manifest")
    p.add_argument("--type", choices=["calendar", "wallpapers", "cinema", "all"], required=True)
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


if __name__ == "__main__":
    main()
