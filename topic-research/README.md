# 主题学习研究工作流 (Topic Research)

从 B 站视频字幕自动生成主题学习资料的命令行工具。

## 工作流概览

```text
1. 搜索主题 → 生成 candidates.html
2. 浏览器中勾选想要研究的视频 → 导出 selection.json
3. 下载字幕 → 调用 MiniMax 生成单视频知识卡片 → 跨视频汇总
```

## 安装

```bash
cd topic-research
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS / Linux
pip install -e .
```

复制环境变量模板并填入 MiniMax API Key：

```bash
cp .env.example .env
# 编辑 .env，把 MINIMAX_API_KEY 替换为你的 key
```

## 使用

### 第一步：搜索候选

```bash
python -m topic_research.cli search --topic "agent 开发" --slug agent-development
```

执行后会在 `topics/agent-development/` 下生成：

- `candidates/<bvid>.json`：每个视频的元数据 + 评分
- `candidates.html`：浏览器打开这个文件
- `state.json`：断点续跑状态

### 第二步：勾选视频

打开 `topics/agent-development/candidates.html`，勾选视频 → 点击 "导出勾选 selection.json" → 把 `selection.json` 放回 `topics/agent-development/` 目录。

页面会用颜色提示字幕状态：

- 🟢 官方字幕：质量最好
- 🟡 自动字幕：可能有错别字，仍可使用
- 🔴 无字幕：会被跳过（请勿勾选）

### 第三步：处理

```bash
python -m topic_research.cli process --slug agent-development
```

执行后会生成：

- `sources/<bvid>.txt`：原始字幕
- `cards/<bvid>.md`：单视频知识卡片
- `report.md`：跨视频综合报告
- `learning-path.md`：推荐学习路线
- `search-gaps.md`：知识缺口与下一步关键词

## 设计文档

见 `docs/plans/2026-07-23-topic-learning-workflow-design.md`。

## 安全

- API Key 仅通过 `MINIMAX_API_KEY` 环境变量传入，缺失即报错退出
- 仓库 `.gitignore` 已忽略 `.env`、`topics/*/sources/`、`topics/*/cards/`、`topics/*/selection.json` 等本地资料
- 历史脚本 `job_matcher.py` 中暴露过的 Key 应尽快在 MiniMax 控制台轮换，不应在本工具复用

## 已知限制（第一版）

- 仅支持 B站；YouTube 待后续扩展
- 不做 ASR；没有官方/自动字幕的视频会被跳过
- 评分权重为初版，可根据实际效果调整
- 单视频卡片为 Markdown，尚未接入向量库