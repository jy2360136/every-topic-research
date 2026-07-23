"""字幕文本切块

基于段落长度，按 LLM 输入上限粗略切块。中文按 1 字符 ~ 1 token 估算。
"""
from __future__ import annotations


def chunk_paragraphs(text: str, max_chars: int = 6000, overlap_chars: int = 200) -> list[str]:
    """按段落切块，超过 max_chars 的段落单独成块，过长段落硬切"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf:
            chunks.append(buf)
            buf = ""

    for p in paragraphs:
        if len(p) > max_chars:
            flush()
            for i in range(0, len(p), max_chars - overlap_chars):
                piece = p[i : i + max_chars]
                chunks.append(piece)
            continue
        if len(buf) + len(p) + 2 > max_chars:
            flush()
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p
    flush()

    # 段间 overlap
    if overlap_chars > 0 and len(chunks) > 1:
        new_chunks = [chunks[0]]
        for c in chunks[1:]:
            tail = new_chunks[-1][-overlap_chars:]
            new_chunks.append(tail + "\n" + c)
        chunks = new_chunks

    return chunks


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：英文按 4 字符/token，中文按 1.5 字符/token"""
    en = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    other = len(text) - en
    return int(en / 4 + other / 1.5)