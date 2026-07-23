"""生成一份带示例数据的 candidates.html，用于本地预览 UI

在你这台机器无法直连 B 站的情况下，先让你看到完整页面长什么样、
勾选按钮如何工作、selection.json 导出格式是什么。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from topic_research.candidates_html import render
from topic_research.score_candidates import ScoredCandidate
from topic_research.search_bilibili import VideoMeta

ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = ROOT / "topics" / "agent-development"
OUT_HTML = TOPIC_DIR / "candidates.html"


def _meta(**kw):
    base = dict(
        bvid="BV1", aid=1, title="示例标题", owner_mid=0, owner_name="示例UP主",
        duration=900, publish_time=0, description="", view=200000, like=3000,
        coin=200, favorite=1500, reply=300, share=80, danmaku=1000,
        subtitle_type="official",
    )
    base.update(kw)
    return VideoMeta(**base)


def main():
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    metas = [
        _meta(
            bvid="BV1xx411c7mD",
            title="Agent 开发入门：ReAct + Function Calling 实操",
            owner_name="CodeTuber",
            duration=18 * 60,
            view=380000, like=12000, coin=1800, favorite=9800, reply=2500,
            danmaku=4200,
            subtitle_type="official",
            cover="https://i0.hdslb.com/bfs/archive/abc.jpg",
            publish_time=1717200000,
            description="从零搭建一个能调用工具的 agent，覆盖 ReAct、function calling、记忆。",
            tag=["agent", "AI"],
        ),
        _meta(
            bvid="BV1xx411c7mE",
            title="LangGraph 实战：构建可观测的多 Agent 系统",
            owner_name="AIExplorer",
            duration=27 * 60,
            view=210000, like=7400, coin=1100, favorite=6500, reply=1800,
            danmaku=3000,
            subtitle_type="auto",
            cover="https://i0.hdslb.com/bfs/archive/def.jpg",
            publish_time=1714500000,
            description="用 LangGraph 搭建多 Agent 系统，讲解节点、边、状态机。",
            tag=["LangGraph", "agent"],
        ),
        _meta(
            bvid="BV1xx411c7mF",
            title="为什么你的 Agent 不稳定？5 个常见坑",
            owner_name="AgentDoctor",
            duration=12 * 60,
            view=150000, like=4800, coin=620, favorite=4200, reply=900,
            danmaku=1600,
            subtitle_type="official",
            cover="https://i0.hdslb.com/bfs/archive/ghi.jpg",
            publish_time=1719800000,
            description="讲解 agent 不稳定的常见原因及规避方法。",
            tag=["agent", "debug"],
        ),
        _meta(
            bvid="BV1xx411c7mG",
            title="手写一个极简 Agent：从规划到工具调用",
            owner_name="CodeTeacher",
            duration=45 * 60,
            view=520000, like=22000, coin=3400, favorite=19000, reply=4500,
            danmaku=8000,
            subtitle_type="auto",
            cover="https://i0.hdslb.com/bfs/archive/jkl.jpg",
            publish_time=1712000000,
            description="从规划到工具调用，全程手写一个 agent。",
            tag=["agent", "tutorial"],
        ),
        _meta(
            bvid="BV1xx411c7mH",
            title="闲聊：AI 行业最近发生的事（无字幕）",
            owner_name="NewsUP",
            duration=8 * 60,
            view=180000, like=3200, coin=200, favorite=1500, reply=1100,
            danmaku=2400,
            subtitle_type="none",
            cover="https://i0.hdslb.com/bfs/archive/mno.jpg",
            publish_time=1719700000,
            description="随便聊聊行业动态。",
            tag=["news"],
        ),
        _meta(
            bvid="BV1xx411c7mI",
            title="Agent 评估：如何衡量一个 agent 的好坏",
            owner_name="EvalLab",
            duration=22 * 60,
            view=90000, like=2800, coin=380, favorite=2400, reply=600,
            danmaku=900,
            subtitle_type="official",
            cover="https://i0.hdslb.com/bfs/archive/pqr.jpg",
            publish_time=1715000000,
            description="讲解 agent 评估指标与基准测试。",
            tag=["agent", "evaluation"],
        ),
    ]

    now_ts = 1721000000  # 2024-07-15
    scored = []
    for m in metas:
        from topic_research.score_candidates import score_candidate
        scored.append(score_candidate(m, "agent 开发", now_ts))
    scored.sort(key=lambda s: s.score, reverse=True)

    render(scored, title="Agent 开发（示例数据）", slug="agent-development", out_path=OUT_HTML)
    print(f"Demo candidates HTML generated at: {OUT_HTML}")


if __name__ == "__main__":
    main()