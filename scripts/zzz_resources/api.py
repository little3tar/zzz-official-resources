"""米哈游 Wiki、米游社文章和资源 CDN 的请求封装。"""


import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import BBS_API, ENTRY_API, HEADERS, QUALITY_ORDER


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
