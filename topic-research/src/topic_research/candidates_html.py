"""渲染本地候选页面 candidates.html

使用纯静态 HTML + 一段 JS 完成勾选，无需后端。
- 每张卡片含多选框
- 顶部按钮：全选高分项、仅官方字幕、全不选、导出 selection.json
- 自动字幕黄色警告，无字幕红色"将跳过"提示
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .score_candidates import ScoredCandidate


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title} — 候选视频</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #f5f6f8; color: #1f2330; margin: 0; padding: 16px 32px; }}
  header {{ position: sticky; top: 0; background: #fff; padding: 12px 16px; border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,.06); margin-bottom: 20px; z-index: 5; }}
  h1 {{ margin: 0 0 4px; font-size: 20px; }}
  .toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
  button {{ padding: 6px 12px; border: 1px solid #d0d3d8; background: #fff; border-radius: 6px;
           cursor: pointer; font-size: 13px; }}
  button:hover {{ background: #f0f3f7; }}
  .stats {{ font-size: 12px; color: #5b6273; margin-top: 8px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
          gap: 16px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 14px;
          box-shadow: 0 1px 3px rgba(0,0,0,.06); display: flex; flex-direction: column; gap: 8px; }}
  .card-header {{ display: flex; gap: 10px; align-items: flex-start; }}
  .cover {{ width: 160px; height: 96px; object-fit: cover; border-radius: 6px;
           background: #e8eaef; flex-shrink: 0; }}
  .title {{ font-size: 14px; font-weight: 600; line-height: 1.4; margin: 0; }}
  .meta-row {{ font-size: 12px; color: #5b6273; display: flex; flex-wrap: wrap; gap: 8px; }}
  .score-pill {{ background: #e8f0ff; color: #1d4ed8; padding: 2px 8px; border-radius: 12px;
                font-weight: 600; font-size: 12px; }}
  .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
  .badge-official {{ background: #d1f7d6; color: #166534; }}
  .badge-auto {{ background: #fff4cc; color: #92580a; }}
  .badge-none {{ background: #fde2e2; color: #991b1b; }}
  .badge-unknown {{ background: #e0e3eb; color: #475569; }}
  .warn {{ background: #fff8db; color: #8a6100; padding: 6px 8px; border-radius: 4px;
         font-size: 12px; }}
  .skip {{ background: #fde2e2; color: #991b1b; padding: 6px 8px; border-radius: 4px;
         font-size: 12px; }}
  .reasons {{ background: #fafbfd; padding: 6px 8px; border-radius: 4px; font-size: 12px;
             color: #5b6273; }}
  .actions {{ display: flex; align-items: center; justify-content: space-between;
             margin-top: 4px; }}
  .checkbox {{ transform: scale(1.2); }}
  .subscores {{ font-size: 11px; color: #5b6273; }}
  .subscores span {{ margin-right: 6px; }}
  .empty {{ color: #9aa0ac; font-style: italic; }}
</style>
</head>
<body>
<header>
  <h1>📚 主题：{title}</h1>
  <div class="stats">
    共 <b id="total-count">0</b> 条候选，
    已勾选 <b id="selected-count">0</b> 条，
    其中官方字幕 <b id="official-count">0</b> 条、
    自动字幕 <b id="auto-count">0</b> 条、
    无字幕（将跳过）<b id="none-count">0</b> 条
  </div>
  <div class="toolbar">
    <button onclick="selectTop()">全选高分项 (≥ 0.7)</button>
    <button onclick="selectOfficial()">仅选官方字幕</button>
    <button onclick="selectNone()">全不选</button>
    <button onclick="exportSelection()">导出勾选 selection.json</button>
    <span id="export-msg" class="stats" style="margin-left:8px;"></span>
  </div>
</header>

<div class="grid" id="grid">
  {cards}
</div>

<script>
  const items = {items_json};

  function refreshStats() {{
    const checked = items.filter(i => i.checked);
    document.getElementById('selected-count').textContent = checked.length;
    document.getElementById('official-count').textContent =
      checked.filter(i => i.subtitle_type === 'official').length;
    document.getElementById('auto-count').textContent =
      checked.filter(i => i.subtitle_type === 'auto').length;
    document.getElementById('none-count').textContent =
      checked.filter(i => i.subtitle_type === 'none').length;
  }}

  function bind() {{
    items.forEach(it => {{
      const cb = document.getElementById('cb-' + it.bvid);
      cb.addEventListener('change', () => {{
        it.checked = cb.checked;
        refreshStats();
      }});
    }});
  }}

  function selectTop() {{
    items.forEach(it => {{
      if (it.subtitle_type === 'none') {{
        it.checked = false;
      }} else {{
        it.checked = it.score >= 0.7;
      }}
      const cb = document.getElementById('cb-' + it.bvid);
      if (cb) cb.checked = it.checked;
    }});
    refreshStats();
  }}

  function selectOfficial() {{
    items.forEach(it => {{
      it.checked = it.subtitle_type === 'official';
      const cb = document.getElementById('cb-' + it.bvid);
      if (cb) cb.checked = it.checked;
    }});
    refreshStats();
  }}

  function selectNone() {{
    items.forEach(it => {{
      it.checked = false;
      const cb = document.getElementById('cb-' + it.bvid);
      if (cb) cb.checked = false;
    }});
    refreshStats();
  }}

  function exportSelection() {{
    const payload = {{
      topic_slug: "{slug}",
      exported_at: new Date().toISOString(),
      selected: items
        .filter(i => i.checked && i.subtitle_type !== 'none')
        .map(i => ({{
          bvid: i.bvid,
          title: i.title,
          owner: i.owner,
          duration: i.duration,
          subtitle_type: i.subtitle_type,
          score: i.score,
          url: i.url
        }}))
    }};
    const json = JSON.stringify(payload, null, 2);
    const fileName = '{slug}-selection.json';

    // 优先用 File System Access API（Chrome / Edge），弹出"另存为"对话框
    if (window.showSaveFilePicker) {{
      window.showSaveFilePicker({{
        suggestedName: fileName,
        types: [{{ description: 'JSON', accept: {{ 'application/json': ['.json'] }} }}]
      }}).then(async (handle) => {{
        const writable = await handle.createWritable();
        await writable.write(json);
        await writable.close();
        document.getElementById('export-msg').textContent =
          '✅ 已保存到 ' + handle.name + '。请把文件放到 topic-research/topics/{slug}/selection.json，然后跑 python -m topic_research.cli run --slug {slug}';
      }}).catch(err => {{
        if (err.name === 'AbortError') return;  // 用户取消
        document.getElementById('export-msg').textContent = '⚠️ 保存失败：' + err.message;
      }});
      return;
    }}

    // 兜底：老浏览器用 a.download，文件落到默认下载目录
    const blob = new Blob([json], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    document.getElementById('export-msg').textContent =
      '✅ 已下载 ' + fileName + '。直接跑 python -m topic_research.cli run --slug {slug}，会自动从下载目录把它挪到主题目录并开始处理。';
  }}

  document.getElementById('total-count').textContent = items.length;
  refreshStats();
  bind();
</script>
</body>
</html>
"""


