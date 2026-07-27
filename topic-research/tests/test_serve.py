"""serve 子系统单元测试

不启 HTTP server，只直接调 Handler 处理函数，验证：
- /api/health 返回 ok
- /api/save-selection 写入文件
- /api/run-process 在没有 selection.json 时拒绝
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def handler_setup(tmp_path, monkeypatch):
    """构造一个绑定好 topic_dir 的 Handler 实例，避免启动 HTTP server"""
    topic_dir = tmp_path / "topics" / "demo"
    topic_dir.mkdir(parents=True)
    (topic_dir / "candidates.html").write_text(
        "<html><body><button onclick='exportSelection()'>导出</button></body></html>",
        encoding="utf-8",
    )
    # 用 fake cli 模块替换，避免触发真实搜索/处理
    fake_cli = mock.MagicMock()
    fake_cli.cmd_process = mock.MagicMock()
    sys.modules["topic_research.cli"] = fake_cli

    from topic_research import serve as srv

    cls = srv.build_handler(tmp_path, topic_dir, "demo", fake_cli)
    return cls, topic_dir, fake_cli, srv


class _StubRequest:
    """最小 stub，让 _read_body 能工作"""

    def __init__(self, body: bytes, headers: dict | None = None):
        self.headers = headers or {"Content-Length": str(len(body))}
        self.rfile = mock.MagicMock()
        self.rfile.read.return_value = body


class _StubWFile:
    def __init__(self):
        self.calls: list[tuple[int, str, bytes]] = []

    def write(self, data: bytes):
        self.calls.append(("write", "data", data))


def _make_handler(cls, body: bytes = b""):
    """直接实例化 Handler，stub 掉网络 IO（绕过 __init__，手动设必要属性）"""
    h = cls.__new__(cls)
    h.raw_requestline = b"GET / HTTP/1.1"
    h.requestline = "GET / HTTP/1.1"
    h.request_version = "HTTP/1.1"
    h.command = "GET"
    h.close_connection = True
    h.path = "/"
    h.headers = {"Content-Length": str(len(body))}
    h.rfile = mock.MagicMock()
    h.rfile.read.return_value = body
    h.wfile = _StubWFile()
    return h


def test_health(handler_setup):
    cls, *_ = handler_setup
    h = _make_handler(cls)
    h.do_GET()  # path = "/", but we want /api/health
    h.path = "/api/health"
    h.do_GET()
    payload = json.loads(h.wfile.calls[-1][2])
    assert payload == {"ok": True, "slug": "demo"}


def test_save_selection_writes_file(handler_setup):
    cls, topic_dir, *_ = handler_setup
    body = json.dumps({"selected": [{"bvid": "BV1", "title": "t", "subtitle_type": "official"}]}).encode()
    h = _make_handler(cls, body)
    h.path = "/api/save-selection"
    h.do_POST()
    payload = json.loads(h.wfile.calls[-1][2])
    assert payload["ok"] is True
    assert payload["count"] == 1
    saved = (topic_dir / "selection.json").read_text(encoding="utf-8")
    assert "BV1" in saved


def test_save_selection_rejects_empty(handler_setup):
    cls, *_ = handler_setup
    body = json.dumps({"selected": []}).encode()
    h = _make_handler(cls, body)
    h.path = "/api/save-selection"
    h.do_POST()
    payload = json.loads(h.wfile.calls[-1][2])
    assert payload["ok"] is False


def test_run_process_requires_selection(handler_setup):
    cls, *_ = handler_setup
    h = _make_handler(cls)
    h.path = "/api/run-process"
    h.do_POST()
    payload = json.loads(h.wfile.calls[-1][2])
    assert payload["ok"] is False
    assert "selection.json" in payload["error"]