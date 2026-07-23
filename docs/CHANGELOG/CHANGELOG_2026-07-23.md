# CHANGELOG — 2026-07-23

## 新增

### 项目骨架
- 新建 `topic-research/` 子项目（Python CLI 工具）
- `pyproject.toml`：声明 `topic_research` 包及依赖（requests / bilibili-api-python / python-dotenv / pyyaml / rich / jinja2 / tenacity）
- `.env.example`：MINIMAX_API_KEY / MINIMAX_API_URL / MINIMAX_MODEL / BILI_CANDIDATE_LIMIT / TOPIC_CONCURRENCY
- `.gitignore`：忽略 `.env`、`topics/*/sources/`、`topics/*/chunks/`、`topics/*/cards/`、`topics/*/candidates/`、`topics/*/selection.json`、`topics/*/state.json`、`topics/*/logs/`、`topics/*/report.md` 等本地数据
- `README.md`：三步使用说明 + 安全提示 + 已知限制

### 核心模块（topic-research/src/topic_research/）
- `config.py`：环境变量加载 + API Key 校验
- `minimax_client.py`：MiniMax API 客户端，含指数退避重试、JSON 容错解析、用量统计、`generate_text` / `generate_json`
- `prompts.py`：集中管理单视频卡片 / 跨视频汇总的 Prompt
- `topic_init.py`：创建主题目录结构、写 topic.yaml
- `state_store.py`：state.json 读写、断点续跑
- `search_bilibili.py`：B 站搜索 + 详情 + 元数据采集 + 字幕类型探测
- `search_bing_bilibili.py`：Bing 兜底（用于无法直连 api.bilibili.com 的环境）
- `score_candidates.py`：综合评分 7 维权重公式
- `candidates_html.py`：渲染 candidates.html（封面 / 评分 / 字幕状态 / 勾选按钮）
- `selection_io.py`：读取 selection.json 并过滤无字幕视频
- `subtitle_fetch.py`：下载 B 站字幕（官方 / 自动）
- `subtitle_clean.py`：BBCode 剥离、标点规范化、短句合并、保留时间戳段落
- `chunker.py`：段落切块 + token 估算
- `card_generator.py`：分块 → 局部摘要 → 最终单视频卡片
- `cross_synthesizer.py`：跨视频汇总
- `report_writer.py`：从 report.md 拆出 learning-path.md / search-gaps.md
- `cli.py`：argparse 入口，3 子命令 search / process / init

### 测试（topic-research/tests/）
- 18 个测试全部通过：`test_chunker` (3) / `test_subtitle_clean` (3) / `test_score_candidates` (5) / `test_minimax_client` (3) / `test_e2e_smoke` (4)

### 演示与验证
- `examples/generate_demo_html.py`：生成 6 个示例候选（3 官方 / 2 自动 / 1 无字幕）
- `examples/screenshot_demo.py`：Playwright 截图脚本
- 截图 3 张：`screenshots/01_initial.png`、`screenshots/02_top_selected.png`、`screenshots/03_official_only.png`

### 文档
- `docs/plans/2026-07-23-topic-learning-workflow-design.md`：完整设计文档
- `docs/specs/spec.md`：当前架构与业务事实
- `docs/tasks/2026-07-23-topic-learning-workflow.md`：本次任务记录
- `docs/CHANGELOG/CHANGELOG_2026-07-23.md`：本文件
- `AGENTS.md`：从 jy_chan 项目规则改写为 topic-research 项目规则

## 修改

- `AGENTS.md`：从 jy_chan 的数据库/Alembic 规则改写为 topic-research 的 CLI 工具规则

## 验证

- `python -m pip install -e .` → 成功
- `python -m pytest topic-research/tests/` → **18 passed in 0.54s**
- `python -m topic_research.cli init --topic "test"` → 创建主题目录
- `python -m topic_research.cli search ...` → 在缺 Key 时给出友好错误
- Playwright 截图 → UI 三种状态均正确切换

## 已知遗留

- **本机无法直连 `*.bilibili.com`**（SSL 握手失败 exit 35），端到端搜索/字幕下载流程尚未在本机跑通
- 旧 `job_matcher.py:15` 中的 MiniMax Key 已明文暴露在多个位置（源码 + 聊天记录），建议立即 rotate；本工具不会复用该 Key
- 第一版评分权重为硬编码，未来应改为可配置
- `subtitle_fetch` 没有瞬时 5xx 重试
- 没有跨平台 CI（仅在 Windows 11 验证）