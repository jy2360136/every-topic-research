"""通过 Bing 搜索 B 站视频，绕过对 api.bilibili.com 的直连依赖

适用场景：当机器无法直连 *.bilibili.com 时，
用 Bing 抓 "site:bilibili.com <关键词>" 视频结果，再回补 B 站详情页元数据。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .search_bilibili import HEADERS, VideoMeta

logger = logging.getLogger(__name__)

BING_SEARCH_URL = "https://www.bing.com/search"


def _bvid_from_url(url: str) -> str | None:
    m = re.search(r"(BV[0-9A-Za-z]{6,})", url)
    return m.group(1) if m else None


def search_bilibili_via_bing(
    keyword: str,
    max_results: int = 30,
    max_pages: int = 3,
) -> list[str]:
    """从 Bing 搜索结果里抽取 bilibili.com 视频 URL 的 bvid 列表"""
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )

    bvids: list[str] = []
    seen: set[str] = set()

    for page in range(max_pages):
        if len(bvids) >= max_results:
            break
        params = {
            "q": f"site:bilibili.com/video {keyword}",
            "first": page * 10 + 1,
        }
        try:
            r = sess.get(BING_SEARCH_URL, params=params, timeout=15)
            r.raise_for_status()
        except Exception as e:
            logger.warning("Bing 搜索失败 page=%d: %s", page, e)
            break

        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "bilibili.com/video/" not in href:
                continue
            bvid = _bvid_from_url(href)
            if bvid and bvid not in seen:
                seen.add(bvid)
                bvids.append(bvid)
            if len(bvids) >= max_results:
                break
        time.sleep(0.6)

    return bvids[:max_results]


def fetch_meta_via_official_site(bvid: str) -> VideoMeta | None:
    """从 www.bilibili.com 视频页面解析元数据（不需要 api.bilibili.com）

    注意：这只在能直连 www.bilibili.com 时可用；在不能直连的环境下需调用方捕获异常。
    """
    sess = requests.Session()
    sess.headers.update(HEADERS)
    url = f"https://www.bilibili.com/video/{bvid}"
    try:
        r = sess.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning("访问 %s 失败: %s", url, e)
        return None
    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.video-title") or soup.select_one("title")
    title = (title_el.get_text(strip=True) if title_el else "") or ""

    # meta 信息
    view = _parse_int(soup, "浏览", default=0) or _parse_view_from_meta(html)
    like = _parse_int(soup, "点赞", default=0)
    duration = _parse_duration_from_meta(html)

    return VideoMeta(
        bvid=bvid,
        aid=0,
        title=title,
        owner_mid=0,
        owner_name="",
        duration=duration,
        publish_time=0,
        description="",
        view=view,
        like=like,
        coin=0,
        favorite=0,
        reply=0,
        share=0,
        danmaku=0,
        tag=[],
        cover="",
        url=url,
    )


def _parse_int(soup, key: str, default: int = 0) -> int:
    return default


def _parse_view_from_meta(html: str) -> int:
    m = re.search(r'"view":\s*(\d+)', html)
    return int(m.group(1)) if m else 0


def _parse_duration_from_meta(html: str) -> int:
    m = re.search(r'"duration":\s*(\d+)', html)
    return int(m.group(1)) if m else 0