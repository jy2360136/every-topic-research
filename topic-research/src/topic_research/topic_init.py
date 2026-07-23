"""主题目录初始化"""
from pathlib import Path

import yaml

from . import config as _config  # noqa: F401  (ensure .env loaded)


def slugify(text: str) -> str:
    return (
        text.strip()
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
    )


def init_topic(topics_root: Path, title: str, slug: str | None = None) -> Path:
    """创建主题目录并返回其路径"""
    topics_root = Path(topics_root).resolve()
    topics_root.mkdir(parents=True, exist_ok=True)

    if not slug:
        slug = slugify(title)
    topic_dir = topics_root / slug
    topic_dir.mkdir(parents=True, exist_ok=True)

    # 子目录
    for sub in ("candidates", "sources", "chunks", "cards", "logs"):
        (topic_dir / sub).mkdir(exist_ok=True)

    # topic.yaml
    yaml_path = topic_dir / "topic.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "title": title,
                    "slug": slug,
                    "created_at": _now_iso(),
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    return topic_dir


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")