"""集中存放 LLM prompt 模板，便于后续调整"""
SINGLE_VIDEO_CARD_SYSTEM = (
    "你是一名严谨的研究助手，擅长把视频字幕整理为结构化知识卡片。"
    "请只根据给定的字幕内容回答，不要编造没有出现的信息。"
)

SINGLE_VIDEO_CARD_PROMPT = """你是一名研究助手，下面是一段来自 B 站视频「{title}」的字幕（UP主：{owner}）。
字幕类型：{subtitle_type}。

请阅读以下字幕并输出一份结构化的知识卡片（使用 Markdown），包含以下字段：

## TL;DR
（一句话讲清楚这个视频讲了什么）

## 主题标签
（列出 3~8 个关键词）

## 核心概念
（用列表形式列出 5~12 个核心概念，并各给一句话解释）

## 关键论点
（按要点列出视频中提出的关键判断、结论或经验）

## 实操步骤 / 代码片段
（如果视频提到了具体步骤、命令、代码，请整理出来；没有则写「无」）

## 工具与资源
（视频中提到的工具、库、模型、链接等）

## 前置知识
（理解此视频需要哪些前置概念）

## 常见误区 / 反直觉点
（视频提到的易错点、踩坑、反直觉结论）

## 信息密度评分
（1~5 分；只读字幕无法判断视觉信息时评 2~3 分）

## 是否值得看原片
（结合信息密度评分给出建议，例如：内容已覆盖 / 可挑选时间戳观看 / 不必看）

下面是字幕正文（按时间戳切分，可能很长，请耐心阅读）：

=====
{body}
=====

请输出 Markdown 卡片，不要输出额外解释。
"""


CROSS_VIDEO_SYSTEM = (
    "你是一名严谨的研究助理，擅长从多份材料中提炼共识、识别冲突。"
    "请只根据给定的输入回答，不要编造未给出的事实。"
)

CROSS_VIDEO_PROMPT = """下面是关于主题「{topic}」的 {n} 个 B 站视频的知识卡片摘要。
请你综合这些卡片生成一份结构化的主题学习资料。

## 任务
1. 提炼出该主题的「知识地图」（分章节列出关键知识点）。
2. 标出多源共识：哪些观点被 ≥2 个视频同时提及。
3. 标出冲突与差异：哪些观点在不同视频中说法不同。
4. 给出「推荐学习路线」：由浅入深，应该按什么顺序看哪些视频。
5. 给出「知识缺口」：哪些方面信息不足，需要进一步搜索。

## 输入材料
=====
{materials}
=====

## 输出格式
使用 Markdown 输出，包含以下小节：
- # 知识地图
- # 多源共识
- # 冲突与差异
- # 推荐学习路线
- # 知识缺口与下一步搜索关键词
"""


def single_card_prompt(*, title: str, owner: str, subtitle_type: str, body: str) -> str:
    return SINGLE_VIDEO_CARD_PROMPT.format(
        title=title,
        owner=owner,
        subtitle_type=subtitle_type,
        body=body,
    )


def cross_video_prompt(*, topic: str, n: int, materials: str) -> str:
    return CROSS_VIDEO_PROMPT.format(topic=topic, n=n, materials=materials)