"""本地 HTTP server，让 candidates.html 走 HTTP 而不是 file://

浏览器安全模型下：
- file:// 模式下 JS 不能 fetch 任意文件
- a.download 总会触发下载对话框
- File System Access API 必须弹"另存为"对话框

解决：起一个绑定 127.0.0.1 的本地 HTTP server，candidates.html 通过 fetch
把 selection 数据 POST 到 /api/save-selection，server 直接写文件到主题目录。
零对话框、零路径选择，跨浏览器可用。
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)


# process 状态（单任务，简单内存存储）
_process_state: dict = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "exit_code": None,
    "log_tail": [],
}


class Handler(BaseHTTPRequestHandler):
    """HTTP handler，绑死到具体 topic_dir / slug"""

    # 由 build_handler 注入
    project_root: Path = Path()
    topic_dir: Path = Path()
    slug: str = ""
    cli_module = None  # topic_research.cli 引用，避免循环导入

    # 关闭 access log 默认输出，太多噪声
    def log_message(self, fmt, *args):  # noqa: A003
        logger.debug(fmt, *args)

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning("POST body 解析失败: %s", e)
            return None

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._serve_html()
        if path == "/api/status":
            return self._json(self._build_status())
        if path == "/api/health":
            return self._json({"ok": True, "slug": self.slug})
        self._send_json(404, {"error": "not found", "path": path})

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/save-selection":
            return self._save_selection()
        if path == "/api/run-process":
            return self._run_process()
        self._send_json(404, {"error": "not found", "path": path})

    # ---- handlers ----

    def _serve_html(self) -> None:
        """读 candidates.html，把 a.download 逻辑替换成 fetch POST"""
        html_path = self.topic_dir / "candidates.html"
        if not html_path.exists():
            return self._send_json(404, {"error": f"{html_path} 不存在，请先跑 search 阶段"})
        text = html_path.read_text(encoding="utf-8")

        # 注入：http 模式下改用 fetch POST
        inject = """
