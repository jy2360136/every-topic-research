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


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def search_videos(
    keyword: str,
    max_results: int = 60,
    page_size: int = 20,
    sort: str = "totalrank",  # totalrank / click / pubdate / dm / stow
    max_pages: int = 5,
    session: requests.Session | None = None,
) -> list[dict]:
    """返回搜索结果原始 video 字典列表"""
    sess = session or requests.Session()
    sess.headers.update(HEADERS)

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
            data = r.json()
        except Exception as e:
            logger.warning("搜索失败 page=%s: %s", page, e)
            time.sleep(1)
            continue

        items = (
            data.get("data", {})
            .get("result", {})
            .get("video", [])
        )
        if not items:
            break
        for it in items:
            out.append(it)
            if len(out) >= max_results:
                break
        time.sleep(0.4)
    return out


def get_video_detail(bvid: str, session: requests.Session | None = None) -> dict:
    sess = session or requests.Session()
    sess.headers.update(HEADERS)
    r = sess.get(VIEW_URL, params={"bvid": bvid}, timeout=20)
    r.raise_for_status()
    data = r.json().get("data") or {}
    return data


def _coerce_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _normalize(item: dict) -> VideoMeta | None:
    bvid = item.get("bvid")
    if not bvid:
        return None
    stat = item.get("stat") or {}
    return VideoMeta(
        bvid=bvid,
        aid=_coerce_int(item.get("aid")),
        title=(item.get("title") or "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
        owner_mid=_coerce_int(item.get("mid")),
        owner_name=(item.get("author") or "").strip(),
        duration=_coerce_int(item.get("duration"), 0),
        publish_time=_coerce_int(item.get("pubdate") or item.get("senddate")),
        description=(item.get("description") or "").strip(),
        view=_coerce_int(stat.get("view")),
        like=_coerce_int(stat.get("like")),
        coin=_coerce_int(stat.get("coin") or stat.get("coin_count")),
        favorite=_coerce_int(stat.get("favorite")),
        reply=_coerce_int(stat.get("reply")),
        share=_coerce_int(stat.get("share")),
        danmaku=_coerce_int(stat.get("danmaku") or item.get("danmaku")),
        tag=item.get("tag") or [],
        cover=(item.get("pic") or "").strip(),
        url=f"https://www.bilibili.com/video/{bvid}",
    )


def collect(keyword: str, max_results: int = 60, sort: str = "totalrank") -> list[VideoMeta]:
    """搜索并规范化"""
    items = search_videos(keyword, max_results=max_results, sort=sort)
    metas: list[VideoMeta] = []
    seen = set()
    for it in items:
        meta = _normalize(it)
        if not meta or meta.bvid in seen:
            continue
        seen.add(meta.bvid)
        # 时长过滤：太短的视频通常不是教程
        if 0 < meta.duration < 60:
            continue
        metas.append(meta)
    return metas