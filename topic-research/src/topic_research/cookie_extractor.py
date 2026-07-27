"""从本地浏览器 Cookie 存储自动提取 B 站 SESSDATA

支持的浏览器（按顺序尝试）：
1. Chrome（默认 + 所有 Profile）
2. Edge（默认 + 所有 Profile）

技术细节：
- Chrome / Edge 的 Cookie 是 SQLite 数据库，文件被浏览器锁住。
  解锁办法：复制到临时目录再读（不破坏原文件）。
- 加密字段是 DPAPI 加密（Windows 用户密钥）。
- Chrome 127+ 引入了 App-Bound Encryption，本模块暂不支持；
  遇到这种情况会打 WARNING 并跳过。

用法：
    from topic_research.cookie_extractor import extract_sessdata
    sessdata = extract_sessdata()  # str | None
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# 临时复制文件路径（在 finally 里清）
_TMP_COOKIE_PATHS: list[str] = []


def _decrypt_dpapi(encrypted: bytes) -> str | None:
    """用 Windows DPAPI 解密 Chrome / Edge 的 cookie 值（v10 前）"""
    try:
        import win32crypt  # type: ignore

        # pywin32 风格调用
        decoded = win32crypt.CryptUnprotectData(
            encrypted, None, None, None, 0
        )
        if decoded and len(decoded) >= 2 and decoded[1]:
            return decoded[1].decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug("DPAPI 解密失败: %s", e)
    return None


def _read_chrome_cookies(user_data_dir: Path) -> list[tuple[str, bytes | None, str | None]]:
    """从 Chrome / Edge 的 Cookie DB 读取所有 bilibili.com 条目

    返回 list of (name, encrypted_value, plaintext_value)

    Chrome 110+ 把 Cookies 移到 Network/Cookies；老版本还在顶层 Cookies。
    同时检查两个位置。
    """
    if not user_data_dir.exists():
        return []

    # 找所有 profile + 两种 cookie 路径
    profile_dirs = []
    default_dir = user_data_dir / "Default"
    if default_dir.exists():
        profile_dirs.append(default_dir)
    for p in sorted(user_data_dir.iterdir()):
        if p.is_dir() and p.name.startswith("Profile "):
            profile_dirs.append(p)

    cookie_files: list[Path] = []
    for prof in profile_dirs:
        for rel in ("Network/Cookies", "Cookies"):  # Chrome 110+ vs 旧
            cf = prof / rel
            if cf.exists():
                cookie_files.append(cf)

    out: list[tuple[str, bytes | None, str | None]] = []
    for cookie_path in cookie_files:
        # Chrome 锁住原文件 → 复制到临时目录
        fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="chrome_cookies_")
        os.close(fd)
        try:
            shutil.copy2(cookie_path, tmp_path)
        except Exception as e:
            logger.debug("复制 cookie 文件失败 %s: %s", cookie_path, e)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            continue
        _TMP_COOKIE_PATHS.append(tmp_path)

        try:
            conn = sqlite3.connect(tmp_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, encrypted_value, value FROM cookies "
                    "WHERE host_key LIKE '%bilibili.com' AND name='SESSDATA'"
                )
                for name, enc, plain in cur.fetchall():
                    out.append((name, enc, plain))
            finally:
                conn.close()
        except Exception as e:
            logger.debug("读取 cookie DB 失败 %s: %s", cookie_path, e)

    return out


def _try_browser(name: str, user_data_dir: Path) -> str | None:
    """尝试从一个浏览器的 user_data_dir 提取 SESSDATA"""
    rows = _read_chrome_cookies(user_data_dir)
    for cookie_name, enc, plain in rows:
        if cookie_name != "SESSDATA":
            continue
        if plain:
            logger.info("从 %s 拿到 SESSDATA（明文，%d 字符）", name, len(plain))
            return plain
        if enc:
            # Chrome 80+ 几乎所有 cookie 都是 v10 encrypted
            # v10 前 = DPAPI 解密即可；v10 / v11 需要 Chrome 的 os_crypt
            # 这里先尝试 DPAPI；如果返回的是 16 字节随机前缀 + 加密数据，
            # 说明是新版，会被 decrypt 出来成乱码
            decrypted = _decrypt_dpapi(enc)
            if decrypted and "账号未登录" not in decrypted and len(decrypted) > 50:
                logger.info("从 %s 拿到 SESSDATA（DPAPI，%d 字符）", name, len(decrypted))
                return decrypted
            logger.warning(
                "%s 的 SESSDATA 用了 Chrome 80+ 的 v10 加密（App-Bound Encryption），"
                "需要 Chrome 主进程上下文解密，本模块暂不支持。"
                "请改用 --auto-cookie=cdp 模式或手动粘贴 SESSDATA。",
                name,
            )
            return None
    return None


def extract_sessdata() -> str | None:
    """自动从本地浏览器提取 B 站 SESSDATA

    尝试顺序：Chrome → Edge

    注意：Chrome 110+ 把 cookie DB 移到 Network/Cookies 并被 Network Service
    进程独占锁住，shutil.copy2 在大多数 Windows 上会 PermissionError。
    这种情况会 WARNING 提示改用 CDP 模式（--from-cdp），
    或者先关掉浏览器再跑。
    """
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        logger.warning("LOCALAPPDATA 未设置，跳过浏览器 cookie 提取")
        return None

    browsers = [
        ("Chrome", Path(local) / "Google" / "Chrome" / "User Data"),
        ("Edge", Path(local) / "Microsoft" / "Edge" / "User Data"),
    ]

    for name, user_data_dir in browsers:
        try:
            sessdata = _try_browser(name, user_data_dir)
            if sessdata:
                return sessdata
        except Exception as e:
            logger.debug("%s 提取失败: %s", name, e)

    logger.warning(
        "本地文件读取失败（很可能 Chrome 110+ 锁住了 cookie DB）。\n"
        "  选项 1: 先关掉 Chrome 再跑\n"
        "  选项 2: Chrome 加 --remote-debugging-port=9222 启动，用 --from-cdp\n"
        "  选项 3: 浏览器 Application 面板复制 SESSDATA 粘到 .env"
    )
    return None


def extract_sessdata_cdp(port: int = 9222) -> str | None:
    """通过 Chrome DevTools Protocol 从运行中的 Chrome 提取 B 站 SESSDATA

    使用前提：Chrome 启动时带 --remote-debugging-port=9222
    启动方法：
      - 关闭所有 Chrome 窗口
      - chrome.exe --remote-debugging-port=9222
      - 或桌面快捷方式属性 → 目标 → 末尾加 --remote-debugging-port=9222

    优点：跨 Chrome 版本稳定，不碰文件
    缺点：需要 Chrome 启动时加 flag（一次配置）
    """
    try:
        import urllib.request
        import json as jsonlib

        # 1. 列出所有可用 page / target
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
        targets = jsonlib.loads(resp.read())
    except Exception as e:
        logger.warning("CDP 端口 %d 连不上: %s。请确认 Chrome 启动时加了 --remote-debugging-port=%d", port, e, port)
        return None

    # 2. 找有 wsUrl 的 page（type=page）
    page = next((t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)
    if not page:
        logger.warning("CDP: 没找到 page target（需要先打开一个 Chrome 窗口）")
        return None

    # 3. 通过 websocket 调 Network.getCookies
    try:
        import websocket  # type: ignore
    except ImportError:
        logger.error(
            "需要安装 websocket-client 才能用 CDP：pip install websocket-client"
        )
        return None

    try:
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
        try:
            ws.send(jsonlib.dumps({
                "id": 1,
                "method": "Network.getCookies",
                "params": {"urls": ["https://www.bilibili.com"]},
            }))
            raw = ws.recv()
            payload = jsonlib.loads(raw)
            cookies = (payload.get("result") or {}).get("cookies") or []
            for c in cookies:
                if c.get("name") == "SESSDATA":
                    val = c.get("value", "")
                    if val:
                        logger.info("从 CDP 拿到 SESSDATA（%d 字符）", len(val))
                        return val
            logger.warning("CDP: 没在 bilibili.com cookies 里找到 SESSDATA（先在 Chrome 里登录 B 站）")
            return None
        finally:
            ws.close()
    except Exception as e:
        logger.warning("CDP WebSocket 调用失败: %s", e)
        return None


def extract_sessdata_from_clipboard() -> str | None:
    """从 Windows 剪贴板读 SESSDATA

    用户操作：浏览器 Application 面板 → Cookies → 找到 SESSDATA → 复制 Value
    然后跑 CLI。CLI 自动读剪贴板。
    """
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=5,
        )
        text = (result.stdout or "").strip().strip('"')
        # SESSDATA 通常 200+ 字符，含百分号和逗号
        if 50 < len(text) < 1000 and "%" in text or "," in text:
            return text
    except Exception as e:
        logger.debug("剪贴板读取失败: %s", e)
    return None


def cleanup_tmp() -> None:
    """清理临时复制的 cookie DB 文件"""
    for p in _TMP_COOKIE_PATHS:
        try:
            os.unlink(p)
        except OSError:
            pass
    _TMP_COOKIE_PATHS.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    v = extract_sessdata()
    if v:
        print(f"\n✅ 拿到 SESSDATA，长度 {len(v)}")
        print(f"前 20 字符: {v[:20]}...")
    else:
        print("\n❌ 没拿到 SESSDATA")
    cleanup_tmp()