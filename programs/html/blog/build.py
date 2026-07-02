#!/usr/bin/env python3
"""
Blog build script
使い方: python build.py
posts/*.md を読んでHTMLに変換し、posts.json を更新します。
"""

import os
import json
import re
import sys
from html import escape
from pathlib import Path

BLOG_DIR = Path(__file__).parent
POSTS_DIR = BLOG_DIR / "posts"
POSTS_JSON = BLOG_DIR / "posts.json"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_str = content[3:end].strip()
    body = content[end + 3:].strip()
    meta = {}
    for line in fm_str.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body


def md_to_html(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["extra", "toc", "nl2br"],
        )
    except ImportError:
        print("⚠  markdown ライブラリが見つかりません。")
        print("   pip install markdown  でインストールしてください。")
        print("   フォールバックの簡易変換を使います。\n")
        return _simple_md_to_html(text)


def _simple_md_to_html(text: str) -> str:
    """最小限のMarkdown→HTML変換（fallback用）"""
    html = []
    in_ul = False
    for line in text.splitlines():
        if line.startswith("### "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_ul: html.append("<ul>"); in_ul = True
            html.append(f"<li>{_inline(line[2:])}</li>")
        elif line.strip() == "---":
            if in_ul: html.append("</ul>"); in_ul = False
            html.append("<hr>")
        elif line.strip() == "":
            if in_ul: html.append("</ul>"); in_ul = False
            html.append("")
        else:
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<p>{_inline(line)}</p>")
    if in_ul:
        html.append("</ul>")
    return "\n".join(html)


def _inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"!\[(.+?)\]\((.+?)\)", r'<img src="\2" alt="\1" style="max-width:100%">', text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


POST_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex">
    <title>{title} | IKU NAVI ブログ</title>
    <link rel="stylesheet" href="../style.css">
    <link rel="icon" href="../../images/favicon.ico">
</head>
<body>
    <header class="site-header">
        <nav class="breadcrumb">
            <a href="../../index.html">IKU NAVI</a>
            <span>›</span>
            <a href="../index.html">ブログ</a>
            <span>›</span>
            <span>{title}</span>
        </nav>
    </header>

    <main class="post-container">
        <article class="post">
            <div class="post-meta">
                <time datetime="{date}">{date_ja}</time>
                {author_html}
            </div>
            <h1 class="post-title">{title}</h1>
            {thumbnail_html}
            <div class="post-body">
                {body}
            </div>
        </article>
    </main>

    <footer class="site-footer">
        <a href="../index.html">← ブログ一覧に戻る</a>
    </footer>
</body>
</html>
"""


def format_date_ja(date_str: str) -> str:
    try:
        from datetime import datetime
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{d.year}年{d.month}月{d.day}日"
    except Exception:
        return date_str


def build_post(md_path: Path) -> dict | None:
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(text)

    title = meta.get("title", md_path.stem)
    date = meta.get("date", "")
    author = meta.get("author", "")
    excerpt = meta.get("excerpt", "")
    thumbnail = meta.get("thumbnail", "")

    body_html = md_to_html(body_md)

    # frontmatter 由来の値は HTML エスケープして埋め込む（本文は Markdown 変換済みなので除く）
    author_html = f'<span class="post-author">{escape(author)}</span>' if author else ""
    thumbnail_html = (
        f'<div class="post-thumbnail"><img src="{escape(thumbnail)}" alt="{escape(title)}"></div>'
        if thumbnail
        else ""
    )

    html = POST_HTML_TEMPLATE.format(
        title=escape(title),
        date=escape(date),
        date_ja=escape(format_date_ja(date)),
        author_html=author_html,
        thumbnail_html=thumbnail_html,
        body=body_html,
    )

    slug = md_path.stem
    out_path = POSTS_DIR / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"  ✓ {slug}.html")

    return {
        "slug": slug,
        "title": title,
        "date": date,
        "author": author,
        "excerpt": excerpt,
        "thumbnail": thumbnail,
        "path": f"posts/{slug}.html",
    }


def main():
    md_files = sorted(POSTS_DIR.glob("*.md"), reverse=True)
    if not md_files:
        print("posts/*.md が見つかりません。")
        return

    # template.md はスキップ
    md_files = [f for f in md_files if f.stem != "template"]

    print(f"記事を {len(md_files)} 件変換します...\n")
    posts = []
    for md_path in md_files:
        result = build_post(md_path)
        if result:
            posts.append(result)

    # 日付順（新しい順）でソート
    posts.sort(key=lambda p: p["date"], reverse=True)

    POSTS_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nposts.json を更新しました（{len(posts)} 件）")
    print("完了！")


if __name__ == "__main__":
    main()
