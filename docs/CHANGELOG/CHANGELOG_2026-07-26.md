# CHANGELOG — 2026-07-26

## 排查

### SESSDATA 过期导致 process 阶段"无字幕，跳过"

用户实测时浏览器点"立即开始处理"后，所有视频都跳过。
排查发现：

- `player/v2` 接口返回 `need_login_subtitle=true` + `subtitles=[]`
- `x/web-interface/nav` 返回 `isLogin: false, code: -101`
- `.env` 里的 `BILI_SESSDATA` 已过期（B站约 1 个月有效期）

### serve 进程持有过期 SESSDATA

**根因**：serve 后台进程（`task bykgza51i`）在 SESSDATA 过期前启动，
内存里持有的是过期值；用户更新 `.env` 后进程未重启，所以仍用旧值调 API。

**修复**：停掉旧 serve → 重启 → 新进程读到 `.env` 里的新 SESSDATA → 成功。

## 新增

### 尝试过的 CDP / 本地 cookie 自动提取（**未启用，留作备用**）

- [`topic-research/src/topic_research/cookie_extractor.py`](../topic-research/src/topic_research/cookie_extractor.py)
  - `extract_sessdata()`：从 Chrome / Edge 本地 cookie DB 读
  - `extract_sessdata_cdp()`：通过 CDP 从运行中的 Chrome 读
  - `extract_sessdata_from_clipboard()`：从 Windows 剪贴板读

### 为什么放弃自动提取

| 方案 | 失败原因 |
|---|---|
| 本地 cookie DB | Chrome 110+ 锁住 `Network/Cookies`，v20 App-Bound Encryption 必须 Chrome 进程上下文 |
| CDP | 需要 Chrome 加 `--remote-debugging-port=9222` flag，且 CLI 调 CDP 需用户反复授权 |
| 剪贴板 | 仍需手动从浏览器复制一次，节省有限 |

最终决定：保留 `.env` 手动粘贴方案，1 个月一次。
`cookie_extractor.py` 留作代码资产，未被 CLI 实际调用。

## 端到端跑通

| 指标 | 数值 |
|---|---|
| 候选数 | 86（"agent 开发"，5–40 min） |
| 字幕可用率 | 93% |
| process 成功 | 64 / 79（81%）|
| process 失败 | 15 / 79（其中 13 个之前已处理跳过，2 个真无字幕）|
| 真无字幕视频 | 2（B站后台数据缺失，不可恢复）|

## 已知遗留

- **SESSDATA 1 个月过期一次**：需用户手动重新粘贴到 `.env`
- **serve 进程持有过期 SESSDATA**：必须重启 serve 才能让配置变更生效
- **cookie_extractor.py 是死代码**：未来若启用自动提取再做集成
- **CDP 自动提取未启用**：浏览器安全模型限制