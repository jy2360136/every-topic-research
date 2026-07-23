"""读取 selection.json"""
import json
from pathlib import Path


def load_selection(selection_file: Path) -> list[dict]:
    """读取用户在浏览器里导出的 selection.json"""
    p = Path(selection_file)
    if not p.exists():
        raise FileNotFoundError(
            f"未找到 {p}。请先在浏览器候选页点击「导出勾选 selection.json」，"
            f"并把文件放回主题目录。"
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    selected = data.get("selected", [])
    if not isinstance(selected, list):
        raise ValueError("selection.json 中 selected 字段应为列表")
    # 过滤无字幕视频
    return [s for s in selected if s.get("subtitle_type") in ("official", "auto", "unknown")]