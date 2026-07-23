"""端到端冒烟测试（不调用网络/MiniMax）

覆盖：
- topic_init 创建目录
- candidates_html 渲染
- selection_io 解析
- state_store 持久化
"""
import json
import os
from pathlib import Path

import pytest

from topic_research import candidates_html, score_candidates, selection_io, state_store
from topic_research.search_bilibili import VideoMeta
from topic_research.topic_init import init_topic


def _meta(bvid="BV1xx", **kw):
    base = dict(
        bvid=bvid, aid=1, title=f"测试视频 {bvid}", owner_mid=0, owner_name="测试UP",
        duration=900, publish_time=0, description="agent 开发相关", view=200000,
        like=3000, coin=200, favorite=1500, reply=300, share=80, danmaku=1000,
        subtitle_type="official",
    )
    base.update(kw)
    return VideoMeta(**base)


def test_topic_init(tmp_path: Path):
    d = init_topic(tmp_path, title="agent 开发")
    assert (d / "topic.yaml").exists()
    assert (d / "candidates").exists()
    assert (d / "sources").exists()
    assert (d / "cards").exists()


def test_candidates_html_render(tmp_path: Path):
    metas = [_meta("BV1a"), _meta("BV1b", subtitle_type="auto"), _meta("BV1c", subtitle_type="none")]
    scored = score_candidates.score_all(metas, "agent 开发", now_ts=10**9)
    out = tmp_path / "candidates.html"
    candidates_html.render(scored, title="agent 开发", slug="agent-development", out_path=out)
    html = out.read_text(encoding="utf-8")
    assert "agent 开发" in html
    assert "官方字幕" in html
    assert "自动字幕" in html
    assert "无字幕" in html
    # selection 导出按钮
    assert "导出勾选 selection.json" in html


def test_selection_io(tmp_path: Path):
    p = tmp_path / "selection.json"
    payload = {
        "topic_slug": "agent-development",
        "selected": [
            {"bvid": "BV1a", "title": "T1", "subtitle_type": "official"},
            {"bvid": "BV1c", "title": "T3", "subtitle_type": "none"},
        ],
    }
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    items = selection_io.load_selection(p)
    # 无字幕视频被过滤
    assert len(items) == 1
    assert items[0]["bvid"] == "BV1a"


def test_state_store(tmp_path: Path):
    s = state_store.StateStore(tmp_path)
    s.upsert_video("BV1", title="t", subtitle_type="official")
    s.update_video("BV1", card_state="done")
    s.save()
    s2 = state_store.StateStore(tmp_path)
    assert s2.video("BV1")["card_state"] == "done"