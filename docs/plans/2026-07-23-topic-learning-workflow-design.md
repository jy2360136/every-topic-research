# 主题学习研究工作流 — 设计文档

> 日期：2026-07-23
> 作者：Claude（基于与用户的多次澄清）
> 状态：已批准，进入实施阶段

## 1. 背景与目标

用户想学习某个领域（例如 "Agent 开发"），目前的痛点：

- 需要在 B站、YouTube 上手动搜索并筛选视频
- 不一定有时间看完每个视频
- 已有油猴脚本可提取字幕，但提取后缺乏后续处理
- 想要把这些视频内容自动整合为可直接学习的主题资料

本工具要做的是：**输入一个研究主题 → 自动从 B站 找到高质量视频 → 由用户人工确认 → 下载字幕 → 用 MiniMax 生成单视频知识卡片和跨视频综合报告**，形成一套完整、可迭代的工作流。

## 2. 范围与非目标

### 第一版范围

- 仅支持 B站
- 不做 ASR（没有官方或自动字幕的视频直接跳过）
- 仅依赖字幕来源：官方字幕、自动字幕
- 通过本地网页让用户勾选候选视频
- 通过 MiniMax-M3 完成总结与汇总
- 输出 Markdown 报告 + 学习路线 + 状态文件

### 非目标

- 不做 YouTube（后续扩展）
- 不做 ASR
- 不做向量数据库或 RAG 检索
- 不做全网多源聚合
- 不做自动部署或 Web 服务

## 3. 整体工作流

```text
[1] 用户输入主题关键词，例如 "agent 开发"
        ↓
[2] 系统调用 B站搜索接口，按播放量排序拉取候选
        ↓
[3] 对每个候选计算综合分（相关性、播放量、互动率、发布时间、
    时长、字幕状态、UP主可信度、内容重叠度）
        ↓
[4] 渲染本地候选页面 candidates.html
        ↓
[5] 用户在浏览器中勾选想要研究的视频
        ↓
[6] 工具读取勾选结果：
        官方字幕：直接下载
        自动字幕：下载并标注"自动字幕，可能有错别字"
        无字幕：跳过
        ↓
[7] 对勾选的视频下载字幕、清洗、分块
        ↓
[8] MiniMax 分块抽取单视频知识卡片
        ↓
[9] MiniMax 跨视频汇总：去重、合并、冲突识别
        ↓
[10] 产出 Markdown 报告 + state.json
```

## 4. 关键设计决策

| 项 | 决策 |
|---|---|
| 平台范围 | 仅 B站 |
| 候选生成 | 搜索 + 综合评分 |
| 筛选界面 | 本地网页 candidates.html |
| 字幕范围 | 官方字幕 + 自动字幕，不做 ASR |
| 自动字幕提示 | 在候选页面显示黄色警告 |
| 没有字幕的视频 | 勾选时直接跳过 |
| 模型 | MiniMax-M3，API Key 仅读取环境变量 |
| 字幕工具链 | bilibili-api-python（首选），回退 yt-dlp |
| 总结方式 | 两层：单视频知识卡片 + 跨视频综合 |
| 输出形式 | Markdown 文件 + state.json |
| 项目目录 | topics/<slug>/{candidates,sources,chunks,cards,logs} |

## 5. 架构

```text
┌──────────────────────────────┐
│        CLI 入口 (cli.py)        │
│  - argparse                  │
│  - 阶段调度 + 断点续跑        │
└───────────────┬──────────────┘
                │
        ┌───────┼───────┐
        │       │       │
        ▼       ▼       ▼
   阶段1      阶段2     阶段3
   搜索+评分  候选页+选择  字幕+MiniMax

        │
        └───────┬───────┐
                ▼       ▼
        单视频卡片生成  跨视频汇总
```

每个阶段独立可重跑，依赖 state.json 记录当前状态。

## 6. 组件拆分

| 组件 | 职责 | 复用度 |
|---|---|---|
| `cli.py` | argparse、阶段调度、断点续跑 | 唯一 |
| `topic_init.py` | 创建主题目录结构、生成 topic.yaml | 通用 |
| `search_bilibili.py` | 调用 B站搜索 API、抓元数据 | 仅 B站 |
| `score_candidates.py` | 综合评分与去重 | 通用 |
| `candidates_html.py` | 渲染 candidates.html | 通用 |
| `selection_io.py` | 读取候选页面勾选结果 | 通用 |
| `subtitle_fetch.py` | 下载 B站字幕 | 仅 B站 |
| `subtitle_clean.py` | 去时间戳、合并短句、清洗重复 | 通用 |
| `chunker.py` | 按 token / 字符切分 | 通用 |
| `minimax_client.py` | MiniMax API 封装 | 通用 |
| `card_generator.py` | 单视频知识卡片生成 | 通用 |
| `cross_synthesizer.py` | 跨视频汇总 | 通用 |
| `report_writer.py` | 写出 Markdown 报告 | 通用 |
| `state_store.py` | state.json 读写 | 通用 |

