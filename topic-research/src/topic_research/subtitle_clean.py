"""字幕清洗

- 去除 BBCode 标记
- 去除重叠时间戳片段
- 合并连续短句
- 规范化空白与标点
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CleanCue:
    from_s: float
    to_s: float
    text: str


_BBCODE = re.compile(r"\{[^}]*\}|\\[a-zA-Z]+|[<\[](em|b|i|u|strong)[>\]]")
_DUP_PUNCT = re.compile(r"([，。！？,.!?]){2,}")
_WHITESPACE = re.compile(r"\s+")
_TIMESTAMP_LINE = re.compile(r"\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*")
_BLANK = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    text = _BBCODE.sub("", text)
    text = _TIMESTAMP_LINE.sub("", text)
    text = _DUP_PUNCT.sub(r"\1", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def merge_short_cues(
    cues: list, min_len: int = 6, max_window_s: float = 4.0
) -> list[CleanCue]:
    """将连续的过短字幕合并到一个窗口内"""
    out: list[CleanCue] = []
    buf: list = []

    def flush():
        if not buf:
            return
        text = " ".join(clean_text(c.content) for c in buf if clean_text(c.content))
        if not text:
            buf.clear()
            return
        out.append(CleanCue(buf[0].from_s, buf[-1].to_s, text))
        buf.clear()

    for c in cues:
        if not buf:
            buf.append(c)
            continue
        if (
            len(" ".join(cc.content for cc in buf)) >= min_len
            or (c.from_s - buf[-1].to_s) > max_window_s
        ):
            flush()
            buf.append(c)
        else:
            buf.append(c)
    flush()
    return out


def cues_to_paragraphs(cues: list, max_paragraph_chars: int = 280) -> str:
    """输出适合作为 LLM 输入的段落文本"""
    cleaned = merge_short_cues(cues)
    paragraphs: list[str] = []
    buf = ""
    for c in cleaned:
        line = c.text.strip()
        if not line:
            continue
        # 时间戳可保留用于上下文提示
        line_with_ts = f"[{_fmt_short(c.from_s)}] {line}"
        if len(buf) + len(line_with_ts) + 1 > max_paragraph_chars:
            paragraphs.append(buf.strip())
            buf = line_with_ts
        else:
            buf = f"{buf}\n{line_with_ts}".strip()
    if buf:
        paragraphs.append(buf.strip())
    text = "\n\n".join(paragraphs)
    text = _BLANK.sub("\n\n", text)
    return text


def _fmt_short(s: float) -> str:
    sec = int(s)
    h, rem = divmod(sec, 3600)
    m, ss = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{ss:02d}"
    return f"{m:02d}:{ss:02d}"