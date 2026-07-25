"""官方接口地址、目录名称和资源分类常量。"""





BLACKBOARD = "https://act-api-takumi-static.mihoyo.com/common/blackboard/zzz_wiki"


ENTRY_API = "https://act-api-takumi-static.mihoyo.com/hoyowiki/zzz/wapi/entry_page"


BBS_API = "https://bbs-api.miyoushe.com/post/wapi/getPostFull"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Rpc-Wiki_app": "zzz",
}


QUALITY_ORDER = {"2K": 4, "1080P": 3, "720P": 2, "480P": 1}


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
