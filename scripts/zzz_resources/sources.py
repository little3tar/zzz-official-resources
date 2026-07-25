"""壁纸、代理人资料、好感壁纸和代理人视频的官方数据解析。"""


import json
import re
import time

from .api import best_video_url, fetch_bbs_post, fetch_entry, load_json
from .config import (
    AGENT_ROOT,
    BLACKBOARD,
    CALENDAR_COLLECTION,
    FLATTEN_WALLPAPER_CATEGORIES,
    NAME_GROUPED_CATEGORIES,
    WALLPAPER_COLLECTIONS,
    WALLPAPER_ROOT,
)
from .records import (
    add_targets,
    ext_from_url,
    extract_series_base,
    image_items,
    module_group_names,
    path_join,
    sanitize,
    video_urls,
)


_agent_entries_cache = None


_canonical_names_cache = None


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
                        url = item["image"]
                        ext = ext_from_url(url, ".png")
                        records.append({
                            "resource_type": "cinema",
                            "category": category,
                            "group": role,
                            "entry_id": str(entry["entry_id"]),
                            "module_id": module_id,
                            "source_name": name,
                            "url": url,
                            "ext": ext,
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

        # 获取条目页 → 提取 post_id。失败时仍保留占位记录，不能误判为远端删除。
        video_url = ""
        definition = ""
        fetch_status = ""
        try:
            page = fetch_entry(entry_id)
        except Exception as exc:
            print(f"    跳过：entry_page 获取失败 ({exc})")
            page = None
            fetch_status = "entry_fetch_failed"

        if page is not None:
            ext = page.get("ext") or {}
            post_ext = ext.get("post_ext") or {}
            post_id = post_ext.get("post_id") or ""
            if not post_id:
                print(f"    警告：无 post_id（page_type={page.get('page_type')}）")
                fetch_status = "missing_post_id"
            else:
                # 获取米游社文章 → 提取视频
                try:
                    post = fetch_bbs_post(post_id)
                    vod_list = post.get("vod_list") or []
                    video_url, definition = best_video_url(vod_list)
                    if video_url:
                        print(f"    → {definition} {video_url[:80]}...")
                        fetch_status = "ok"
                    else:
                        print("    警告：vod_list 中无视频")
                        fetch_status = "no_video"
                except Exception as exc:
                    print(f"    警告：bbs post {post_id} 获取失败 ({exc})，记录已保留待后续修复")
                    fetch_status = "bbs_fetch_failed"
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
            "status": fetch_status,
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
