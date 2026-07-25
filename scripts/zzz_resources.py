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

BLACKBOARD = "https://act-api-takumi-static.mihoyo.com/common/blackboard/zzz_wiki"
ENTRY_API = "https://act-api-takumi-static.mihoyo.com/hoyowiki/zzz/wapi/entry_page"
BBS_API = "https://bbs-api.miyoushe.com/post/wapi/getPostFull"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Rpc-Wiki_app": "zzz",
}
QUALITY_ORDER = {"2K": 4, "1080P": 3, "720P": 2, "480P": 1}


def _manifest_dir(dest):
    d = Path(dest) / ".manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(type_name, dest):
    return _manifest_dir(dest) / f"{type_name}_manifest.csv"


def _report_path(dest):
    return _manifest_dir(dest) / "last_check_report.csv"
WALLPAPER_ROOT = "壁纸合集"
CALENDAR_COLLECTION = "月历壁纸合集"
AGENT_ROOT = "代理档案"

WALLPAPER_COLLECTIONS = [
    ("EP短片壁纸合集", 1864),
    ("EP短片壁纸合集", 1599),
    ("New Eridan 时尚", 1990),
    ("丽都有丽事", 1989),
    ("六分街街头异闻", 1988),
    ("邦布们的说明书", 1987),
    ("活动壁纸合集", 1965),
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
FLATTEN_WALLPAPER_CATEGORIES = {
    "动态壁纸合集",
    "过塑手账壁纸合集",
    "丽都放大镜壁纸合集",
    "六分街街头异闻",
}
NAME_GROUPED_CATEGORIES = {"丽都有丽事", "邦布们的说明书"}


def extract_series_base(tab_name):
    """从 tab_name 末尾剥离数字，返回 (系列名, 是否有数字后缀)。"""
    name = tab_name.strip()
    m = re.match(r"^(.+?)(\d+)$", name)
    if m:
        return m.group(1).strip(), True
    return name, False


def request_bytes(url, timeout=60, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(), response.headers


def load_json(url, timeout=60, extra_headers=None):
    body, _ = request_bytes(url, timeout, extra_headers=extra_headers)
    return json.loads(body.decode("utf-8"))


def fetch_bbs_post(post_id, retries=3):
    """获取米游社文章完整数据，包含 vod_list 视频列表。

    需要完整的浏览器安全头（Sec-Fetch-*, Sec-Ch-Ua-*），否则返回 403。"""
    url = f"{BBS_API}?post_id={post_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": f"https://www.miyoushe.com/zzz/article/{post_id}",
        "Origin": "https://www.miyoushe.com",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    last_error = None
    for attempt in range(retries):
        if attempt > 0:
            wait = (attempt + 1) * 2  # 递增等待：2s, 4s, 6s
            print(f"    重试 {attempt + 1}/{retries}（等待 {wait}s）...")
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read()
            root = json.loads(body.decode("utf-8"))
            if root.get("retcode") != 0:
                retcode = root.get("retcode")
                if retcode == 1034:
                    raise RuntimeError(f"bbs post {post_id} retcode=1034: 米游社 API 风控拦截，无法获取视频链接（不影响已有文件）")
                last_error = RuntimeError(f"bbs post {post_id} retcode={retcode}: {root.get('message')}")
                continue
            return root["data"]["post"]
        except urllib.error.HTTPError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue
    raise last_error or RuntimeError(f"bbs post {post_id} failed after {retries} retries")


def best_video_url(vod_list):
    """从 vod_list 中选出最高清晰度的视频 URL，返回 (url, definition)。"""
    best_url = None
    best_def = ""
    best_rank = -1
    for vod in vod_list if isinstance(vod_list, list) else []:
        for res in vod.get("resolutions", []):
            rank = QUALITY_ORDER.get(res.get("definition", ""), 0)
            if rank > best_rank:
                best_rank = rank
                best_url = res.get("url", "")
                best_def = res.get("definition", "")
    return best_url, best_def


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
    url = r.get("url", "")
    # 去掉视频 URL 的时效性签名参数，避免每次 check-remote 误判为新增/移除
    url_clean = re.sub(r"\?auth_key=.*", "", url)
    return "|".join(
        [
            r.get("resource_type", ""),
            str(r.get("entry_id", "")),
            str(r.get("module_id", "")),
            r.get("source_name", ""),
            url_clean,
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
                        "resource_type": "wallpapers",
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
        is_name_grouped = category in NAME_GROUPED_CATEGORIES
        for module in page.get("modules", []):
            module_id = str(module.get("id") or "")
            group = group_names.get(module_id, "") or page.get("name") or category
            use_group_dir = category not in FLATTEN_WALLPAPER_CATEGORIES if not is_name_grouped else False
            base_relative_dir = path_join(WALLPAPER_ROOT, category, sanitize(group, f"{entry_id}-{module_id}") if use_group_dir else "")
            img_seq = 0
            vid_seq = 0
            for comp in module.get("components", []):
                for item in image_items(comp):
                    img_seq += 1
                    name = str(item.get("tab_name") or "").strip()
                    base = sanitize(name, "壁纸")
                    if is_name_grouped:
                        series_name, has_suffix = extract_series_base(name)
                        if has_suffix:
                            item_group = sanitize(series_name, f"{entry_id}-{module_id}")
                            item_dir = path_join(WALLPAPER_ROOT, category, item_group)
                        else:
                            item_group = ""
                            item_dir = path_join(WALLPAPER_ROOT, category)
                    else:
                        item_group = group if use_group_dir else ""
                        item_dir = base_relative_dir
                    records.append(
                        {
                            "resource_type": "wallpapers",
                            "category": category,
                            "group": item_group,
                            "entry_id": str(entry_id),
                            "module_id": module_id,
                            "source_name": name,
                            "url": item["image"],
                            "ext": ext_from_url(item["image"], ".jpg"),
                            "base": base,
                            "relative_dir": item_dir,
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
                            "relative_dir": base_relative_dir,
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


# 缓存：避免 check-local --type all 时重复遍历全部代理人页面
_agent_entries_cache = None
_canonical_names_cache = None


def agent_entries():
    global _agent_entries_cache
    if _agent_entries_cache is not None:
        return _agent_entries_cache
    url = f"{BLACKBOARD}/v1/home/content/list?app_sn=zzz_wiki&channel_id=43&page_num=1&page_size=100"
    data = load_json(url, timeout=30)["data"]
    channel = find_channel({"children": data["list"]}, 43)
    if not channel:
        raise RuntimeError("agent channel 43 not found")
    _agent_entries_cache = [
        {
            "entry_id": int(item["content_id"]),
            "title": item.get("title") or "",
            "role": item.get("alias_name") or item.get("title") or str(item["content_id"]),
        }
        for item in channel.get("list", [])
    ]
    return _agent_entries_cache


def page_agent_name(page):
    """从 module 2 (基础信息) 的 data JSON 中提取权威特工全名。"""
    for mod in page.get("modules", []):
        if str(mod.get("id") or "") == "2":
            for comp in mod.get("components", []):
                try:
                    d = json.loads(comp.get("data") or "{}")
                    name = (d.get("name") or "").strip()
                    if name:
                        return name
                except json.JSONDecodeError:
                    pass
    return None


def canonical_agent_names():
    """遍历所有特工页面，返回权威名称映射 {entry_id: page_name}。（结果缓存）"""
    global _canonical_names_cache
    if _canonical_names_cache is not None:
        return _canonical_names_cache
    names = {}
    for entry in agent_entries():
        page = fetch_entry(entry["entry_id"])
        name = page_agent_name(page)
        if name:
            names[entry["entry_id"]] = name
    _canonical_names_cache = names
    return names


def build_cinema():
    """采集特工页面上的意象影画、角色展示、媒体物料三个模块。"""
    MODULE_CATEGORY = {
        "279": "意象影画",
        "12": "角色展示",
        "949": "媒体物料",
    }
    records = []
    for entry in agent_entries():
        page = fetch_entry(entry["entry_id"])
        role = page_agent_name(page) or entry["role"] or page.get("name") or str(entry["entry_id"])
        role_dir = sanitize(role, str(entry["entry_id"]))
        seen_279_cinema = False
        for module in page.get("modules", []):
            module_id = str(module.get("id") or "")
            category = MODULE_CATEGORY.get(module_id)
            if not category:
                continue
            for comp in module.get("components", []):
                items = image_items(comp)
                if not items:
                    continue
                if module_id == "279":
                    if seen_279_cinema:
                        continue
                    cinema_items = [
                        item for item in items
                        if re.match(r"影画展示\d", str(item.get("tab_name") or ""))
                    ]
                    if cinema_items:
                        seen_279_cinema = True
                        for item in cinema_items:
                            name = str(item.get("tab_name") or "").strip()
                            records.append({
                                "resource_type": "cinema",
                                "category": category,
                                "group": role,
                                "entry_id": str(entry["entry_id"]),
                                "module_id": module_id,
                                "source_name": name,
                                "url": item["image"],
                                "ext": ext_from_url(item["image"], ".png"),
                                "base": name,
                                "relative_dir": path_join(AGENT_ROOT, role_dir, category),
                            })
                else:
                    for item in items:
                        name = str(item.get("tab_name") or "").strip()
                        if not name:
                            continue
                        records.append({
                            "resource_type": "cinema",
                            "category": category,
                            "group": role,
                            "entry_id": str(entry["entry_id"]),
                            "module_id": module_id,
                            "source_name": name,
                            "url": item["image"],
                            "ext": ext_from_url(item["image"], ".png"),
                            "base": name,
                            "relative_dir": path_join(AGENT_ROOT, role_dir, category),
                        })
    return add_targets(records)


def build_goodwill():
    """采集好感壁纸视频，以 channel 43 的特工名为标准做交叉匹配。"""
    url = f"{BLACKBOARD}/v1/home/content/list?app_sn=zzz_wiki&channel_id=99&page_num=1&page_size=100"
    data = load_json(url, timeout=30)["data"]
    channel = find_channel({"children": data["list"]}, 99)
    if not channel:
        raise RuntimeError("goodwill channel 99 not found")

    # 以 page 全名为权威标准名，channel 43 alias 为兜底
    def _norm(s):
        return re.sub(r"[·「」&！\s]", "", s)

    page_names = canonical_agent_names()
    alias_map = {entry["entry_id"]: entry["role"] for entry in agent_entries()}
    canonical_names = set(page_names.values())
    alias_to_page = {}  # alias → page_name 兜底映射
    for eid, alias in alias_map.items():
        if eid in page_names and alias != page_names[eid]:
            alias_to_page[alias] = page_names[eid]
        if eid not in page_names:
            canonical_names.add(alias)

    norm_to_canon = {}
    for name in canonical_names:
        norm_to_canon[_norm(name)] = name
    # alias 兜底：让 resolve 能通过别名找到 page 全名
    for alias, page_name in alias_to_page.items():
        key = _norm(alias)
        if key not in norm_to_canon:
            norm_to_canon[key] = page_name

    def resolve_agent(title):
        raw = title.replace("好感壁纸", "").replace("动态壁纸", "").strip()
        if not raw:
            return raw
        raw_norm = _norm(raw)
        if raw_norm in norm_to_canon:
            return norm_to_canon[raw_norm]
        # 优先前缀匹配（避免"安比"错误匹配到"零号·安比"）
        for canon_name in canonical_names:
            canon_norm = _norm(canon_name)
            if canon_norm.startswith(raw_norm) or raw_norm.startswith(canon_norm):
                return canon_name
        # 子串匹配兜底
        for canon_name in canonical_names:
            canon_norm = _norm(canon_name)
            if canon_norm in raw_norm or raw_norm in canon_norm:
                return canon_name
        return raw

    records = []
    for item in channel.get("list", []):
        entry_id = int(item["content_id"])
        title = item.get("title") or ""
        agent = resolve_agent(title)
        if not agent:
            continue
        page = fetch_entry(entry_id)
        for module in page.get("modules", []):
            module_id = str(module.get("id") or "")
            for comp in module.get("components", []):
                for url in video_urls(comp):
                    records.append(
                        {
                            "resource_type": "goodwill",
                            "category": "好感壁纸",
                            "group": agent,
                            "entry_id": str(entry_id),
                            "module_id": module_id,
                            "source_name": title,
                            "url": url,
                            "ext": ext_from_url(url, ".mp4"),
                            "base": sanitize(f"{agent}好感壁纸", f"goodwill-{entry_id}"),
                            "relative_dir": path_join(AGENT_ROOT, sanitize(agent, str(entry_id)), "好感壁纸"),
                        }
                    )
    return add_targets(records)


def build_agent_videos():
    """采集频道73「角色视频」中的「不可售影像」和「代理人档案」视频。

    视频托管于米游社文章，需通过 bbs-api 获取 vod_list 后选取最高清晰度下载。
    代理人名称与 channel 43 的权威名称做交叉匹配，确保目录名一致。
    """
    # 获取频道 73 的条目列表
    url = f"{BLACKBOARD}/v1/home/content/list?app_sn=zzz_wiki&channel_id=13&page_num=1&page_size=100"
    data = load_json(url, timeout=30)["data"]
    ch13 = find_channel({"children": data["list"]}, 13)
    if not ch13:
        raise RuntimeError("channel 13 not found")
    ch73 = find_channel({"children": ch13.get("children", [])}, 73)
    if not ch73:
        raise RuntimeError("channel 73 not found")

    # 筛选目标分类
    TARGET_PREFIXES = ["不可售影像", "代理人档案"]
    items = []
    for item in ch73.get("list", []):
        title = (item.get("title") or "").strip()
        for prefix in TARGET_PREFIXES:
            if title.startswith(prefix):
                items.append((prefix, item))
                break

    if not items:
        print("未找到不可售影像或代理人档案条目")
        return []

    # 构建权威名称映射（复用 build_goodwill 的归一化逻辑）
    def _norm(s):
        return re.sub(r"[·「」&！\s•]", "", s)

    page_names = canonical_agent_names()
    alias_map = {entry["entry_id"]: entry["role"] for entry in agent_entries()}
    canonical_names = set(page_names.values())
    for eid, alias in alias_map.items():
        if eid not in page_names:
            canonical_names.add(alias)

    norm_to_canon = {}
    for name in canonical_names:
        norm_to_canon[_norm(name)] = name

    def resolve_agent(raw_name):
        """将标题中解析出的代理人名匹配到权威名称。"""
        raw_norm = _norm(raw_name)
        if raw_norm in norm_to_canon:
            return norm_to_canon[raw_norm]
        # 优先前缀匹配（避免"安比"错误匹配到"零号·安比"）
        for canon_name in canonical_names:
            canon_norm = _norm(canon_name)
            if canon_norm.startswith(raw_norm) or raw_norm.startswith(canon_norm):
                return canon_name
        # 子串匹配兜底
        for canon_name in canonical_names:
            canon_norm = _norm(canon_name)
            if canon_norm in raw_norm or raw_norm in canon_norm:
                return canon_name
        return raw_name

    records = []
    for prefix, item in items:
        entry_id = int(item["content_id"])
        title = item.get("title") or ""

        # 从标题解析代理人名：去掉前缀和分隔符
        raw_name = title[len(prefix):].strip()
        # 去掉前缀分隔符 丨 | 等
        raw_name = re.sub(r"^[丨|｜\s]+", "", raw_name).strip()
        # 对于"叶瞬光 • 暖霞拾光"这种情况，取 • 前面的主名称
        raw_name = re.split(r"[•·]", raw_name)[0].strip()
        # 去掉书名号式括号
        raw_name = raw_name.replace("「", "").replace("」", "").strip()

        if not raw_name:
            continue

        agent = resolve_agent(raw_name)
        agent_dir = sanitize(agent, str(entry_id))
        category = prefix  # "不可售影像" 或 "代理人档案"

        print(f"  [{prefix}] {raw_name} → {agent} (entry={entry_id})")

        # 获取条目页 → 提取 post_id
        try:
            page = fetch_entry(entry_id)
        except Exception as exc:
            print(f"    跳过：entry_page 获取失败 ({exc})")
            continue

        ext = page.get("ext") or {}
        post_ext = ext.get("post_ext") or {}
        post_id = post_ext.get("post_id") or ""
        if not post_id:
            print(f"    跳过：无 post_id（page_type={page.get('page_type')}）")
            continue

        # 获取米游社文章 → 提取视频
        video_url = ""
        definition = ""
        try:
            post = fetch_bbs_post(post_id)
            vod_list = post.get("vod_list") or []
            video_url, definition = best_video_url(vod_list)
            if video_url:
                print(f"    → {definition} {video_url[:80]}...")
            else:
                print(f"    警告：vod_list 中无视频")
        except Exception as exc:
            print(f"    警告：bbs post {post_id} 获取失败 ({exc})，记录已保留待后续修复")
        finally:
            # 请求间隔，避免触发速率限制
            time.sleep(2)

        records.append({
            "resource_type": "agent_videos",
            "category": category,
            "group": agent,
            "entry_id": str(entry_id),
            "module_id": "",
            "source_name": title,
            "url": video_url,
            "ext": ".mp4",
            "base": category,
            "relative_dir": path_join(AGENT_ROOT, agent_dir),
            "definition": definition,
        })

    return add_targets(records)


def expand_types(type_name):
    return ["wallpapers", "cinema", "goodwill", "agent_videos"] if type_name == "all" else [type_name]


def build_records(type_name):
    builders = {"wallpapers": build_wallpapers, "cinema": build_cinema, "goodwill": build_goodwill, "agent_videos": build_agent_videos}
    records = []
    for t in expand_types(type_name):
        if t == "wallpapers":
            records.extend(build_calendar())
        records.extend(builders[t]())
    return records


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
        "bytes",
        "content_length",
        "status",
    ]
    path = _manifest_path(type_name, dest)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
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


def save_by_type(records, dest):
    for t, rows in split_by_type(records).items():
        write_manifest(t, rows, dest)


_WEBP_HEADER = bytes("RIFF", "ascii") + b"\x00" * 8 + bytes("WEBP", "ascii")


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


def write_report(rows, dest):
    fields = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]
    path = _report_path(dest)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def cmd_list(args):
    dest = args.dest
    for t in ("wallpapers", "cinema", "goodwill"):
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
    old = []
    for t in expand_types(args.type):
        old.extend(read_manifest(t, args.dest))
    old_by_key = {r.get("key") or stable_key(r): r for r in old}
    cur_by_key = {r["key"]: r for r in current}
    rows = []
    for key, r in cur_by_key.items():
        rows.append({**r, "remote_status": "new" if key not in old_by_key else "unchanged"})
    for key, r in old_by_key.items():
        if key not in cur_by_key:
            rows.append({**r, "remote_status": "removed_or_changed"})
    write_report(rows, args.dest)
    save_by_type(current, args.dest)
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


if __name__ == "__main__":
    main()
