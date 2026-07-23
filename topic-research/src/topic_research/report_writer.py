"""把跨视频汇总结果拆分为多个 Markdown 文件"""
from __future__ import annotations

import re
from pathlib import Path

SECTION_PATTERNS = [
    ("learning_path.md", r"#{1,3}\s*推荐学习路线"),
    ("search_gaps.md", r"#{1,3}\s*知识缺口与下一步搜索关键词"),
]


def split_report(report_md: Path, topic_dir: Path, topic_title: str) -> dict[str, Path]:
    """把综合报告中的特定小节拆出为独立 Markdown

    返回 {文件名: Path}
    """
    text = Path(report_md).read_text(encoding="utf-8")
    out: dict[str, Path] = {}

    for filename, pattern in SECTION_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        section_text = _extract_section(text, match.start())
        target = Path(topic_dir) / filename.replace("_", "-") if filename == "search_gaps.md" else Path(topic_dir) / filename
        # 用更直观的文件名
        if filename == "learning_path.md":
            target = Path(topic_dir) / "learning-path.md"
        elif filename == "search_gaps.md":
            target = Path(topic_dir) / "search-gaps.md"
        target.write_text(f"# {section_text.splitlines()[0].lstrip('# ').strip()}\n\n" + section_text, encoding="utf-8")
        out[filename] = target
    return out


def _extract_section(text: str, start: int) -> str:
    """提取从 start 开始的二级（##）或三级（###）小节内容"""
    # 找到下一个相同或更高级标题
    lines = text.splitlines()
    start_line = text[:start].count("\n")
    cur_level = len(re.match(r"^(#+)", lines[start_line]).group(1))
    end_line = len(lines)
    for i in range(start_line + 1, len(lines)):
        m = re.match(r"^(#+)", lines[i])
        if m and len(m.group(1)) <= cur_level:
            end_line = i
            break
    return "\n".join(lines[start_line:end_line]).strip()