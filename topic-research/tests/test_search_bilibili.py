"""search_bilibili 单元测试

专注 B 站 all/v2 接口响应解析：
- duration 是 "mm:ss" / "h:mm:ss" 字符串，需要被解析成秒
- 扁平字段（play / favorites / review / danmaku）替代旧版 stat 嵌套
- result 是 list，video 段在 result_type == 'video' 中
"""
from topic_research.search_bilibili import (
    _parse_duration,
    _normalize,
    VideoMeta,
)


class TestParseDuration:
    def test_mm_ss(self):
        assert _parse_duration("1353:6") == 1353 * 60 + 6

    def test_h_mm_ss(self):
        assert _parse_duration("1:23:45") == 3600 + 23 * 60 + 45

    def test_pure_seconds_int(self):
        assert _parse_duration(600) == 600

    def test_pure_seconds_str(self):
        assert _parse_duration("600") == 600

    def test_zero_and_none(self):
        assert _parse_duration("") == 0
        assert _parse_duration(None) == 0

    def test_garbage(self):
        assert _parse_duration("abc") == 0


class TestNormalizeFromV2:
    def test_flat_fields(self):
        """all/v2 接口返回的是扁平字段，不是 stat 嵌套"""
        item = {
            "bvid": "BV1xx",
            "aid": 12345,
            "title": "Agent<em class=\"keyword\">开发</em>",
            "author": "TestUP",
            "mid": 999,
            "duration": "12:34",  # mm:ss
            "pubdate": 1700000000,
            "description": "desc",
            "play": 1000,
            "like": 100,
            "favorites": 50,
            "review": 20,
            "danmaku": 30,
            "tag": "agent,AI",
            "pic": "https://x.jpg",
        }
        m = _normalize(item)
        assert m is not None
        assert m.bvid == "BV1xx"
        assert m.title == "Agent开发"  # <em> 标签被剥除
        assert m.duration == 12 * 60 + 34
        assert m.view == 1000
        assert m.like == 100
        assert m.favorite == 50
        assert m.reply == 20
        assert m.danmaku == 30
        assert m.owner_name == "TestUP"
        assert m.cover == "https://x.jpg"