## 7. 数据流

### 阶段 1：搜索与评分

```text
input: 关键词
  → bilibili 搜索接口
  → 抓元数据：标题、UP主、时长、发布时间、播放、点赞、收藏、弹幕、简介
  → 计算综合分
  → 输出 candidates/<bvid>.json
```

综合分公式：

```text
score = 0.30*播放量分 + 0.20*相关性分 + 0.15*发布时间分
      + 0.10*字幕可用分 + 0.10*UP主可信分
      + 0.10*互动率分 + 0.05*时长合理分
```

### 阶段 2：本地候选页面

- 顶部按钮：全选高分项、仅选有官方字幕项、导出勾选 JSON
- 每张卡片：封面、标题、UP主、播放/点赞/收藏、发布时间、时长、字幕类型、综合分、子分、降权原因、多选框
- 自动字幕：黄色警告条
- 无字幕：红色 “将跳过” 提示

### 阶段 3：处理已选视频

```text
读取已选 JSON + 主题目录
  对每个 bvid:
    下载字幕 → sources/<bvid>.txt
    清洗分块 → chunks/<bvid>/<n>.txt
    MiniMax 抽取 → cards/<bvid>.md
  汇总：
    MiniMax 跨视频汇总 → report.md / learning-path.md / search-gaps.md
  更新 state.json
```

## 8. 状态文件

```json
{
  "topic": "agent-development",
  "title": "Agent 开发",
  "created_at": "2026-07-23T10:00:00",
  "updated_at": "2026-07-23T10:00:00",
  "videos": {
    "BV1abc...": {
      "title": "...",
      "owner": "...",
      "duration": 1234,
      "publish_time": "...",
      "view": 100000,
      "like": 5000,
      "subtitle_type": "official|auto|none",
      "score": 0.87,
      "selection_state": "selected|rejected",
      "fetch_state": "fetched|failed|skipped",
      "card_state": "done|failed|pending",
      "card_file": "cards/BV1abc....md",
      "error": null
    }
  },
  "report_state": "done|partial|pending",
  "report_file": "report.md",
  "last_stage": "synthesis"
}
```

## 9. 错误处理

| 场景 | 处理 |
|---|---|
| MiniMax Key 未设置 | 立即退出并提示 |
| MiniMax 429/5xx | 指数退避 2^n，最多 4 次 |
| MiniMax 返回截断 | 自动续写，合并多段 |
| MiniMax 返回非 JSON | 重试，记录错误样本 |
| B站搜索失败 | 重试 3 次，再失败则降级排序选项 |
| 单个 bvid 失败 | state.json 记录失败原因，不影响其他视频 |
| 字幕不存在 | state.json 标记为 skipped |
| 用户中断 | 每完成一个视频就更新 state.json，下次自动续跑 |
| 文件 I/O 错误 | 每 5 个视频写一次快照 |

## 10. 测试策略

- 单元测试：minimax_client、chunker、subtitle_clean、score_candidates
- 集成测试：完整链路跑 1 个示例视频
- 验收测试：用 Agent 开发主题端到端生成报告
- 手动验证：候选页面预览、单视频卡片质量
- 端到端可视化：用 Playwright 截图首页与候选页

## 11. 交付物

```text
topic-research/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docs/
│   └── plans/
│       └── 2026-07-23-topic-learning-workflow-design.md
├── src/topic_research/
│   ├── cli.py
│   ├── topic_init.py
│   ├── search_bilibili.py
│   ├── score_candidates.py
│   ├── candidates_html.py
│   ├── selection_io.py
│   ├── subtitle_fetch.py
│   ├── subtitle_clean.py
│   ├── chunker.py
│   ├── minimax_client.py
│   ├── card_generator.py
│   ├── cross_synthesizer.py
│   ├── report_writer.py
│   └── state_store.py
└── tests/
    ├── test_minimax_client.py
    ├── test_chunker.py
    ├── test_subtitle_clean.py
    ├── test_score_candidates.py
    └── test_e2e_smoke.py
```

## 12. 安全注意事项

- MiniMax API Key 仅通过环境变量 `MINIMAX_API_KEY` 传入
- 仓库一律不上传 .env、candidates 选择 JSON、sources/、cards/ 等本地资料
- 仓库内任何位置出现形如 `sk-cp-...` 的字面量都视为安全事件，需先报告位置再处置