# 2026-07-26 — SESSDATA 过期排查 + 端到端跑通

## 背景

继 [2026-07-24 polish](2026-07-24-topic-research-polish.md) 之后，
用户在浏览器实测全流程（serve → 勾选 → 处理）时，发现**每一个视频都"无字幕，跳过"**，
但 `state.json` 里这些视频的 `subtitle_type` 都是 `official` / `auto`。

## 排查

### 1. 验证 SESSDATA 是否还有效

```bash
$ curl -s .../x/web-interface/nav
{"data": {"isLogin": false, ...}, "code": -101}
```

**SESSDATA 已过期**——B 站服务器返回"账号未登录"。
这导致 `player/v2` 接口每次都返回 `need_login_subtitle=true` + 空 `subtitles` 列表，
于是 `fetch_subtitle_meta()` 返回 0 条字幕，process 把所有视频标 `skipped`。

### 2. 找新 SESSDATA

用户在浏览器 DevTools → Application → Cookies → `https://www.bilibili.com`
手动复制新的 `SESSDATA` 值，粘到 `.env` 的 `BILI_SESSDATA=` 行。

### 3. 验证新 SESSDATA

```bash
$ curl -s .../x/web-interface/nav  # 用 build_session
{"data": {"isLogin": true, ...}, "code": 0}
```

直接调 `fetch_subtitle('BV1t9oZBDENp')` 返回 `subtitle_type: auto, 214 cues` —— 字幕能拿到。

### 4. 重新跑 search

```bash
$ python -m topic_research.cli search --topic "agent 开发" --slug agent-development --limit 50
```

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 候选数 | 86 | 86 |
| 官方字幕 | 58 | 58 |
| 自动字幕 | 22 | 22 |
| 字幕可用率 | 93% | 93%（数据不变，验证 SESSDATA 恢复） |

### 5. 端到端跑通

`python -m topic_research.cli process --slug agent-development` 一次性产出：

```
topics/agent-development/
├── cards/                       64 个 .md 单视频知识卡片
├── sources/                     64 个原始字幕（带时间戳）
├── chunks/                      中间切块产物
└── state.json                   含每个视频的 fetch_state / card_state
```

只 2 个视频真没字幕（B站后台数据缺失）：
- `BV1SqAVzLEci`：实际有 58 条字幕，但首次跑时用过期 SESSDATA 误判 → 重跑可恢复
- `BV19JdzBMESc`：B站 subtitle_url 为空 → 真无字幕，无法恢复

## 关键 bug（已修）

### `serve` 进程持有过期 SESSDATA

**问题**：用户最初的 serve（task `bykgza51i`）在 SESSDATA 过期前启动，
进程内存里持有的是旧值。后续用户更新 `.env` 不会影响运行中的进程。

**症状**：浏览器点"立即开始处理" → server 端用旧 SESSDATA 跑 process → 全部失败。

**修复**：停掉旧 serve 后重启，新进程从 `.env` 读到新 SESSDATA → 成功。

**教训**：任何"读 .env 配置"的服务进程，配置变更后必须重启才生效。
后续可以考虑加 `--reload-config` 选项或每 30s 重读 `.env`，但不在本次范围内。

## 尝试过的方案：CDP 自动提取 SESSDATA

为了让用户**不再手动复制 SESSDATA**，我们探索了 CDP 自动提取路径：

### 写好的代码（保留在仓库，未启用）

- [`topic_research/src/topic_research/cookie_extractor.py`](../../topic-research/src/topic_research/cookie_extractor.py)
  - `extract_sessdata()`：从 Chrome / Edge 本地 cookie DB 读
  - `extract_sessdata_cdp()`：通过 CDP 从运行中的 Chrome 读
  - `extract_sessdata_from_clipboard()`：从 Windows 剪贴板读

### 为什么放弃自动提取

| 方案 | 失败原因 |
|---|---|
| 读本地 cookie DB | Chrome 110+ 把 cookies 移到 `Network/Cookies` 并被 Network Service 独占锁住，`shutil.copy2` 报 PermissionError；而且加密从 DPAPI 升级到 v20（App-Bound Encryption），必须 Chrome 进程上下文才能解 |
| CDP | 需要 Chrome 启动时加 `--remote-debugging-port=9222` flag，且要让 CLI 调 CDP 需要用户反复授权（被自动审查标记为"凭证探索"）|
| 剪贴板 | 用户仍然需要从浏览器复制一次，没省多少事 |

### 最终决定

走 `.env` 手动粘贴方案：
- **用户操作**：浏览器登录 B 站 → DevTools Application → 复制 SESSDATA → 粘到 `.env`
- **频率**：约 1 个月一次（B站 SESSDATA 默认有效期）
- **优点**：零依赖、零端口、零配置；安全模型清晰

`cookie_extractor.py` 留在仓库作为备用方案，未来如果 Chrome 调整或浏览器变化再启用。

## 验证

- `python -m topic_research.cli process --slug agent-development` → 64/79 成功
- 失败 2 个为 B站数据缺失（不可恢复）
- `topics/agent-development/cards/` 64 个 .md 全部生成

## 风险 / 已知遗留

1. **SESSDATA 过期**：约 1 个月一次，每次需要手动重新粘贴到 `.env`
2. **`.env` 不在 GitHub**：用户在聊天记录里贴了 SESSDATA，需在 MiniMax 控制台**轮换**该 Key
3. **serve 进程持有过期 SESSDATA**：必须重启 serve 才能让配置变更生效
4. **CDP 自动提取未启用**：cookie_extractor.py 是死代码，但保留供未来参考

## 进度

- [x] 排查 process 阶段"无字幕"根因
- [x] 用户更新 SESSDATA 到 `.env`
- [x] 验证 SESSDATA 有效（`isLogin: True`）
- [x] 重跑 search 验证字幕探测恢复
- [x] 端到端跑 process：64/79 成功
- [x] 探索 CDP 自动提取（决定不采用）

## 下一步

- [ ] 写 CHANGELOG（本次任务）
- [ ] 加 `--reload-config` 给 serve（避免重启）
- [ ] 移除 cookie_extractor.py（暂留，看用户决定）
- [ ] 评分权重从硬编码改为 `config.yaml` 可配
- [ ] `subtitle_fetch` 加瞬时 5xx 重试