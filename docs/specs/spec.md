# topic-research — 架构与业务事实

> 详细设计稿见 [`docs/plans/2026-07-23-topic-learning-workflow-design.md`](../plans/2026-07-23-topic-learning-workflow-design.md)。
> 本文档是当前实际架构与业务事实的"单一来源"，与 plans/ 设计稿有冲突时以本文件为准（并在 CHANGELOG 中说明）。

## 1. 项目定位

一个**纯本地 Python CLI 工具**，把 B 站视频字幕整理为可学习的主题资料。

不是 Web 服务，不依赖数据库，不依赖前端构建。

## 2. 入口与子命令

唯一 CLI 入口：`python -m topic_research.cli`

```text
topic-research
├── search    搜索 B 站候选 + 生成 candidates.html
├── process   处理已选视频：下载字幕 + 生成卡片 + 跨视频汇总
└── init      仅创建主题目录
```

## 3. 模块划分

`topic-research/src/topic_research/`

| 模块 | 职责 | 复用度 |
|---|---|---|
| `config.py` | 加载 `.env`；校验 API Key | 唯一 |
| `minimax_client.py` | MiniMax API 封装（重试 / JSON 容错 / 用量统计） | 通用 |
| `prompts.py` | 集中存放 LLM Prompt 模板 | 通用 |
| `topic_init.py` | 创建主题目录结构、写 topic.yaml | 通用 |
| `state_store.py` | state.json 读写、断点续跑 | 通用 |
| `search_bilibili.py` | B 站搜索 / 详情 / 元数据 | 仅 B 站 |
| `search_bing_bilibili.py` | Bing 兜底：用于无法直连 api.bilibili.com 的环境 | 仅 B 站 |
| `score_candidates.py` | 综合评分（7 维权重） | 通用 |
| `candidates_html.py` | 渲染 candidates.html | 通用 |
| `selection_io.py` | 读取 selection.json | 通用 |
| `subtitle_fetch.py` | 下载 B 站字幕（官方/自动） | 仅 B 站 |
| `subtitle_clean.py` | 字幕清洗 + 短句合并 | 通用 |
| `chunker.py` | 按段落切块 | 通用 |
| `card_generator.py` | 单视频知识卡片 | 通用 |
| `cross_synthesizer.py` | 跨视频汇总 | 通用 |
| `report_writer.py` | 拆出 learning-path.md / search-gaps.md | 通用 |
| `cli.py` | argparse + 阶段调度 | 唯一 |

## 4. 数据流

```text
[1] 用户：python -m topic_research.cli search --topic "agent 开发" --slug agent-development
    ↓
[2] search_bilibili.collect → 搜索元数据 + 字幕类型探测
    ↓
[3] score_candidates.score_all → 综合分 + 降权原因
    ↓
[4] candidates_html.render → 写入 candidates/<bvid>.json + candidates.html
    ↓
[5] 用户在浏览器勾选 → 导出 selection.json → 放回 topics/<slug>/
    ↓
[6] python -m topic_research.cli process --slug agent-development
    ↓
[7] subtitle_fetch.fetch_subtitle → sources/<bvid>.txt
    ↓
[8] subtitle_clean.cues_to_paragraphs → chunker.chunk_paragraphs → chunks/<bvid>/<n>.txt
    ↓
[9] minimax_client.generate_text → cards/<bvid>.md
    ↓
[10] minimax_client.generate_text → report.md / learning-path.md / search-gaps.md
```

## 5. 主题目录结构

```text
topic-research/topics/<slug>/
├── topic.yaml              主题元数据
├── state.json              阶段状态、断点续跑
├── candidates.html         浏览器候选页
├── selection.json          用户勾选结果
├── candidates/<bvid>.json  每个视频的元数据 + 评分
├── sources/<bvid>.txt      字幕（带时间戳）
├── chunks/<bvid>/<n>.txt   切块后的字幕
├── cards/<bvid>.md         单视频知识卡片
├── report.md               跨视频综合报告
├── learning-path.md        推荐学习路线
├── search-gaps.md          知识缺口与下一步关键词
├── logs/                   运行日志
└── screenshots/            Playwright 截图（如有 UI 验证）
```

## 6. 状态字段

state.json 中每个视频的字段：

| 字段 | 取值 |
|---|---|
| `selection_state` | `pending` / `selected` / `rejected` |
| `fetch_state` | `pending` / `fetched` / `failed` / `skipped` |
| `card_state` | `pending` / `done` / `failed` |
| `subtitle_type` | `official` / `auto` / `none` / `unknown` |

顶层还有 `last_stage`（`init` / `search_done` / `process_done` / `process_done_no_cards`）。

## 7. 外部依赖

| 依赖 | 用途 | 失败处理 |
|---|---|---|
| MiniMax API | LLM 总结、汇总 | 指数退避 4 次；JSON 解析失败时让模型重输出 |
| B 站公开 API（搜索 / 详情 / 字幕） | 采集 | 单视频失败记 `error`，不影响其他视频 |
| Bing 搜索（兜底） | 当 api.bilibili.com 不可达时 | 仅在 `--use-bing` 时启用 |

## 8. 评分公式

```text
score = 0.30*播放量分 + 0.20*相关性分 + 0.15*发布时间分
      + 0.10*字幕可用分 + 0.10*UP主可信分
      + 0.10*互动率分 + 0.05*时长合理分
```

## 9. 安全约束

- API Key 只通过 `MINIMAX_API_KEY` 或 `.env` 传入，绝不入源码 / 不入日志 / 不入聊天记录。
- `.env` 已被 `.gitignore`；任何对 `.env.example` 的修改必须保持占位符为 `your-minimax-key-here`。
- 仓库内任何位置出现形如 `sk-cp-...` 的字面量都视为安全事件，需先报告位置再处置。

## 10. 已知限制

- 仅支持 B 站；YouTube 待扩展。
- 不做 ASR；没有官方/自动字幕的视频会被跳过（`subtitle_type == "none"`）。
- Bing 兜底仅在搜索阶段有效；字幕下载仍需要直连 `api.bilibili.com`。
- 第一版评分公式为初版，需根据"实际选中的视频"调权重。