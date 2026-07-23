"""项目配置加载"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    MINIMAX_API_KEY: str = os.environ.get("MINIMAX_API_KEY", "").strip()
    MINIMAX_API_URL: str = os.environ.get(
        "MINIMAX_API_URL", "https://api.minimaxi.com/anthropic/v1/messages"
    )
    MINIMAX_MODEL: str = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
    BILI_CANDIDATE_LIMIT: int = int(os.environ.get("BILI_CANDIDATE_LIMIT", "60"))
    BILI_MIN_DURATION: int = int(os.environ.get("BILI_MIN_DURATION", "300"))
    BILI_MAX_DURATION: int = int(os.environ.get("BILI_MAX_DURATION", "2400"))
    BILI_SESSDATA: str = os.environ.get("BILI_SESSDATA", "").strip()
    TOPIC_CONCURRENCY: int = int(os.environ.get("TOPIC_CONCURRENCY", "2"))


CONFIG = Config()


def require_api_key() -> str:
    if not CONFIG.MINIMAX_API_KEY:
        raise SystemExit(
            "MINIMAX_API_KEY is not set. Please put the key into .env "
            "or export it as an environment variable before running."
        )
    return CONFIG.MINIMAX_API_KEY