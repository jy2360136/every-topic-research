"""state.json 读写"""
import json
from datetime import datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class StateStore:
    def __init__(self, topic_dir: Path):
        self.path = Path(topic_dir) / "state.json"
        self.data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {
            "topic": self.path.parent.name,
            "title": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "videos": {},
            "report_state": "pending",
            "report_file": "",
            "last_stage": "init",
            "candidates_html": "",
            "selection_file": "",
        }

    def save(self) -> None:
        self.data["updated_at"] = now_iso()
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- 通用字段 ----
    def set(self, key: str, value) -> None:
        self.data[key] = value

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    # ---- videos ----
    def upsert_video(self, bvid: str, **fields) -> None:
        v = self.data.setdefault("videos", {}).setdefault(bvid, {})
        v.update(fields)

    def video(self, bvid: str) -> dict:
        return self.data.setdefault("videos", {}).setdefault(bvid, {})

    def selected_videos(self) -> list[tuple[str, dict]]:
        return [
            (bvid, v)
            for bvid, v in self.data.get("videos", {}).items()
            if v.get("selection_state") == "selected"
        ]

    def update_video(self, bvid: str, **fields) -> None:
        v = self.data.setdefault("videos", {}).setdefault(bvid, {})
        v.update(fields)
        self.save()