# topic-research project rules

> 本仓库围绕"主题学习研究工作流"展开：基于 B 站视频字幕自动生成主题学习资料。
> 主要交付物是 [`topic-research/`](topic-research/) 下的 Python CLI 工具，
> 设计文档见 [`docs/plans/2026-07-23-topic-learning-workflow-design.md`](docs/plans/2026-07-23-topic-learning-workflow-design.md)。

## Source of truth

- 当前架构与业务事实：优先阅读 `docs/specs/`，尤其是 `docs/specs/spec.md`。
- 单次任务统一使用 `docs/tasks/YYYY-MM-DD-topic.md`；同一天同类任务可使用 `YYYY-MM-DD-HHmm-topic.md`。
- 任务完成后的变更记录：`docs/CHANGELOG/CHANGELOG_YYYY-MM-DD.md`。
- 用户提供但暂不需要阅读的参考资料：`docs/references/`。
- 详细设计稿与实施记录在 `docs/plans/`（不要把日常任务混入 plans/，plans/ 只保留重大设计文档）。

## Project shape

- 这是一个**纯本地 CLI 工具**，不是 Web 服务：
  - 无后端进程、无数据库、无 Alembic 迁移
  - 无前端框架、无 dist 构建产物
  - 所有数据落盘到 `topic-research/topics/<slug>/` 下
  - 唯一的外部依赖是 LLM（MiniMax API）和 B 站公开接口
- 唯一入口：`python -m topic_research.cli {search,process,init}`。
- 主题数据是**个人研究资料**，默认不入库（已在 `.gitignore` 忽略 sources/、chunks/、cards/、selection.json、state.json、report.md、learning-path.md、search-gaps.md）。

## Before work

- 检查 cwd、Git 状态、工作区是否干净；当前目录默认不是 Git 仓库，需要时再 `git init`。
- 新需求先在 `docs/tasks/` 建立任务文件，记录需求、非目标、验收、风险、进度与遗留项。
- 涉及破坏性变更（重写 CLI 子命令、删除模块、改动 state.json schema、调整评分权重）先在 `docs/tasks/` 草拟方案，与用户对齐后再动手。
- 涉及网络协议（B 站 API 路径、MiniMax API 格式）的改动必须先确认当前端点可用，不要凭训练数据臆造。

## LLM provider

- 所有模型调用统一走 [`minimax_client.py`](topic-research/src/topic_research/minimax_client.py)，
  **不在业务代码里直连 `requests.post(api_url)`**。
- 切换模型仅改 `MINIMAX_MODEL` 环境变量；切换 endpoint 仅改 `MINIMAX_API_URL`。
- 重试、指数退避、JSON 解析容错、用量统计都由 client 负责，业务模块不重复实现。

## Secrets

- **API Key 只通过环境变量 `MINIMAX_API_KEY` 或本地 `.env` 传入**；缺失即报错退出，绝不写入源码、测试夹具或日志。
- `.env` 已在 `.gitignore` 中；任何对 `.env.example` 的修改必须保持 key 占位符为 `your-minimax-key-here`。
- 仓库内任何位置出现形如 `sk-cp-...` 的字面量都视为安全事件，先报告位置再处置，禁止复制、提交或贴回聊天。

## Encoding and platforms

- 源码与 Markdown 全部 UTF-8；禁止无意 BOM。
- 中文写入优先用 Python 写入；通过 Windows cmd/Git Bash 管道写入中文时，先用 `python -X utf8 ...` 验证解码。
- 兼容 Windows 开发与 Linux 生产：
  - 路径用 `pathlib.Path` 处理，避免硬编码 `\` 或 `/`
  - 不依赖 `bash` 才有的命令；测试覆盖 `pytest`，CI 友好
  - Windows 控制台默认 GBK，错误消息尽量使用 ASCII，避免出现 `UnicodeEncodeError`

## Frontend done（仅指本地 HTML）

- 候选页是纯静态 `candidates.html`，用 Playwright 验证：
  - 渲染无错、勾选按钮有效、selection.json 导出格式正确
  - 截图归档到 `topics/<slug>/screenshots/`
- E2E 用隔离的 fixture 数据（参见 [`examples/generate_demo_html.py`](topic-research/examples/generate_demo_html.py)），不要污染真实主题目录。

## Tests

- 测试集中在 `topic-research/tests/`，覆盖：chunker、subtitle_clean、score_candidates、minimax_client JSON 解析、e2e_smoke（topic_init + html + selection_io + state_store）。
- 修改业务逻辑后必须 `python -m pytest topic-research/tests/` 全绿再交付。
- 不要为了"全绿"删测试；旧契约废弃时用新测试覆盖。

## Data verification

- 主题数据写在 `topic-research/topics/<slug>/`，由 `state.json` 维护断点续跑状态：
  - 每个视频有 `selection_state / fetch_state / card_state` 三态
  - 失败要记录 `error` 字段，不让单个视频卡死整批
- 跨视频汇总 `report.md` 可重跑；卡片 `cards/<bvid>.md` 是稳定的源材料，重跑汇总时优先复用。
- 数据同步（搜索抓取、字幕下载、模型调用）必须记录起止时间、候选数、成功数、失败数、token 用量。

## Cleanup and Git

- `tmp/`、截图、缓存、本地主题目录中的 `screenshots/` 仅在确认无引用价值后清理。
- 不要删除 `topic-research/tests/`、`topic-research/src/topic_research/` 中的任何模块，除非已被新模块完整替代。
- 不在仓库根长期保留 `task_plan.md`、`progress.md`、`findings.md` 等工具草稿；有效内容合并到 `docs/tasks/` 后清理。
- 完成定义：代码 + 测试 + Playwright 截图（如有 UI 改动）+ `state.json` 兼容性确认 + 文档（spec/tasks/CHANGELOG）+ 清理。
- 完成并确认无误后可以 commit；未经用户明确要求不得 push 或部署。

## Network caveats

- 本机直连 `*.bilibili.com` 不可达时，不要假装可用，必须显式提示用户并提供离线路径：
  - `examples/generate_demo_html.py` 提供本地示例候选
  - 用户也可以用现有油猴脚本下载字幕后直接进入 process 阶段
- 不要为了"看起来工作"就在搜索失败时静默返回空结果；失败要写日志、写 state.json。