<script>
(function () {
  if (location.protocol !== 'http:' && location.protocol !== 'https:') return;
  // 替换原有的「导出勾选」按钮行为：POST 到 /api/save-selection
  // 原按钮文本保留，绑定一个 http 专用 handler
  var btn = document.querySelector('button[onclick="exportSelection()"]');
  if (!btn) return;
  btn.removeAttribute('onclick');
  btn.addEventListener('click', function () {
    var payload = {
      topic_slug: window.TOPIC_SLUG || '',
      exported_at: new Date().toISOString(),
      selected: items.filter(function (i) { return i.checked && i.subtitle_type !== 'none'; })
        .map(function (i) {
          return {
            bvid: i.bvid, title: i.title, owner: i.owner,
            duration: i.duration, subtitle_type: i.subtitle_type,
            score: i.score, url: i.url
          };
        })
    };
    fetch('/api/save-selection', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); }).then(function (j) {
      var msg = document.getElementById('export-msg');
      if (j.ok) {
        msg.innerHTML = '✅ 已直接保存到 <code>' + j.path + '</code>。'
          + '<br><button id="run-process-btn" style="margin-top:8px;padding:8px 14px;background:#1d4ed8;color:#fff;border:none;border-radius:6px;cursor:pointer">▶ 立即开始处理</button>';
        document.getElementById('run-process-btn').addEventListener('click', function () {
          this.disabled = true; this.textContent = '处理中...';
          fetch('/api/run-process', { method: 'POST' })
            .then(function (r) { return r.json(); }).then(function (j2) {
              if (j2.ok) {
                this.textContent = '✅ 已开始处理';
                pollStatus();
              } else {
                this.textContent = '❌ 启动失败';
                msg.innerHTML += '<br><span style="color:#c00">' + (j2.error || '') + '</span>';
              }
            }.bind(this));
        });
      } else {
        msg.innerHTML = '❌ 保存失败：' + (j.error || 'unknown');
      }
    });
  });

  function pollStatus() {
    fetch('/api/status').then(function (r) { return r.json(); }).then(function (j) {
      var msg = document.getElementById('export-msg');
      msg.innerHTML = '✅ 已直接保存。<br>处理进度：'
        + '<br>' + (j.log_tail || []).map(function (l) { return '<code>' + l + '</code>'; }).join('<br>')
        + (j.running ? '<br><small>轮询中...</small>' : (j.exit_code === 0
            ? '<br><a href="../report.md" target="_blank">查看 report.md</a>'
            : (j.exit_code !== null ? '<br><span style="color:#c00">失败 exit=' + j.exit_code + '</span>' : '')));
      if (j.running) setTimeout(pollStatus, 1500);
    });
  }
})();
</script>
"""
        text = text.replace("</body>", inject + "\n</body>")
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _save_selection(self) -> None:
        data = self._read_body()
        if data is None:
            return self._json({"ok": False, "error": "invalid JSON body"})
        selected = data.get("selected") or []
        if not selected:
            return self._json({"ok": False, "error": "selected 为空"})
        target = self.topic_dir / "selection.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("selection.json saved (%d 个) → %s", len(selected), target)
        self._json({"ok": True, "path": str(target), "count": len(selected)})

    def _run_process(self) -> None:
        if _process_state["running"]:
            return self._json({"ok": False, "error": "已有 process 在跑"})
        selection = self.topic_dir / "selection.json"
        if not selection.exists():
            return self._json({"ok": False, "error": f"selection.json 不存在：{selection}"})

        def worker():
            _process_state["running"] = True
            _process_state["last_started_at"] = time.time()
            _process_state["log_tail"] = []
            try:
                ns = argparse.Namespace(slug=self.slug, topic=None)
                self.cli_module.cmd_process(ns)
                _process_state["exit_code"] = 0
            except SystemExit as e:
                _process_state["exit_code"] = int(e.code) if isinstance(e.code, int) else 1
            except Exception as e:
                logger.exception("process 异常")
                _process_state["log_tail"].append(f"[error] {e}")
                _process_state["exit_code"] = 1
            finally:
                _process_state["running"] = False
                _process_state["last_finished_at"] = time.time()

        threading.Thread(target=worker, daemon=True).start()
        return self._json({"ok": True})

    def _build_status(self) -> dict:
        # 把最近日志截尾（同时从 logging 抓一下最新一行）
        log_tail = list(_process_state["log_tail"])
        # 简单粗暴：抓 logger buffer（如果 future 有需要可换成 logging.Handler）
        return {
            "running": _process_state["running"],
            "last_started_at": _process_state["last_started_at"],
            "last_finished_at": _process_state["last_finished_at"],
            "exit_code": _process_state["exit_code"],
            "log_tail": log_tail[-30:],
        }

    def _json(self, payload, code=200):
        self._send_json(code, payload)


def build_handler(project_root: Path, topic_dir: Path, slug: str, cli_module):
    """返回一个绑定好上下文的 Handler 类"""
    import topic_research.cli as cli
    cls = type(
        "BoundHandler",
        (Handler,),
        {
            "project_root": project_root,
            "topic_dir": topic_dir,
            "slug": slug,
            "cli_module": cli,
        },
    )
    return cls


def serve(project_root: Path, slug: str, port: int = 8765, open_browser: bool = True) -> None:
    topic_dir = project_root / "topics" / slug
    if not topic_dir.exists():
        raise SystemExit(f"主题目录不存在：{topic_dir}。请先跑 search 阶段。")

    from . import cli as cli_module

    handler_cls = build_handler(project_root, topic_dir, slug, cli_module)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    url = f"http://127.0.0.1:{port}/"

    # 注册 logging handler 把日志写到 _process_state.log_tail
    class _LogCapture(logging.Handler):
        def emit(self, record):
            try:
                line = self.format(record)
                _process_state["log_tail"].append(line)
                # 控制长度
                if len(_process_state["log_tail"]) > 500:
                    del _process_state["log_tail"][:len(_process_state["log_tail"]) - 500]
            except Exception:
                pass

    capture = _LogCapture()
    capture.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    capture.setLevel(logging.INFO)
    logging.getLogger("topic_research").addHandler(capture)

    print(f"\n  topic-research serve  →  {url}")
    print(f"  主题目录：{topic_dir}")
    print(f"  浏览器打开后：勾选视频 → 点「导出勾选」→ 文件直接落到 selection.json")
    print(f"  → 再点「立即开始处理」即跑 process 全流程")
    print(f"  Ctrl+C 退出\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopping...")
        server.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    serve(project_root, args.slug, args.port, open_browser=not args.no_open)