"""离线测试 minimax_client 的 JSON 解析逻辑（不实际发请求）"""
from topic_research.minimax_client import _safe_json_loads


def test_safe_json_loads_plain():
    assert _safe_json_loads('{"a": 1}') == {"a": 1}
    assert _safe_json_loads("[1,2,3]") == [1, 2, 3]


def test_safe_json_loads_with_fence():
    text = "```json\n{\"a\": 2}\n```"
    assert _safe_json_loads(text) == {"a": 2}


def test_safe_json_loads_with_extra_text():
    text = "以下为 JSON 输出：\n{\"a\": 3}\n谢谢！"
    assert _safe_json_loads(text) == {"a": 3}