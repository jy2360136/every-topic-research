"""bili_session 单元测试

B 站 player/v2 接口对未登录请求会返回空 subtitles 列表。
本测试只验证 Session 工厂行为：未配置 SESSDATA 不应附加 cookie；
配置 SESSDATA 后应附加 .bilibili.com 域的 SESSDATA cookie。
"""
import importlib
import sys

import requests


def _has_sessdata(sess: requests.Session) -> bool:
    """检查 session 中是否存在任何 SESSDATA cookie（任意域）"""
    return any(c.name == "SESSDATA" for c in sess.cookies)


def _reload_bili_session_with_sessdata(sessdata_value: str):
    """注入一个假的 CONFIG（含指定 SESSDATA）到 bili_session，然后 reload"""
    fake_module = type(sys)("fake_topic_research_config")
    fake_module.CONFIG = type("FakeConfig", (), {"BILI_SESSDATA": sessdata_value})()
    # 清缓存，确保 bili_session 重新 import 我们的 fake_config
    for mod_name in list(sys.modules):
        if mod_name.startswith("topic_research.bili_session") or mod_name == "topic_research.config":
            del sys.modules[mod_name]
    # 插入 fake config 作为 topic_research.config 的替身
    sys.modules["topic_research.config"] = fake_module
    import topic_research.bili_session as bs
    importlib.reload(bs)
    return bs


def test_no_sessdata_means_no_cookie():
    bs = _reload_bili_session_with_sessdata("")
    sess = bs.build_session()
    assert not _has_sessdata(sess), "未配置 SESSDATA 时不应附加 cookie"


def test_sessdata_attached_as_cookie():
    bs = _reload_bili_session_with_sessdata("abc123%2Ctest")
    sess = bs.build_session()
    # 通过 domain 拿 cookie
    assert sess.cookies.get("SESSDATA", domain=".bilibili.com") == "abc123%2Ctest"


def test_existing_session_keeps_other_cookies():
    bs = _reload_bili_session_with_sessdata("")
    sess = requests.Session()
    sess.cookies.set("foo", "bar", domain=".bilibili.com")
    out = bs.build_session(sess)
    assert out.cookies.get("foo", domain=".bilibili.com") == "bar"
    assert not _has_sessdata(out)
