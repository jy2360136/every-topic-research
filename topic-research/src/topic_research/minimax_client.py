"""MiniMax API 客户端封装

提供：
- 同步文本生成
- JSON 输出模式（强制模型返回合法 JSON）
- 自动指数退避重试
- Token 用量统计
- 流式续写支持（针对长文本输出）
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .config import CONFIG, require_api_key

logger = logging.getLogger(__name__)


class MinimaxError(Exception):
    """通用 MiniMax 调用错误"""


class MinimaxRateLimited(MinimaxError):
    """触发限流"""


class MinimaxServerError(MinimaxError):
    """5xx 类服务端错误"""


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: dict | None) -> None:
        if not usage:
            return
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.output_tokens += int(usage.get("output_tokens", 0) or 0)


class MinimaxClient:
    """MiniMax API 客户端，封装鉴权、重试、JSON 解析、用量统计"""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or require_api_key()
        self.api_url = api_url or CONFIG.MINIMAX_API_URL
        self.model = model or CONFIG.MINIMAX_MODEL
        self.timeout = timeout
        self.usage = UsageStats()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict) -> dict:
        resp = requests.post(
            self.api_url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise MinimaxError(f"响应非 JSON: {resp.text[:200]}") from e

        if resp.status_code == 429:
            raise MinimaxRateLimited(str(data))
        if resp.status_code >= 500:
            raise MinimaxServerError(str(data))
        if resp.status_code != 200:
            raise MinimaxError(f"HTTP {resp.status_code}: {data}")

        # 兼容 base_resp 与直接返回
        base = data.get("base_resp")
        if base and base.get("status_code", 0) != 0:
            raise MinimaxError(f"业务错误: {base.get('status_msg', '')}")

        return data

    def _extract_text(self, data: dict) -> str:
        content = data.get("content", [])
        if isinstance(content, str):
            return content
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        return ""

    @retry(
        retry=retry_if_exception_type((MinimaxRateLimited, MinimaxServerError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _call_with_retry(self, payload: dict) -> dict:
        return self._post(payload)

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """普通文本生成"""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        data = self._call_with_retry(payload)
        self.usage.add(data.get("usage"))
        return self._extract_text(data).strip()

    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        schema_hint: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        max_parse_retries: int = 2,
    ) -> dict | list | Any:
        """要求模型返回 JSON；解析失败会自动让模型重输出"""
        sys_msg = system or "你是一名严谨的研究助手，只输出合法 JSON。"
        if schema_hint:
            sys_msg += "\n\n输出 JSON Schema 提示：\n" + schema_hint

        for attempt in range(max_parse_retries + 1):
            text = self.generate_text(
                prompt=prompt,
                system=sys_msg,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                return _safe_json_loads(text)
            except json.JSONDecodeError as e:
                logger.warning("JSON 解析失败 (attempt %d): %s", attempt + 1, e)
                if attempt == max_parse_retries:
                    raise MinimaxError(f"模型多次无法输出合法 JSON: {text[:200]}") from e
                prompt = (
                    "上一条输出不是合法 JSON，请重新输出严格的 JSON。\n\n"
                    f"原问题：{prompt}\n\n上次输出：{text[:500]}"
                )

    def total_usage(self) -> dict:
        return {
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
        }


def _safe_json_loads(text: str) -> Any:
    """支持 ```json ... ``` 围栏以及首尾杂文本"""
    text = text.strip()
    # 去除 markdown 围栏
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首行 ```xxx 和末尾 ```
        inner = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        text = "\n".join(inner).strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试抽取第一个 JSON 块
        for start_char in ("{", "["):
            i = text.find(start_char)
            if i >= 0:
                snippet = text[i:]
                end = _find_json_end(snippet)
                if end > 0:
                    return json.loads(snippet[:end])
        raise


def _find_json_end(s: str) -> int:
    """找到第一个完整 JSON 的结束位置"""
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1