from topic_research.score_candidates import (
    relevance_score,
    view_score,
    duration_score,
    publish_time_score,
)
from topic_research.search_bilibili import VideoMeta


def _meta(**kw):
    base = dict(
        bvid="BV1", aid=1, title="", owner_mid=0, owner_name="",
        duration=600, publish_time=0, description="", view=10000,
        like=100, coin=10, favorite=50, reply=20, share=5, danmaku=100,
    )
    base.update(kw)
    return VideoMeta(**base)


def test_relevance():
    m = _meta(title="Agent 开发入门", description="讲 agent")
    score = relevance_score(m, "agent 开发")
    assert score > 0.5


def test_view_score():
    assert view_score(_meta(view=0)) == 0
    assert view_score(_meta(view=10_000_000)) >= 0.95


def test_duration_score():
    assert duration_score(_meta(duration=30)) < 0.5
    assert duration_score(_meta(duration=1200)) >= 0.95


def test_publish_time_score_recent():
    import time
    now = int(time.time())
    m = _meta(publish_time=now - 86400 * 30)  # 30 天前
    assert publish_time_score(m, now) == 1.0


def test_publish_time_score_old():
    import time
    now = int(time.time())
    m = _meta(publish_time=now - 86400 * 365 * 4)  # 4 年前
    assert publish_time_score(m, now) == 0.0