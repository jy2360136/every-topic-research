# CHANGELOG — 2026-07-23

## SESSDATA 修复（2026-07-23 深夜）

**根因**：B 站 `player/v2` 接口对未登录请求返回 `need_login_subtitle=true` + 空 `subtitles` 列表。油猴脚本在登录浏览器里能拿到字幕是因为它有 `SESSDATA` cookie；CLI 用裸 `requests` 没带过登录态。

**修复**：
- 新增 [`topic-research/src/topic_research/bili_session.py`](../topic-research/src/topic_research/bili_session.py)：所有 B 站请求统一通过 `build_session()`，自动从 `BILI_SESSDATA` 环境变量读 SESSDATA 并设为 `.bilibili.com` cookie
- [search_bilibili.py](../topic-research/src/topic_research/search_bilibili.py) 和 [subtitle_fetch.py](../topic-research/src/topic_research/subtitle_fetch.py) 改走 `build_session`
- `config.py` / `.env` / `.env.example` 增加 `BILI_SESSDATA` 配置项
- 新增 [tests/test_bili_session.py](../topic-research/tests/test_bili_session.py)：3 个用例覆盖有/无/已有 cookie 三种情况

**附带修复**（同一调试过程中发现）：
- B 站 `duration` 字段是 `"mm:ss"` 字符串（如 `"1353:6"`），原代码 `_coerce_int` 直接当 0 处理 → 5–40 min 时长过滤完全失效。新增 `_parse_duration()` 解析 mm:ss / h:mm:ss / 纯秒数 / 数字字符串
- B 站 all/v2 接口 `data.result` 实际是 list（每项 `result_type` + `data`），不是 nested dict。原代码 `data.result.video` 报 `'list' object has no attribute 'get'`
- `search_videos` 用 `max_results` 提前 break 导致多排序合并时每路只拉 1 页；改为 `combine_sorts=True` 时每路放大到 3 倍

**效果**（同一关键词 "agent 开发"）：
| 指标 | 修复前 | 修复后 |
|---|---|---|
| 候选数 | 19 | 74 |
| 官方字幕 | 0 | 49 |
| 自动字幕 | 0 | 19 |
| 无字幕 | 19 (100%) | 6 (8%) |
| 5–40 min 过滤 | 失效（全 duration=0）| 生效 |
| 多排序合并 | 未启用 | 默认 totalrank+click+pubdate 三路去重 |

**SESSDATA 取用**：浏览器登录 B 站 → F12 → Application → Storage → Cookies → `https://www.bilibili.com` → 找 `SESSDATA` 行复制 Value（SESSDATA 是 HttpOnly，JavaScript 读不到）。也可以 Network → 任意 api.bilibili.com 请求 → Request Headers → Cookie 字段。

## 文档清理（2026-07-23 晚）

- 用户确认已在 MiniMax 控制台 rotate 旧 Key，移除以下文档中关于 "Key 泄漏需要 rotate" 的风险描述：
  - `README.md`、`AGENTS.md`：删除 `job_matcher.py` 泄漏 Key 的相关条目
  - `docs/specs/spec.md`、`docs/plans/2026-07-23-topic-learning-workflow-design.md`：改为通用安全规则（保留 `sk-cp-...` 字面量告警）
  - `docs/tasks/2026-07-23-topic-learning-workflow.md`：移除"安全风险"项和"并行 rotate"提示
  - `docs/CHANGELOG/CHANGELOG_2026-07-23.md`（本文件）：将"已知遗留"改为 rotate 已完成
- 通用安全规则（API Key 仅从 `.env` / 环境变量读、`.env` 入 `.gitignore`、禁明文 Key 入库）保持不变

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
- 历史 MiniMax Key 已在 MiniMax 控制台完成 rotate，本工具不复用旧 Key
- 第一版评分权重为硬编码，未来应改为可配置
- `subtitle_fetch` 没有瞬时 5xx 重试
- 没有跨平台 CI（仅在 Windows 11 验证）