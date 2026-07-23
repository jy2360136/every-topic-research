from topic_research.chunker import chunk_paragraphs, estimate_tokens


def test_chunk_short_text():
    text = "段落A\n\n段落B\n\n段落C"
    chunks = chunk_paragraphs(text, max_chars=100)
    assert len(chunks) == 1
    assert "段落A" in chunks[0]


def test_chunk_long_paragraph_hard_split():
    p = "x" * 1500
    chunks = chunk_paragraphs(p, max_chars=600, overlap_chars=100)
    # 应被切成多块，每块 ≤ max_chars（最后一块除外）+overlap
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 800  # 600 + 100 overlap + 一点容差


def test_estimate_tokens():
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("中文测试") > 0