def render_card(item: dict) -> str:
    sub_t = item["subtitle_type"]
    badge_map = {
        "official": ('<span class="badge badge-official">官方字幕</span>', ""),
        "auto": ('<span class="badge badge-auto">自动字幕</span>', '<div class="warn">⚠ 仅自动字幕，可能有错别字</div>'),
        "none": ('<span class="badge badge-none">无字幕</span>', '<div class="skip">✖ 该视频将被跳过，不会被总结</div>'),
        "unknown": ('<span class="badge badge-unknown">字幕未知</span>', ""),
    }
    badge, warn = badge_map.get(sub_t, ("", ""))

    subs = item["sub_scores"]
    sub_html = (
        f'<div class="subscores">'
        f'<span>相关 {subs["relevance"]:.2f}</span>'
        f'<span>播放 {subs["view"]:.2f}</span>'
        f'<span>新鲜 {subs["publish_time"]:.2f}</span>'
        f'<span>UP {subs["up"]:.2f}</span>'
        f'<span>互动 {subs["interaction"]:.2f}</span>'
        f'<span>时长 {subs["duration"]:.2f}</span>'
        f'<span>字幕 {subs["subtitle"]:.2f}</span>'
        f'</div>'
    )

    reasons_html = ""
    if item["reasons"]:
        reasons_html = (
            '<div class="reasons">⚑ ' + escape("；".join(item["reasons"])) + '</div>'
        )

    cover = item.get("cover") or ""
    owner = escape(item.get("owner", ""))
    title = escape(item.get("title", ""))
    desc = escape(item.get("description", "")[:120])
    pub = escape(item.get("publish_time_human", ""))
    url = escape(item.get("url", "#"))

    return f"""
<div class="card">
  <div class="card-header">
    <img class="cover" loading="lazy" src="{cover}" onerror="this.style.display='none'" />
    <div style="flex:1; min-width:0;">
      <p class="title"><a href="{url}" target="_blank">{title}</a></p>
      <div class="meta-row">
        <span>👤 {owner}</span>
        <span>⏱ {item['duration_human']}</span>
        <span>📅 {pub}</span>
      </div>
      <div class="meta-row">
        <span>▶ {item['view']:,}</span>
        <span>👍 {item['like']:,}</span>
        <span>★ {item['favorite']:,}</span>
        <span>💬 {item['reply']:,}</span>
        <span class="score-pill">综合 {item['score']:.2f}</span>
      </div>
    </div>
  </div>
  <div class="meta-row">{badge}</div>
  {warn}
  {subs}
  {reasons_html}
  <div class="actions">
    <label><input type="checkbox" class="checkbox" id="cb-{item['bvid']}" {'checked' if item.get('checked') else ''}/> 选入主题</label>
    <span class="meta-row">{item['bvid']}</span>
  </div>
</div>
"""


def _humanize_duration(sec: int) -> str:
    if sec <= 0:
        return "未知"
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _humanize_time(ts: int) -> str:
    if not ts:
        return "未知"
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def render(
    candidates: list[ScoredCandidate],
    title: str,
    slug: str,
    out_path: Path,
    default_checked_bvids: set[str] | None = None,
) -> Path:
    """渲染 candidates.html"""
    default_checked_bvids = default_checked_bvids or set()
    items: list[dict] = []
    cards_html: list[str] = []
    for c in candidates:
        m = c.meta
        item = {
            "bvid": m.bvid,
            "title": m.title,
            "owner": m.owner_name,
            "duration": m.duration,
            "duration_human": _humanize_duration(m.duration),
            "publish_time_human": _humanize_time(m.publish_time),
            "view": m.view,
            "like": m.like,
            "favorite": m.favorite,
            "reply": m.reply,
            "subtitle_type": m.subtitle_type,
            "score": c.score,
            "sub_scores": c.sub_scores,
            "reasons": c.reasons,
            "cover": m.cover,
            "url": m.url,
            "checked": m.bvid in default_checked_bvids,
        }
        items.append(item)
        cards_html.append(render_card(item))

    html = HTML_TEMPLATE.format(
        title=escape(title),
        slug=escape(slug),
        cards="\n".join(cards_html),
        items_json=json.dumps(items, ensure_ascii=False),
    )
    Path(out_path).write_text(html, encoding="utf-8")
    return Path(out_path)