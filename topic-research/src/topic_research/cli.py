"""CLI 主入口

典型用法：
    # 第一次：搜索 + 生成候选页
    python -m topic_research.cli search --topic "agent 开发" --slug agent-development

    # 浏览器中查看 candidates.html，勾选后下载 selection.json 放回主题目录
    # 然后跑处理阶段
    python -m topic_research.cli process --topic "agent 开发" --slug agent-development

可分阶段独立运行；state.json 实现断点续跑。
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

from . import score_candidates, candidates_html, selection_io, subtitle_fetch, subtitle_clean
from . import chunker
from .card_generator import generate_card
from .config import CONFIG, require_api_key
from .cross_synthesizer import synthesize
from .minimax_client import MinimaxClient
from .report_writer import split_report
from .search_bilibili import collect
from .state_store import StateStore
from .topic_init import init_topic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("topic_research")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _topic_dir(slug: str | None, topic_arg: str | None) -> Path:
    if slug:
        return _project_root() / "topics" / slug
    if topic_arg:
        from .topic_init import slugify

        return _project_root() / "topics" / slugify(topic_arg)
    raise SystemExit("需要 --topic 或 --slug")


def cmd_search(args: argparse.Namespace) -> None:
    require_api_key()
    title = args.topic
    slug = args.slug or title

    topic_dir = init_topic(_project_root() / "topics", title=title, slug=slug)
    state = StateStore(topic_dir)
    state.set("title", title)

    logger.info("主题：%s（slug=%s）", title, slug)
    if getattr(args, "use_bing", False):
        from .search_bing_bilibili import (
            search_bilibili_via_bing,
            fetch_meta_via_official_site,
        )

        logger.info("通过 Bing 搜索 B站视频（绕过 api.bilibili.com）...")
        bvids = search_bilibili_via_bing(title, max_results=args.limit)
        metas = []
        for bvid in bvids:
            meta = fetch_meta_via_official_site(bvid)
            if meta:
                metas.append(meta)
            time.sleep(0.2)
        if not metas:
            logger.warning("Bing 兜底也未抓到任何候选，请确认网络。")
    else:
        logger.info("搜索 B站候选 ...")
        metas = collect(
            title,
            max_results=args.limit,
            sort=args.sort,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
        )

    # 字幕状态探测：仅查字幕列表，不下载字幕内容
    logger.info("探测每个视频的字幕类型 ...")
    for m in metas:
        try:
            meta = subtitle_fetch.fetch_subtitle_meta(m.bvid)
            subs = meta.get("subtitles", [])
            if not subs:
                m.subtitle_type = "none"
            else:
                # 粗略判断：ai_type 1 表示自动字幕
                has_auto = any(s.get("ai_type") == 1 for s in subs)
                m.subtitle_type = "auto" if has_auto else "official"
        except Exception as e:
            logger.warning("探测字幕失败 %s: %s", m.bvid, e)
            m.subtitle_type = "unknown"
        time.sleep(0.2)

    # 综合评分
    now_ts = int(time.time())
    scored = score_candidates.score_all(metas, title, now_ts)
    scored.sort(key=lambda s: s.score, reverse=True)

    # 落盘 candidates/<bvid>.json
    for s in scored:
        meta_path = topic_dir / "candidates" / f"{s.meta.bvid}.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            __import__("json").dumps(
                {"score": s.score, "sub_scores": s.sub_scores, "reasons": s.reasons, "meta": s.meta.to_dict()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        state.upsert_video(
            s.meta.bvid,
            title=s.meta.title,
            owner=s.meta.owner_name,
            duration=s.meta.duration,
            publish_time=s.meta.publish_time,
            view=s.meta.view,
            like=s.meta.like,
            subtitle_type=s.meta.subtitle_type,
            score=s.score,
            selection_state="pending",
            fetch_state="pending",
            card_state="pending",
            error=None,
        )

    out_html = topic_dir / "candidates.html"
    candidates_html.render(scored, title=title, slug=slug, out_path=out_html)
    state.set("candidates_html", str(out_html))
    state.set("last_stage", "search_done")
    state.save()

    logger.info("候选 HTML 已生成：%s", out_html)
    logger.info("请打开该页面勾选视频，然后点击「导出勾选 selection.json」，将文件放回主题目录。")


def cmd_process(args: argparse.Namespace) -> None:
    require_api_key()
    topic_dir = _topic_dir(args.slug, args.topic)
    if not topic_dir.exists():
        raise SystemExit(f"主题目录不存在：{topic_dir}。请先运行 search 阶段。")

    state = StateStore(topic_dir)
    title = state.get("title") or topic_dir.name
    state.set("title", title)

    selection_file = topic_dir / "selection.json"
    if not selection_file.exists():
        raise SystemExit(
            f"未找到 {selection_file}。请先在候选页面导出勾选结果，并把 selection.json 放回主题目录。"
        )

    selected = selection_io.load_selection(selection_file)
    if not selected:
        raise SystemExit("selection.json 中没有已勾选的有效视频（已自动过滤无字幕视频）。")
    logger.info("已选择 %d 个视频进行处理。", len(selected))

    # 更新 state 的 selection_state
    for s in selected:
        state.upsert_video(
            s["bvid"],
            title=s.get("title"),
            owner=s.get("owner"),
            duration=s.get("duration"),
            subtitle_type=s.get("subtitle_type"),
            selection_state="selected",
        )

    client = MinimaxClient()

    for s in selected:
        bvid = s["bvid"]
        video_state = state.video(bvid)
        if video_state.get("card_state") == "done":
            logger.info("[%s] 已处理过，跳过。", bvid)
            continue

        # 1. 下载字幕
        try:
            result = subtitle_fetch.fetch_subtitle(bvid)
        except Exception as e:
            logger.exception("[%s] 字幕下载失败", bvid)
            state.update_video(bvid, fetch_state="failed", error=str(e))
            continue

        if result.subtitle_type == "none" or not result.cues:
            state.update_video(bvid, fetch_state="skipped", error="无字幕")
            logger.warning("[%s] 无字幕，跳过。", bvid)
            continue

        src_path = topic_dir / "sources" / f"{bvid}.txt"
        subtitle_fetch.save_subtitle_text(result, src_path)
        state.update_video(
            bvid,
            fetch_state="fetched",
            subtitle_type=result.subtitle_type,
            error=None,
        )

        # 2. 单视频卡片
        try:
            card_path = topic_dir / "cards" / f"{bvid}.md"
            generate_card(
                client,
                bvid=bvid,
                title=video_state.get("title") or s.get("title", ""),
                owner=video_state.get("owner") or s.get("owner", ""),
                subtitle_type=result.subtitle_type,
                source_txt=src_path,
                out_card=card_path,
            )
            state.update_video(bvid, card_state="done", card_file=str(card_path))
            logger.info("[%s] 单视频卡片完成。", bvid)
        except Exception as e:
            logger.exception("[%s] 单视频卡片生成失败", bvid)
            state.update_video(bvid, card_state="failed", error=str(e))

        time.sleep(0.5)

    # 3. 跨视频汇总
    cards_for_synth: list[tuple[str, str, Path]] = []
    for s in selected:
        bvid = s["bvid"]
        if state.video(bvid).get("card_state") != "done":
            continue
        card_file = state.video(bvid).get("card_file")
        if not card_file:
            continue
        cards_for_synth.append((bvid, state.video(bvid).get("title", ""), Path(card_file)))

    if not cards_for_synth:
        logger.warning("没有成功生成的单视频卡片，跳过汇总。")
        state.set("last_stage", "process_done_no_cards")
        state.save()
        return

    report_md = topic_dir / "report.md"
    synthesize(
        client,
        topic=title,
        cards=cards_for_synth,
        out_md=report_md,
    )
    state.set("report_state", "done")
    state.set("report_file", str(report_md))
    split_report(report_md, topic_dir, title)
    state.set("last_stage", "process_done")
    state.save()

    usage = client.total_usage()
    logger.info(
        "处理完成。用量：输入 %d tokens / 输出 %d tokens",
        usage["input_tokens"],
        usage["output_tokens"],
    )
    logger.info("综合报告：%s", report_md)


def cmd_init(args: argparse.Namespace) -> None:
    """仅创建主题目录"""
    topic_dir = init_topic(_project_root() / "topics", title=args.topic, slug=args.slug)
    print(topic_dir)


def _candidate_selection_paths(slug: str, topic_dir: Path) -> list[Path]:
    """在常见位置查找用户导出的 selection.json"""
    candidates: list[Path] = []
    target_name = topic_dir / "selection.json"
    candidates.append(target_name)  # 主题目录本身

    # 浏览器默认下载目录
    home = Path.home()
    for dl in (home / "Downloads", home / "下载", home / "Desktop"):
        if dl.exists():
            candidates.append(dl / f"{slug}-selection.json")
            candidates.append(dl / "selection.json")
    return candidates


def cmd_run(args: argparse.Namespace) -> None:
    """一键流程：自动找 selection.json（主题目录或下载目录）→ 复制进去 → 跑 process

    浏览器安全模型下 candidates.html 无法直接写文件到项目目录，
    所以让 run 子命令把用户从下载目录导出的 selection.json 自动归位。
    """
    require_api_key()
    topic_dir = _topic_dir(args.slug, args.topic)
    if not topic_dir.exists():
        raise SystemExit(f"主题目录不存在：{topic_dir}。请先运行 search 阶段。")

    target = topic_dir / "selection.json"
    if target.exists():
        logger.info("selection.json 已在主题目录：%s", target)
    else:
        found = None
        for cand in _candidate_selection_paths(args.slug or topic_dir.name, topic_dir):
            if cand.exists() and cand.resolve() != target.resolve():
                found = cand
                break
        if not found:
            raise SystemExit(
                f"未在主题目录或下载目录找到 selection.json。\n"
                f"  - 预期位置：{target}\n"
                f"  - 也查找了：~/Downloads/、~/下载/、~/Desktop/ 下的 {args.slug}-selection.json\n"
                f"  请先在 candidates.html 勾选并导出 selection.json。"
            )
        import shutil
        shutil.copy2(found, target)
        logger.info("已把 selection.json 从 %s 复制到 %s", found, target)

    # 透传给 cmd_process
    cmd_process(argparse.Namespace(slug=args.slug, topic=args.topic))


def cmd_serve(args: argparse.Namespace) -> None:
    """本地 HTTP server：浏览器直连 → 导出 selection.json 零对话框 → 一键跑 process

    工作流：
    1. 浏览器打开 http://127.0.0.1:<port>/
    2. 勾选视频 → 点「导出勾选」→ 文件直接写到 topics/<slug>/selection.json（无对话框）
    3. 页面出现「▶ 立即开始处理」按钮 → 点击 → 自动跑 process
    4. 页面轮询显示处理进度
    """
    topic_dir = _topic_dir(args.slug, args.topic)
    if not topic_dir.exists():
        raise SystemExit(f"主题目录不存在：{topic_dir}。请先运行 search 阶段。")

    from .serve import serve as _serve

    _serve(
        project_root=_project_root(),
        slug=args.slug or topic_dir.name,
        port=args.port,
        open_browser=not args.no_open,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="topic-research", description="主题学习研究工作流")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="搜索 B站候选 + 生成候选页")
    p_search.add_argument("--topic", required=True, help="主题关键词，例如 'agent 开发'")
    p_search.add_argument("--slug", help="主题目录 slug（默认与 topic 一致）")
    p_search.add_argument("--limit", type=int, default=CONFIG.BILI_CANDIDATE_LIMIT, help="候选上限")
    p_search.add_argument("--sort", default="totalrank", help="排序：totalrank/click/pubdate/dm/stow")
    p_search.add_argument("--min-duration", type=int, default=CONFIG.BILI_MIN_DURATION, help="最小时长（秒），默认 300 = 5 分钟")
    p_search.add_argument("--max-duration", type=int, default=CONFIG.BILI_MAX_DURATION, help="最大时长（秒），默认 2400 = 40 分钟")
    p_search.add_argument("--use-bing", action="store_true", help="走 Bing 搜索 B站视频（用于无法直连 api.bilibili.com 的环境）")
    p_search.set_defaults(func=cmd_search)

    p_proc = sub.add_parser("process", help="处理已选视频：下载字幕 + 生成卡片 + 汇总")
    p_proc.add_argument("--topic", help="主题关键词（与 search 阶段一致）")
    p_proc.add_argument("--slug", help="主题 slug")
    p_proc.set_defaults(func=cmd_process)

    p_init = sub.add_parser("init", help="仅创建主题目录")
    p_init.add_argument("--topic", required=True)
    p_init.add_argument("--slug")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="一键流程：找 selection.json → 跑 process（自动从下载目录归位）")
    p_run.add_argument("--topic", help="主题关键词")
    p_run.add_argument("--slug", help="主题 slug")
    p_run.set_defaults(func=cmd_run)

    p_serve = sub.add_parser("serve", help="本地 HTTP server：浏览器直连，导出零对话框")
    p_serve.add_argument("--slug", help="主题 slug")
    p_serve.add_argument("--topic", help="主题关键词（与 search 阶段一致）")
    p_serve.add_argument("--port", type=int, default=8765, help="端口，默认 8765")
    p_serve.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())