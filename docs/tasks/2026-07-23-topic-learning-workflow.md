# 2026-07-23 — 主题学习研究工作流 (topic-research) MVP

## 需求

用户希望把"在 B 站搜索关键词 → 用油猴脚本提取字幕 → 喂给 MiniMax 总结"形成一套**完整、可复用、可迭代**的工作流，避免每次手动重复操作。

## 非目标

- 第一版不做 YouTube
- 第一版不做 ASR（没有官方/自动字幕的视频跳过）
- 第一版不做 RAG 向量库 / 知识库
- 第一版不做 Web 服务

## 验收

- ✅ 设计文档已写入 [`docs/plans/2026-07-23-topic-learning-workflow-design.md`](../plans/2026-07-23-topic-learning-workflow-design.md)
- ✅ 完整代码 13 个模块 + 测试 18 个全部通过
- ✅ CLI 三子命令：search / process / init
- ✅ 候选 HTML 在浏览器可勾选并导出 selection.json
- ✅ Playwright 截图 3 张（initial / top_selected / official_only）证明 UI 工作
- ✅ MiniMax API Key 只从环境变量 / .env 读取，缺失即报错退出
- ⚠️ 端到端流程在本机尚未跑通：B 站域名不可达，Bing 兜底无结果

## 风险

- **网络层风险**：当前 Windows 11 机器无法直连 `*.bilibili.com`（SSL 握手失败 exit 35）。
  - 影响：自动搜索 / 字幕下载均不可用
  - 缓解：
    - 提供 `examples/generate_demo_html.py` 离线演示 UI
    - 提供 Bing 兜底（`--use-bing`）
    - 用户可绕过 search 阶段，直接用油猴脚本喂字幕到 sources/ 后跑 process
- **API 兼容性风险**：B 站 `player/v2` 接口可能反爬升级；当前实现只取字幕列表最小化请求。

## 进度

- [x] 调研 GitHub 同类项目（BibiGPT-v1 / lycohana/BiliSum / jackwener/bilibili-summary / yupi-hot-monitor / free-video-downloader）
- [x] 写设计文档
- [x] 创建项目骨架（pyproject / .env.example / .gitignore / README）
- [x] 实现 minimax_client / topic_init / state_store / prompts
- [x] 实现 search_bilibili / score_candidates
- [x] 实现 candidates_html / selection_io
- [x] 实现 subtitle_fetch / subtitle_clean / chunker
- [x] 实现 card_generator / cross_synthesizer / report_writer
- [x] 编写 cli.py（search / process / init）
- [x] 编写 18 个测试，全绿
- [x] 调试：`test_clean_text` 时间戳剥离不在单元测试范围；`require_api_key` 改为 ASCII 提示避免 GBK 报错
- [x] 生成演示候选页（6 个示例视频，含 3 官方 / 2 自动 / 1 无字幕）
- [x] Playwright 截图 3 张
- [x] 重写 AGENTS.md
- [x] 创建 docs/specs/spec.md
- [x] 创建 docs/tasks/ 本任务记录
- [x] 创建 docs/CHANGELOG/CHANGELOG_2026-07-23.md
- [ ] （遗留）端到端跑通：需先解决 B 站网络可达性，或改走"用户喂字幕"路径

## 遗留问题

1. **B 站网络不可达**：详见上面的风险。建议优先级最高的待办：
   - 在用户机器上确认是否需要走代理
   - 或新增 `import` 子命令，支持用户把油猴脚本下载的字幕直接喂入 process 阶段
2. **评分公式权重待调优**：第一版写死后只能改代码；建议加 `config.yaml` 读取评分权重。
3. **字幕下载失败重试**：当前 `subtitle_fetch` 没有重试逻辑；遇到瞬时 5xx 会直接失败。
4. **没有 e2e 跑 MiniMax**：受限于 B 站域名不可达，process 阶段尚未真实运行。
5. **没有跨平台 CI**：pytest 已在 Windows 通过，但 Linux 路径/换行还需在 CI 验证。

## 下一步

等待用户决定：

- A. 解决网络问题 → 走完整 search + process 流程
- B. 加 `import` 子命令 → 用户用油猴脚本喂字幕 → 跑 process
- C. 调整 UI / 评分权重 → 等用户看完演示页后反馈