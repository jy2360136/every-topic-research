"""B站视频搜索与元数据获取

数据源：
- 主：网页搜索 API（api.bilibili.com/x/web-interface/search/all/v2）
- 元数据补全：每个视频详情接口（api.bilibili.com/x/web-interface/view）

为避免依赖 bilibili-api-python 的运行时兼容性，这里直接调用公开 Web 接口。
"""
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import requests

from .bili_session import build_session, HEADERS

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"


@dataclass
class VideoMeta:
    bvid: str
    aid: int
    title: str
    owner_mid: int
    owner_name: str
    duration: int  # 秒
    publish_time: int  # unix
    description: str
    view: int
    like: int
    coin: int
    favorite: int
    reply: int
    share: int
    danmaku: int
    tag: list[str] = field(default_factory=list)
    cover: str = ""
    url: str = ""
    # 字幕相关（在 subtitle_fetch 阶段填充）
    subtitle_type: str = "unknown"  # official / auto / none / unknown

    def to_dict(self) -> dict:
        return asdict(self)


def search_videos(
    keyword: str,
    max_results: int = 60,
    page_size: int = 50,  # B 站搜索单页最大 50
    sort: str = "totalrank",  # totalrank / click / pubdate / dm / stow
    max_pages: int = 5,
    session: requests.Session | None = None,
) -> list[dict]:
    """返回搜索结果原始 video 字典列表

    B 站 all/v2 接口当前结构：data.result 是 list，每项形如
    {"result_type": "video", "data": [video_dict, ...]}。
    旧版的 nested {"result": {"video": [...]}} 结构已废弃。
    """
    sess = build_session(session)

    out: list[dict] = []
    for page in range(1, max_pages + 1):
        if len(out) >= max_results:
            break
        params = {
            "keyword": keyword,
            "search_type": "video",
            "page": page,
            "page_size": page_size,
            "order": sort,
            "duration": 0,
            "category_id": "",
        }
        try:
            r = sess.get(SEARCH_URL, params=params, timeout=20)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("搜索失败 page=%s: %s", page, e)
            time.sleep(1)
            continue

        sections = payload.get("data", {}).get("result", [])
        if not isinstance(sections, list) or not sections:
            break

        # 找到 result_type == 'video' 的段；data 是视频对象列表
        items: list[dict] = []
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            if sec.get("result_type") == "video":
                inner = sec.get("data")
                if isinstance(inner, list):
                    items.extend(inner)
        if not items:
            break
        for it in items:
            out.append(it)
            if len(out) >= max_results:
                break
        time.sleep(0.4)
    return out


def get_video_detail(bvid: str, session: requests.Session | None = None) -> dict:
    sess = build_session(session)
    r = sess.get(VIEW_URL, params={"bvid": bvid}, timeout=20)
    r.raise_for_status()
    data = r.json().get("data") or {}
    return data


def _coerce_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_duration(v) -> int:
    """把 B 站搜索结果里的 duration 字段解析成秒数。

    B 站 all/v2 接口当前返回的字段是形如 "1353:6" 的字符串（mm:ss 或 h:mm:ss）。
    也有少数情况返回纯数字（秒）。两种都兼容。
    """
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 2:  # mm:ss
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:  # h:mm:ss
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


def _normalize(item: dict) -> VideoMeta | None:
    bvid = item.get("bvid")
    if not bvid:
        return None
    # 新的 all/v2 响应：video 字段是扁平的（play / like / favorites / review / danmaku），
    # 旧版嵌套的 stat 字段已废弃。
    stat = item.get("stat") or {}
    return VideoMeta(
        bvid=bvid,
        aid=_coerce_int(item.get("aid")),
        title=(item.get("title") or "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
        owner_mid=_coerce_int(item.get("mid")),
        owner_name=(item.get("author") or "").strip(),
        duration=_parse_duration(item.get("duration")),
        publish_time=_coerce_int(item.get("pubdate") or item.get("senddate")),
        description=(item.get("description") or "").strip(),
        view=_coerce_int(stat.get("view") or item.get("play")),
        like=_coerce_int(stat.get("like") or item.get("like")),
        coin=_coerce_int(stat.get("coin") or stat.get("coin_count") or item.get("coin")),
        favorite=_coerce_int(stat.get("favorite") or item.get("favorites")),
        reply=_coerce_int(stat.get("reply") or item.get("review")),
        share=_coerce_int(stat.get("share") or item.get("share")),
        danmaku=_coerce_int(stat.get("danmaku") or item.get("danmaku")),
        tag=item.get("tag") or [],
        cover=(item.get("pic") or "").strip(),
        url=f"https://www.bilibili.com/video/{bvid}",
    )


def collect(
    keyword: str,
    max_results: int = 60,
    sort: str = "totalrank",
    min_duration: int = 300,   # 5 分钟
    max_duration: int = 2400,  # 40 分钟
    combine_sorts: bool = True,
) -> list[VideoMeta]:
    """搜索并规范化

    时长过滤：默认 5–40 分钟（300–2400 秒）。
    - 太短（< 5 min）通常是切片/混剪，没有字幕价值
    - 太长（> 40 min）通常是"几百集大教程"单集，容易没字幕

    combine_sorts=True 时会同时跑 totalrank / click / pubdate 三种排序并去重，
    让用户有更多候选（单排序 5–40 min 区间通常只有 15–20 个）。
    """
    sort_list = ["totalrank", "click", "pubdate"] if combine_sorts else [sort]
    items: list[dict] = []
    seen_raw: set[str] = set()
    for s in sort_list:
        # 多排序合并时，按排序数放大每路拉取量；最终结果仍以 max_results 截断
        per_sort_cap = max_results * (3 if combine_sorts else 1)
        for it in search_videos(keyword, max_results=per_sort_cap, sort=s):
            bvid = it.get("bvid") if isinstance(it, dict) else None
            if not bvid or bvid in seen_raw:
                continue
            seen_raw.add(bvid)
            items.append(it)

    metas: list[VideoMeta] = []
    seen = set()
    for it in items:
        meta = _normalize(it)
        if not meta or meta.bvid in seen:
            continue
        seen.add(meta.bvid)
        # 时长过滤
        if meta.duration and (meta.duration < min_duration or meta.duration > max_duration):
            continue
        metas.append(meta)
    return metas