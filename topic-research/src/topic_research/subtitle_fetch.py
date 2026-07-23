"""B站字幕下载

策略：
1. 调用视频详情接口 cid
2. 通过 player/v2 接口获取字幕列表
3. 优先下载官方字幕；其次下载自动字幕（标记为 auto）
4. 下载 JSON 字幕并规整为统一结构

不依赖浏览器；无字幕/失败时返回空列表与字幕类型。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import requests

from .bili_session import build_session
from .search_bilibili import get_video_detail

logger = logging.getLogger(__name__)

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/v2"
SUBTITLE_PROXY = "https://aisubtitle.hdslb.com/"

SubtitleType = Literal["official", "auto", "none", "unknown"]


@dataclass
class SubtitleCue:
    from_s: float
    to_s: float
    content: str


@dataclass
class SubtitleResult:
    bvid: str
    subtitle_type: SubtitleType
    cues: list[SubtitleCue]
    raw_meta: dict
    error: str | None = None


def _get_session() -> requests.Session:
    return build_session()


def fetch_subtitle_meta(bvid: str, sess: requests.Session | None = None) -> dict:
    """获取字幕列表元数据"""
    sess = sess or _get_session()
    # 详情
    detail = get_video_detail(bvid, sess)
    cid = detail.get("cid")
    aid = detail.get("aid")
    if not cid:
        raise RuntimeError(f"无法获取 cid: {bvid}")
    # player/v2 接口
    r = sess.get(
        PLAYER_URL,
        params={"bvid": bvid, "cid": cid},
        timeout=20,
    )
    r.raise_for_status()
    player = r.json().get("data") or {}
    subtitles = player.get("subtitle", {}).get("subtitles", []) or []
    return {
        "cid": cid,
        "aid": aid,
        "title": detail.get("title", ""),
        "duration": detail.get("duration", 0),
        "subtitles": subtitles,
    }


def _classify(meta_item: dict) -> SubtitleType:
    """根据字幕条目判断类型"""
    if meta_item.get("ai_type") == 1 or meta_item.get("type") == 1:
        return "auto"
    # 默认 AI 自动字幕也会带 ai_type 字段；其他情况按官方字幕对待
    if meta_item.get("ai_type") == 0 or "ai_type" not in meta_item:
        return "official"
    return "unknown"


def _pick_subtitle(subtitles: list[dict]) -> tuple[SubtitleType, dict] | None:
    """优先官方中文，其次官方英文；其次自动中文，最后任意自动"""
    if not subtitles:
        return None

    def lang_key(item: dict) -> int:
        lan = item.get("lan", "")
        if lan.startswith("zh"):
            return 0
        if lan.startswith("en"):
            return 1
        return 2

    officials = [s for s in subtitles if _classify(s) == "official"]
    autos = [s for s in subtitles if _classify(s) == "auto"]

    for bucket, kind in ((officials, "official"), (autos, "auto")):
        if not bucket:
            continue
        bucket_sorted = sorted(bucket, key=lang_key)
        return kind, bucket_sorted[0]
    return None


def _download_subtitle_json(subtitle_url: str, sess: requests.Session) -> dict:
    """下载字幕 JSON（B站 CDN）"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    elif not subtitle_url.startswith("http"):
        subtitle_url = SUBTITLE_PROXY + subtitle_url
    r = sess.get(subtitle_url, timeout=20)
    r.raise_for_status()
    return r.json()


def _parse_subtitle_json(payload: dict) -> list[SubtitleCue]:
    body = payload.get("body") or []
    cues: list[SubtitleCue] = []
    for item in body:
        try:
            cues.append(
                SubtitleCue(
                    from_s=float(item.get("from", 0)),
                    to_s=float(item.get("to", 0)),
                    content=str(item.get("content", "")).strip(),
                )
            )
        except Exception:
            continue
    return cues


def fetch_subtitle(bvid: str, sess: requests.Session | None = None) -> SubtitleResult:
    sess = sess or _get_session()
    try:
        meta = fetch_subtitle_meta(bvid, sess)
    except Exception as e:
        logger.warning("获取字幕元数据失败 %s: %s", bvid, e)
        return SubtitleResult(bvid=bvid, subtitle_type="unknown", cues=[], raw_meta={}, error=str(e))

    subtitles = meta.get("subtitles", [])
    if not subtitles:
        return SubtitleResult(
            bvid=bvid,
            subtitle_type="none",
            cues=[],
            raw_meta={"title": meta.get("title")},
            error=None,
        )

    pick = _pick_subtitle(subtitles)
    if not pick:
        return SubtitleResult(bvid=bvid, subtitle_type="none", cues=[], raw_meta={"title": meta.get("title")})

    sub_type, item = pick
    subtitle_url = item.get("subtitle_url", "")
    if not subtitle_url:
        return SubtitleResult(bvid=bvid, subtitle_type=sub_type, cues=[], raw_meta=item, error="字幕 URL 为空")

    try:
        payload = _download_subtitle_json(subtitle_url, sess)
    except Exception as e:
        return SubtitleResult(bvid=bvid, subtitle_type=sub_type, cues=[], raw_meta=item, error=f"下载失败: {e}")

    cues = _parse_subtitle_json(payload)
    return SubtitleResult(
        bvid=bvid,
        subtitle_type=sub_type,
        cues=cues,
        raw_meta={"title": meta.get("title"), "lan": item.get("lan"), "lan_doc": item.get("lan_doc")},
    )


def save_subtitle_text(result: SubtitleResult, out_path: Path) -> Path:
    """把字幕落盘为纯文本（保留时间戳）"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for c in result.cues:
        ts = f"[{_fmt(c.from_s)} - {_fmt(c.to_s)}]"
        lines.append(f"{ts} {c.content}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _fmt(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"