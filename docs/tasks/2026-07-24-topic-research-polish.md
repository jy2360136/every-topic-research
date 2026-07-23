# 2026-07-24 — topic-research 实战调优（字幕探测 + 一键流程）

## 背景

继 [2026-07-23 MVP](2026-07-23-topic-learning-workflow.md) 之后，用户在真实环境跑通端到端时
发现两个严重影响可用性的问题：

1. **字幕探测 100% 返回 none** —— 19 个候选视频全部标 `subtitle_type=none`，但用户用油猴脚本实测
   这些视频都有字幕。导致 `process` 阶段全跳过，无法生成任何 `cards/<bvid>.md`。
2. **HTML → JSON → process 流程割裂** —— 用户勾完视频导出 `selection.json` 后，需要手动从
   浏览器下载目录复制到项目主题目录。流程上需要两个手动步骤。

附带还发现 3 个隐藏 Bug：

- B 站搜索结果 `duration` 字段是 `"mm:ss"` 字符串（如 `"1353:6"`），原 `_coerce_int` 直接当 0
  处理，导致 5–40 分钟时长过滤完全失效。
- `data.result.video` 实际是 list（不是 nested dict），旧代码报
  `'list' object has no attribute 'get'`。
- `max_results` 在每路搜索时提前 break，多排序合并时每路只拉到 1 页（50 条），B 站实际
  5 页 × 50 条 = 250 条没拉完。

## 任务

### 1. 字幕探测修复（核心）

**根因**：B 站 `player/v2` 接口对未登录请求返回
```json
{ "need_login_subtitle": true, "subtitles": [] }
```
油猴脚本在登录浏览器里有 `SESSDATA` cookie 能拿到字幕；CLI 裸 `requests` 拿不到。

**修复**：
- 新增 [`topic_research/bili_session.py`](../../topic-research/src/topic_research/bili_session.py)：
  所有 B 站请求统一通过 `build_session()`，从 `BILI_SESSDATA` 环境变量读 SESSDATA，
  自动设为 `.bilibili.com` cookie
- [search_bilibili.py](../../topic-research/src/topic_research/search_bilibili.py) 和
  [subtitle_fetch.py](../../topic-research/src/topic_research/subtitle_fetch.py) 改走 `build_session`
- `config.py` / `.env` / `.env.example` 增加 `BILI_SESSDATA` 配置项
- 新增 [test_bili_session.py](../../topic-research/tests/test_bili_session.py)：3 个用例

### 2. duration 解析修复

新增 `_parse_duration()`，兼容 `"mm:ss"` / `"h:mm:ss"` / 纯秒数 / 数字字符串。
[search_bilibili.py](../../topic-research/src/topic_research/search_bilibili.py) `_normalize` 改用。

### 3. B 站 API 响应结构适配

all/v2 接口 `data.result` 是 list（每项 `result_type` + `data`），新代码遍历该 list 筛选
`result_type == 'video'` 段。同时适配扁平字段（`play` / `favorites` / `review` /
`danmaku`），旧版嵌套 `stat` 字段作为 fallback。

### 4. 多排序合并 + 5–40 min 过滤

- `collect()` 新增 `min_duration` / `max_duration` / `combine_sorts` 参数
- `combine_sorts=True` 时同时跑 `totalrank` / `click` / `pubdate` 三路搜索并去重
- 每路 `max_results` 放大到 3 倍以覆盖多页结果
- 5–40 min 时长过滤为 B 站"高质量有字幕"视频的经验区间（避开切片混剪和几百集大教程）

### 5. CLI 一键流程 `run`

新增 `run` 子命令：
```bash
python -m topic_research.cli run --slug agent-development
```
行为：
1. 检查 `topics/<slug>/selection.json` 是否存在
2. 不存在则查找 `~/Downloads/`、`~/下载/`、`~/Desktop/` 下的 `<slug>-selection.json` 或
   `selection.json`
3. 找到后复制到主题目录
4. 立即调用 `process` 全流程

### 6. HTML 导出升级

[candidates_html.py](../../topic-research/src/topic_research/candidates_html.py) `exportSelection`
优先用 File System Access API（Chrome/Edge 84+），弹"另存为"对话框，文件名预填
`<slug>-selection.json`。老浏览器兜底用 `a.download` 落默认下载目录。

## 验证

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 候选数（"agent 开发"，5–40 min） | 19 | **74** |
| 官方字幕 | 0 | **49** |
| 自动字幕 | 0 | **19** |
| 无字幕 | 19 (100%) | 6 (8%) |
| 字幕可用率 | 0% | **92%** |
| duration 过滤 | 失效（全 duration=0）| 生效 |
| 多排序合并 | 未启用 | 默认三路去重 |
| HTML→process 手动步骤 | 导出 + 移动 + 命令（3 步）| 导出 + `run`（2 步）|

### 测试

- 28 个测试全绿（25 旧 + 3 新 `test_bili_session`）
- 7 个新测试覆盖 `_parse_duration` 和 `_normalize`（test_search_bilibili.py）
- 端到端实测：search → 模拟浏览器下载 selection.json → `run` → process → 真实产出
  `sources/<bvid>.txt` / `cards/<bvid>.md` / `report.md` / `learning-path.md` /
  `search-gaps.md`，MiniMax 用量 853 input / 789 output tokens

## 风险

- **SESSDATA 过期**：B 站 SESSDATA 默认 ~1 个月有效，过期需要重新从浏览器复制。
  工具不持久化、过期也只是搜索/字幕探测失败，不会影响 `process` 之外的代码路径。
- **运行时 5–40 min 假设**：此区间基于"用户反馈"的经验值，对窄主题（如
  "agent 开发"）只能拿到 ~20 个；宽主题可拿到 30+。未来可考虑把区间提到
  `config.yaml` 而非 CLI flag。
- **File System Access API 兼容性**：仅 Chrome/Edge 84+ 支持，Firefox/Safari
  走 `a.download` 兜底。Firefox 用户仍需要 `run` 子命令的下载目录归位能力。

## 进度

- [x] 排查字幕探测为 none 的根因
- [x] 新增 `bili_session.py` + `BILI_SESSDATA` 配置
- [x] 改 `search_bilibili.py` / `subtitle_fetch.py` 走 `build_session`
- [x] `_parse_duration` 修复 mm:ss 字符串解析
- [x] 适配 all/v2 接口新结构（list + 扁平字段）
- [x] `collect()` 多排序合并 + 时长过滤
- [x] CLI 新增 `run` 子命令
- [x] HTML `exportSelection` 升级到 File System Access API
- [x] 新增 / 更新 11 个测试
- [x] 端到端实测 search → run → 报告生成

## 下一步

- 把评分权重从硬编码改为 `config.yaml` 可配
- `subtitle_fetch` 加瞬时 5xx 重试
- 加 `import` 子命令（用户喂油猴脚本下载的字幕直接进 process）
- Linux/macOS CI 验证
