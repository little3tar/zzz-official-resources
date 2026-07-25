"""资源命名、身份键、版本指纹和远端差异比较。"""


import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path


def extract_series_base(tab_name):
    """从 tab_name 末尾剥离数字，返回 (系列名, 是否有数字后缀)。"""
    name = tab_name.strip()
    m = re.match(r"^(.+?)(\d+)$", name)
    if m:
        return m.group(1).strip(), True
    return name, False


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
        r["fingerprint"] = revision_fingerprint(r)
    return records


def normalized_url(value):
    """移除会定期变化的鉴权参数，保留真正指向资源的 URL。"""
    if not value:
        return ""
    parts = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    stable_query = [(key, val) for key, val in query if key.lower() not in {"auth_key", "auth_k"}]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(stable_query), parts.fragment)
    )


def stable_key(r):
    """返回逻辑资源身份；URL 属于版本信息，不能参与身份判断。"""
    parts = [
        r.get("resource_type", ""),
        str(r.get("entry_id", "")),
        str(r.get("module_id", "")),
        r.get("category", ""),
        r.get("group", ""),
        r.get("source_name", ""),
        r.get("filename", ""),
    ]
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def revision_fingerprint(r):
    """返回可用远端元数据的指纹；空字段不应单独触发内容变化。"""
    parts = {
        "url": normalized_url(r.get("url", "")),
        "definition": r.get("definition", ""),
        "content_length": str(r.get("content_length", "")),
        "etag": r.get("etag", ""),
        "last_modified": r.get("last_modified", ""),
        "sha256": r.get("sha256", ""),
    }
    return json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def classify_remote_record(old, current):
    """比较同一逻辑资源，区分内容变化、链接恢复和临时抓取失败。"""
    old_path = old.get("relative_path", "")
    current_path = current.get("relative_path", "")
    if old_path and current_path and old_path != current_path:
        return "renamed"

    old_url = normalized_url(old.get("url", ""))
    current_url = normalized_url(current.get("url", ""))
    if old_url and not current_url:
        return "unknown"
    if not old_url and current_url:
        return "resolved"

    comparable_fields = ("definition", "content_length", "etag", "last_modified", "sha256")
    if old_url and current_url and old_url != current_url:
        return "changed"
    for field in comparable_fields:
        old_value = str(old.get(field, "") or "")
        current_value = str(current.get(field, "") or "")
        if old_value and current_value and old_value != current_value:
            return "changed"

    if not current_url and current.get("status") in {
        "entry_fetch_failed",
        "missing_post_id",
        "bbs_fetch_failed",
        "no_video",
    }:
        return "unknown"
    return "unchanged"


def merge_manifest_record(old, current, remote_status):
    """接口临时失败时保留旧的可用远端元数据，避免破坏下一次比较基线。"""
    merged = dict(current)
    if remote_status == "unknown":
        for field in ("url", "definition", "content_length", "etag", "last_modified"):
            if not merged.get(field) and old.get(field):
                merged[field] = old[field]
        merged["status"] = "stale_remote_metadata"
    if remote_status in {"unchanged", "renamed", "resolved", "unknown"}:
        for field in ("bytes", "sha256"):
            if not merged.get(field) and old.get(field):
                merged[field] = old[field]
    merged["key"] = stable_key(merged)
    merged["fingerprint"] = revision_fingerprint(merged)
    return merged


def compare_remote_records(old_records, current_records):
    """返回检查报告记录和适合写回清单的记录。"""
    old_by_key = {stable_key(r): r for r in old_records}
    current_by_key = {stable_key(r): r for r in current_records}
    report = []
    manifest = []

    for key, current in current_by_key.items():
        old = old_by_key.get(key)
        if old is None:
            remote_status = "new"
            saved = dict(current)
            saved["key"] = key
            saved["fingerprint"] = revision_fingerprint(saved)
        else:
            remote_status = classify_remote_record(old, current)
            saved = merge_manifest_record(old, current, remote_status)
        report.append({**current, "key": key, "fingerprint": revision_fingerprint(current), "remote_status": remote_status})
        manifest.append(saved)

    for key, old in old_by_key.items():
        if key not in current_by_key:
            report.append({**old, "key": key, "fingerprint": revision_fingerprint(old), "remote_status": "removed"})
    return report, manifest
