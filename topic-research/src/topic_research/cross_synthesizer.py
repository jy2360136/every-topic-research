"""跨视频汇总"""
from __future__ import annotations

from pathlib import Path

from .minimax_client import MinimaxClient
from .prompts import CROSS_VIDEO_SYSTEM, cross_video_prompt


def synthesize(
    client: MinimaxClient,
    *,
    topic: str,
    cards: list[tuple[str, str, Path]],
    out_md: Path,
) -> Path:
    """cards: [(bvid, title, card_path), ...]"""
    sections: list[str] = []
    for bvid, title, card_path in cards:
        body = Path(card_path).read_text(encoding="utf-8")
        sections.append(f"## 视频：{title}（{bvid}）\n\n{body}\n")

    materials = "\n\n---\n\n".join(sections)

    final = client.generate_text(
        prompt=cross_video_prompt(topic=topic, n=len(cards), materials=materials),
        system=CROSS_VIDEO_SYSTEM,
        temperature=0.2,
        max_tokens=3000,
    )

    out_md = Path(out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(f"# 主题综合：{topic}\n\n{final}\n", encoding="utf-8")
    return out_md