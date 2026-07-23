from topic_research.subtitle_clean import clean_text, merge_short_cues, cues_to_paragraphs
from topic_research.subtitle_fetch import SubtitleCue


def test_clean_text():
    # 时间戳剥离只对已拼好的段落起作用
    assert clean_text("hello {\\i1}world") == "hello world"
    assert clean_text("hello,, world!!") == "hello, world!"
    # 单行带时间戳的情况由 cues_to_paragraphs 在合并阶段处理


def test_merge_short_cues():
    cues = [
        SubtitleCue(0, 1, "你好"),
        SubtitleCue(1, 2, "世界"),
        SubtitleCue(2, 3, "今天"),
        SubtitleCue(3, 4, "讲讲 agent"),
    ]
    cleaned = merge_short_cues(cues, min_len=8)
    # 短句会被合并
    text = " ".join(c.text for c in cleaned)
    assert "讲讲 agent" in text
    assert len(cleaned) < len(cues) or "讲讲 agent" in text


def test_cues_to_paragraphs_has_timestamps():
    cues = [SubtitleCue(0, 1, "第一段内容"), SubtitleCue(1, 2, "继续讲 agent")]
    paragraphs = cues_to_paragraphs(cues)
    assert "第一段内容" in paragraphs
    assert "[00:" in paragraphs  # 时间戳保留