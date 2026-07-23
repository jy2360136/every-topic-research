"""单视频知识卡片生成

- 读取 sources/<bvid>.txt
- 清洗与切块
- 分块送 MiniMax 生成局部摘要
- 合并局部摘要得到最终单视频卡片
"""
from __future__ import annotations

import logging
from pathlib import Path

from .chunker import chunk_paragraphs
from .minimax_client import MinimaxClient
from .prompts import SINGLE_VIDEO_CARD_SYSTEM, single_card_prompt
from .subtitle_clean import cues_to_paragraphs

logger = logging.getLogger(__name__)


def render_paragraphs(source_txt: Path) -> str:
    """从已落盘的字幕文件读取并按 cue 清洗"""
    text = Path(source_txt).read_text(encoding="utf-8")
    # 转回 cue 形式：每行形如 "[hh:mm:ss.mmm - hh:mm:ss.mmm] content"
    from .subtitle_fetch import SubtitleCue
    import re

    cues: list[SubtitleCue] = []
    pat = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})\]\s*(.*)")
    for line in text.splitlines():
        m = pat.match(line)
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2, content = m.groups()
        from_s = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
        to_s = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000
        cues.append(SubtitleCue(from_s=from_s, to_s=to_s, content=content))
    return cues_to_paragraphs(cues)


def _summarize_chunk(client: MinimaxClient, chunk: str, title: str, owner: str, subtitle_type: str) -> str:
    """针对单个 chunk 调用 LLM 抽取关键要点"""
    prompt = (
        "请阅读以下视频「{title}」的字幕片段，提炼出 3~8 个核心要点，"
        "保留关键术语、关键步骤或代码。如果片段中没有实质性内容，请回答「无」。\n\n"
        "=====\n{chunk}\n====="
    ).format(title=title, chunk=chunk)
    return client.generate_text(
        prompt=prompt,
        system="你是严谨的研究助手，只根据给定字幕提炼要点，不要编造。",
        temperature=0.2,
        max_tokens=900,
    )


def generate_card(
    client: MinimaxClient,
    *,
    bvid: str,
    title: str,
    owner: str,
    subtitle_type: str,
    source_txt: Path,
    out_card: Path,
) -> Path:
    """生成单视频知识卡片"""
    paragraphs = render_paragraphs(source_txt)
    chunks = chunk_paragraphs(paragraphs, max_chars=6000)

    # 分块汇总
    partials: list[str] = []
    for i, c in enumerate(chunks):
        logger.info("[%s] 处理 chunk %d/%d (%d 字符)", bvid, i + 1, len(chunks), len(c))
        partials.append(
            "### 片段 " + str(i + 1) + "\n" + _summarize_chunk(client, c, title, owner, subtitle_type)
        )

    materials = "\n\n".join(partials)
    final = client.generate_text(
        prompt=single_card_prompt(
            title=title,
            owner=owner,
            subtitle_type=subtitle_type,
            body=materials,
        ),
        system=SINGLE_VIDEO_CARD_SYSTEM,
        temperature=0.2,
        max_tokens=2400,
    )

    out_card = Path(out_card)
    out_card.parent.mkdir(parents=True, exist_ok=True)
    header = f"# {title}\n\n- BV号：{bvid}\n- UP主：{owner}\n- 字幕：{subtitle_type}\n\n"
    out_card.write_text(header + final, encoding="utf-8")
    return out_card