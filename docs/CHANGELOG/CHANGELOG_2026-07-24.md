# CHANGELOG — 2026-07-24

## 新增

### 字幕探测登录态支持

- 新增 [`topic-research/src/topic_research/bili_session.py`](../topic-research/src/topic_research/bili_session.py)
  - 统一 B 站请求 Session 工厂 `build_session()`
  - 从 `BILI_SESSDATA` 环境变量读 SESSDATA 并自动设为 `.bilibili.com` cookie
  - 已有 session 不被清空（保留其他 cookie）
- `config.py` 新增 `BILI_SESSDATA` 配置项
- `.env` / `.env.example` 新增 `BILI_SESSDATA=your-sessdata-here` 占位
- `search_bilibili.py` 和 `subtitle_fetch.py` 改走 `build_session`，去掉本地 `HEADERS` 重复定义

### CLI 一键流程 `run` 子命令

- 新增 `python -m topic_research.cli run --slug <slug>`
- 行为：先在主题目录找 `selection.json`，没有就在
  `~/Downloads/` / `~/下载/` / `~/Desktop/` 下找 `<slug>-selection.json` 或
  `selection.json`，找到后复制到主题目录，立即跑 `process` 全流程
- 找不到时给出明确的三层查找路径提示

### 5–40 分钟时长过滤 + 多排序合并

- `search_bilibili.collect()` 新增 `min_duration` (默认 300s) /
  `max_duration` (默认 2400s) / `combine_sorts` (默认 True) 三个参数
- `combine_sorts=True` 时同时跑 `totalrank` / `click` / `pubdate` 三路
  B 站搜索并按 BVID 去重
- 每路 `max_results` 放大到 3 倍以覆盖多页（之前 50/路 → 现在 150/路）
- CLI 新增 `--min-duration` / `--max-duration` 选项，绑到 config

### 测试

- 新增 [tests/test_bili_session.py](../topic-research/tests/test_bili_session.py)
  - 3 个用例：有/无 SESSDATA / 已有其他 cookie 的情况
- 新增 [tests/test_search_bilibili.py](../topic-research/tests/test_search_bilibili.py)
  - 6 个 `_parse_duration` 用例（mm:ss / h:mm:ss / 纯秒 / 字符串数字 / 空 / 异常）
  - 1 个 `_normalize` 用例覆盖扁平字段

## 修改

### B 站 all/v2 接口响应适配

`search_bilibili.search_videos` 和 `_normalize` 重写：
- `data.result` 是 list，每项形如 `{"result_type": "video", "data": [video_dict, ...]}`
- 视频字段是扁平的（`play` / `like` / `favorites` / `review` / `danmaku`），
  旧版 `stat` 嵌套字段作为 fallback
- `duration` 字段是 `"mm:ss"` 字符串（如 `"1353:6"` = 22.5 小时），新增
  `_parse_duration()` 解析 mm:ss / h:mm:ss / 纯秒数 / 数字字符串

### HTML 导出升级

`candidates_html.HTML_TEMPLATE` 里 `exportSelection()` 函数：
- 优先用 File System Access API（`window.showSaveFilePicker`，Chrome/Edge 84+）
  弹"另存为"对话框，文件名预填 `<slug>-selection.json`
- 老浏览器兜底用 `a.download`，文件落默认下载目录
- 提示信息更新为引导用户跑 `run` 子命令

### 文档清理

按"已 rotate 旧 Key"的状态，删除 `job_matcher.py` 泄漏相关条目（保留通用安全规则）：
- `README.md`、`AGENTS.md`
- `docs/specs/spec.md`、`docs/plans/2026-07-23-topic-learning-workflow-design.md`
- `docs/tasks/2026-07-23-topic-learning-workflow.md`
- `docs/CHANGELOG/CHANGELOG_2026-07-23.md`（追加"文档清理"小节）
- 通用规则（API Key 仅从 `.env` / 环境变量读、`.env` 入 `.gitignore`、
  禁明文 Key 入库）保持不变

## 验证

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 候选数（"agent 开发"，5–40 min） | 19 | 74 |
| 官方字幕 | 0 | 49 |
| 自动字幕 | 0 | 19 |
| 无字幕 | 19 (100%) | 6 (8%) |
| 测试数量 | 18 | 28 |
| 端到端可用 | ❌ | ✅ |

- `python -m pytest topic-research/tests/` → **28 passed**
- `python -m topic_research.cli search --topic "agent 开发" --slug agent-development --limit 50`
  → 成功，74 个候选，state.json `last_stage=search_done`
- 模拟浏览器下载 `selection.json` 到 `~/Downloads/`，跑
  `python -m topic_research.cli run --slug agent-development`
  → 自动复制到主题目录 → 字幕下载 → MiniMax 单视频卡片 → 跨视频汇总 →
  `report.md` / `learning-path.md` / `search-gaps.md` 全部生成
- MiniMax 用量：853 input tokens / 789 output tokens

## 已知遗留

- SESSDATA 过期后需要重新从浏览器复制（不影响其他代码路径）
- 评分权重仍为硬编码，未来应改为 `config.yaml` 可配
- `subtitle_fetch` 仍无瞬时 5xx 重试
- 仅在 Windows 11 + Python 3.11 上验证，未跑 Linux/macOS CI
