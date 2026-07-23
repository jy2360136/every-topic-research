"""B 站请求 Session 工厂

统一处理：
- User-Agent / Referer
- BILI_SESSDATA cookie（登录态，subtitle 探测必需）
- 超时默认值
"""
from __future__ import annotations

import requests

from .config import CONFIG

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def build_session(sess: requests.Session | None = None) -> requests.Session:
    """返回一个带登录态（若设置了 BILI_SESSDATA）的 requests.Session

    B 站 player/v2 接口对未登录请求会把 subtitle 列表返回为空，
    并在 data.need_login_subtitle 标 true。带 SESSDATA 后才能拿到真实字幕列表。
    """
    if sess is None:
        sess = requests.Session()
    sess.headers.update(HEADERS)
    if CONFIG.BILI_SESSDATA:
        sess.cookies.set("SESSDATA", CONFIG.BILI_SESSDATA, domain=".bilibili.com")
    return sess
