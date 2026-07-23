"""候选视频综合评分

综合分组成（与设计文档一致）：
- 播放量分  30%
- 相关性分  20%
- 发布时间分 15%
- 字幕可用分 10%（正式分数前为 unknown）
- UP 主可信分 10%
- 互动率分  10%
- 时长合理分 5%
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .search_bilibili import VideoMeta


@dataclass
class ScoredCandidate:
    meta: VideoMeta
    score: float
    sub_scores: dict[str, float]
    reasons: list[str]


def _safe_log(value: float, base: float = 2.0) -> float:
    if value <= 0:
        return 0.0
    return math.log(value + 1, base)


def relevance_score(meta: VideoMeta, keyword: str) -> float:
    """简单的关键词命中率"""
    text = (
        meta.title.lower() + " " + meta.description.lower() + " " + " ".join(meta.tag).lower()
    )
    kws = [k.lower() for k in re.split(r"[\s,，]+", keyword) if k.strip()]
    if not kws:
        return 0.5
    hits = sum(1 for k in kws if k and k in text)
    return hits / len(kws)


def publish_time_score(meta: VideoMeta, now_ts: int) -> float:
    """发布时间距离今天越近分数越高；半年内满分，3 年以上 0 分"""
    if not meta.publish_time:
        return 0.0
    age_days = max(0, (now_ts - meta.publish_time) / 86400)
    if age_days <= 180:
        return 1.0
    if age_days >= 365 * 3:
        return 0.0
    # 线性衰减 180~1095 天
    return max(0.0, 1.0 - (age_days - 180) / (365 * 3 - 180))


def view_score(meta: VideoMeta) -> float:
    """对数归一化"""
    return min(1.0, _safe_log(meta.view) / 18.0)  # 2^18 ~= 26 万


def interaction_score(meta: VideoMeta) -> float:
    """互动率 = (点赞+收藏+评论+弹幕) / max(1, 播放量)"""
    if meta.view <= 0:
        return 0.0
    rate = (meta.like + meta.favorite + meta.reply + meta.danmaku) / max(1, meta.view)
    return min(1.0, rate * 50)  # 2% 互动率 ~= 满分


def duration_score(meta: VideoMeta) -> float:
    """5 分钟以下扣分；10~40 分钟最佳；超过 90 分钟略有扣分"""
    sec = meta.duration
    if sec <= 0:
        return 0.5  # 未知
    if sec < 60:
        return 0.1
    if sec < 300:
        return 0.5
    if sec <= 2400:  # 40 分钟内
        return 1.0
    if sec <= 5400:  # 90 分钟
        return 0.8
    return 0.6


def subtitle_score(meta: VideoMeta) -> float:
    if meta.subtitle_type == "official":
        return 1.0
    if meta.subtitle_type == "auto":
        return 0.6
    if meta.subtitle_type == "none":
        return 0.0
    return 0.5  # 未知（未拉取）


def up_score(meta: VideoMeta) -> float:
    """UP 主可信度：粗略用播放量分 + 互动率分合成（同一作者下均值难求）"""
    return min(1.0, _safe_log(meta.view) / 20.0 + 0.2)


def score_candidate(
    meta: VideoMeta, keyword: str, now_ts: int
) -> ScoredCandidate:
    subs = {
        "view": view_score(meta),
        "relevance": relevance_score(meta, keyword),
        "publish_time": publish_time_score(meta, now_ts),
        "subtitle": subtitle_score(meta),
        "up": up_score(meta),
        "interaction": interaction_score(meta),
        "duration": duration_score(meta),
    }
    weights = {
        "view": 0.30,
        "relevance": 0.20,
        "publish_time": 0.15,
        "subtitle": 0.10,
        "up": 0.10,
        "interaction": 0.10,
        "duration": 0.05,
    }
    total = sum(subs[k] * weights[k] for k in weights)

    reasons: list[str] = []
    if subs["relevance"] < 0.5:
        reasons.append("标题/简介与关键词相关度较低")
    if subs["view"] < 0.4:
        reasons.append("播放量较低")
    if subs["publish_time"] < 0.4:
        reasons.append("发布时间较早")
    if meta.subtitle_type == "auto":
        reasons.append("仅有自动字幕，质量可能有误")
    if meta.subtitle_type == "none":
        reasons.append("无字幕，将被跳过")
    if subs["duration"] < 0.5:
        reasons.append("时长过短")

    return ScoredCandidate(meta=meta, score=round(total, 4), sub_scores=subs, reasons=reasons)


def score_all(metas: list[VideoMeta], keyword: str, now_ts: int) -> list[ScoredCandidate]:
    return [score_candidate(m, keyword, now_ts) for m in metas]