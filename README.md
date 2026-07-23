# every-topic-research

> 把 B 站视频字幕自动整理为主题学习资料的本地 Python CLI 工具。

## 快速开始

工具代码在 [`topic-research/`](topic-research/)，完整说明见
[`topic-research/README.md`](topic-research/README.md) 和
[`docs/specs/spec.md`](docs/specs/spec.md)。

```bash
cd topic-research
python -m pip install -e .
cp .env.example .env       # 填入 MINIMAX_API_KEY
python -m topic_research.cli search --topic "agent 开发"
# 浏览器打开 topics/<slug>/candidates.html，勾选后导出 selection.json
python -m topic_research.cli process --slug agent-development
```

## 目录结构

```text
.
├── AGENTS.md                                # 项目规则
├── docs/
│   ├── specs/spec.md                        # 当前架构与业务事实
│   ├── plans/2026-07-23-...                 # 设计文档
│   ├── tasks/2026-07-23-...                 # 任务记录
│   └── CHANGELOG/CHANGELOG_2026-07-23.md
└── topic-research/
    ├── README.md                            # 工具使用说明
    ├── pyproject.toml
    ├── src/topic_research/                  # 13 个核心模块
    ├── tests/                               # 18 个测试全绿
    ├── examples/                            # 离线演示
    └── topics/agent-development/            # 示例主题（演示用）
```

## 安全提示

- API Key **仅通过 `MINIMAX_API_KEY` 环境变量或 `.env` 传入**；绝不入源码、不入聊天记录
- `.gitignore` 已排除 `.env`、油猴脚本副本、所有主题数据