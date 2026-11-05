#!/usr/bin/env python3
"""
Build the Insights section from Markdown.

  content/insights/*.md   one post per file, YAML-style front matter (see content/insights/README.md)

Only posts with `status: published` are built. Drafts are never copied anywhere, so a
draft can sit in the folder (or, better, outside the repo) without going live.

Writes:
  data/insights.json        list of published posts (newest first) for insights.html
  insight-<slug>.html       one page per post, with Article / LegalCase-free JSON-LD
  feed.xml                  RSS 2.0 feed

No third-party packages: a small Markdown subset is supported (## / ### headings,
paragraphs, - lists, 1. lists, **bold**, *italic*, [links](https://...), > quotes).

Run:  python3 tools/build-insights.py            (publishes status: published only)
      python3 tools/build-insights.py --preview --src content/insights/_drafts
            renders every post in that folder, drafts included, as preview-insight-<slug>.html
            (git-ignored) for private review on the local server
"""
import html, json, os, re, sys, datetime
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://bkcorporate.com/'
TYPES = {'update': 'Tax update', 'case-note': 'Case note', 'practice-note': 'Practice note'}


def parse(path):
    raw = open(path, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', raw, re.S)
    if not m:
        raise SystemExit(f'{path}: missing front matter')
    meta, body = {}, m.group(2)
    key, sources = None, []
    for line in m.group(1).split('\n'):
        if not line.strip():
            continue
        if re.match(r'^\s+-\s+title:', line):
            sources.append({'title': unq(line.split('title:', 1)[1])})
        elif re.match(r'^\s+url:', line) and sources:
            sources[-1]['url'] = unq(line.split('url:', 1)[1])
        elif re.match(r'^[A-Za-z_]+:', line):
            key, val = line.split(':', 1)
            meta[key.strip()] = unq(val)
    meta['sources'] = [s for s in sources if s.get('url', '').startswith('https://')]
    for k in ('title', 'type', 'date', 'summary', 'status'):
        if not meta.get(k):
            raise SystemExit(f'{path}: front matter needs "{k}"')
    meta['slug'] = meta.get('slug') or re.sub(r'^\d+-', '', os.path.splitext(os.path.basename(path))[0])
    meta['body_md'] = body.strip()
    return meta


def unq(v):
    v = v.strip()
    if len(v) > 1 and v[0] == v[-1] and v[0] in '"\'':
        v = v[1:-1]
    return v


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'\[([^\]]+)\]\((https://[^)\s]+)\)', lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<em>\1</em>', t)
    return t


def md(text):
    out, para, lst = [], [], None

    def flush():
        nonlocal para, lst
        if para:
            out.append('<p>' + '<br>'.join(inline(x) for x in para) + '</p>')
            para = []
        if lst:
            tag, items = lst
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(i)}</li>' for i in items) + f'</{tag}>')
            lst = None

    for line in text.split('\n'):
        s = line.rstrip()
        if not s.strip():
            flush(); continue
        h = re.match(r'^(#{2,4})\s+(.*)$', s)
        ul = re.match(r'^\s*[-*]\s+(.*)$', s)
        ol = re.match(r'^\s*\d+\.\s+(.*)$', s)
        q = re.match(r'^>\s?(.*)$', s)
        if h:
            flush(); n = len(h.group(1)); out.append(f'<h{n}>{inline(h.group(2))}</h{n}>')
        elif ul or ol:
            tag = 'ul' if ul else 'ol'
            if para: flush()
            if lst and lst[0] != tag: flush()
            if not lst: lst = (tag, [])
            lst[1].append((ul or ol).group(1))
        elif q:
            flush(); out.append(f'<blockquote><p>{inline(q.group(1))}</p></blockquote>')
        else:
            if lst: flush()
            para.append(s.strip())
    flush()
    return '\n'.join(out)


def fmt_date(d):
    try:
        x = datetime.date.fromisoformat(d)
        return f'{x.day} {x:%B %Y}'
    except ValueError:
        return d


def page(p, rel=''):
    e = lambda v: html.escape(str(v or ''))
    label = TYPES.get(p['type'], 'Insight')
    src = ''.join(f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a></li>' for s in p['sources'])
    ld = {
        '@context': 'https://schema.org', '@type': 'Article', 'headline': p['title'], 'description': p['summary'],
        'datePublished': p['date'], 'dateModified': p.get('as_at') or p['date'],
        'author': {'@type': 'Person', 'name': 'Keith Leow', 'jobTitle': 'Licensed Tax Agent'},
        'publisher': {'@type': 'Organization', 'name': 'B & K Group', 'url': SITE},
        'mainEntityOfPage': SITE + f'insight-{p["slug"]}.html', 'articleSection': label,
        'citation': [s['url'] for s in p['sources']]
    }
    draft = p['status'] != 'published'
    return f'''<!DOCTYPE html>
<html lang="en" class="has-gsap">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{e(p["title"])} | B &amp; K Group Insights</title>
    <meta name="description" content="{e(p["summary"])}">
    {'<meta name="robots" content="noindex">' if draft else ''}
    <link rel="preload" href="{rel}assets/fonts/bricolage-grotesque-400-800-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="{rel}css/site.css">
    <meta property="og:title" content="{e(p["title"])}">
    <meta property="og:description" content="{e(p["summary"])}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{SITE}insight-{e(p["slug"])}.html">
    <link rel="canonical" href="{SITE}insight-{e(p["slug"])}.html">
    <link rel="alternate" type="application/rss+xml" title="B &amp; K Group Insights" href="{rel}feed.xml">
    <link rel="icon" type="image/svg+xml" href="{rel}assets/brand/favicon.svg">
    <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
    <a class="skip-link" href="#main">Skip to content</a>
    <div id="header-container"></div>
    <main id="main">
        <section class="page-hero-cine post-hero" data-theme-dark>
            <div class="container">
                <p class="hero-kicker"><a href="{rel}insights.html">Insights</a> · {e(label)}{' · DRAFT FOR REVIEW' if draft else ''}</p>
                <h1>{e(p["title"])}</h1>
                <p class="post-meta">Keith Leow, Licensed Tax Agent · {e(fmt_date(p["date"]))}{(' · information as at ' + e(fmt_date(p["as_at"]))) if p.get("as_at") else ''}</p>
            </div>
        </section>
        <article class="post-body">
            <div class="container post-wrap">
                <p class="post-summary">{e(p["summary"])}</p>
                {md(p["body_md"])}
                {f'<aside class="post-sources"><h2>Sources</h2><ol>{src}</ol></aside>' if src else ''}
                <aside class="post-cta">
                    <h2>Does this affect you?</h2>
                    <p>Tell us your situation and we will say plainly whether it matters and what it would take. The first 15-minute call is free.</p>
                    <p class="post-cta-btns"><a class="btn btn-primary" href="{rel}contact.html#quote">Request a quote</a><a class="btn btn-outline" href="https://wa.me/601130636198?text={html.escape(__import__("urllib.parse").parse.quote("Hi B&K, I read your note: " + p["title"] + ". My question is ..."))}" target="_blank" rel="noopener">WhatsApp</a><a class="btn btn-outline" href="{rel}insights.html#subscribe">Get updates by email</a></p>
                </aside>
            </div>
        </article>
    </main>
    <div id="footer-container"></div>
    <div id="chatbot-container"></div>
    <script src="{rel}js/i18n.js"></script>
    <script src="{rel}js/icons.js"></script>
    <script src="{rel}js/vendor/gsap.min.js"></script>
    <script src="{rel}js/vendor/ScrollTrigger.min.js"></script>
    <script src="{rel}js/vendor/lenis.min.js"></script>
    <script src="{rel}js/vendor/supabase.min.js"></script>
    <script src="{rel}js/supabase.js"></script>
    <script src="{rel}js/chatbot.js"></script>
    <script src="{rel}js/main.js"></script>
    <script src="{rel}js/motion.js"></script>
</body>
</html>
'''


def feed(posts):
    e = lambda v: html.escape(str(v or ''))
    items = ''
    for p in posts:
        d = datetime.datetime.fromisoformat(p['date'] + 'T09:00:00+08:00')
        items += f'''  <item>
    <title>{e(p["title"])}</title>
    <link>{SITE}insight-{e(p["slug"])}.html</link>
    <guid isPermaLink="true">{SITE}insight-{e(p["slug"])}.html</guid>
    <pubDate>{format_datetime(d)}</pubDate>
    <category>{e(TYPES.get(p["type"], "Insight"))}</category>
    <description>{e(p["summary"])}</description>
  </item>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>B &amp; K Group Insights</title>
  <link>{SITE}insights.html</link>
  <description>Malaysian tax updates, case notes and practice notes from B &amp; K Group.</description>
  <language>en-my</language>
{items}</channel>
</rss>
'''


def main():
    args = sys.argv[1:]
    src = os.path.join(ROOT, 'content', 'insights')
    if '--src' in args:
        src = os.path.abspath(args[args.index('--src') + 1])
    files = sorted(f for f in os.listdir(src) if f.endswith('.md') and f.lower() != 'readme.md') if os.path.isdir(src) else []  # subfolders (e.g. _drafts/) are ignored
    posts = [parse(os.path.join(src, f)) for f in files]

    if '--preview' in args:
        # private preview of every post, drafts included: preview-insight-<slug>.html at the site root
        # (git-ignored, noindex for drafts), so header, footer and styles load as on the real page
        for f in os.listdir(ROOT):
            if f.startswith('preview-insight-') and f.endswith('.html'):
                os.remove(os.path.join(ROOT, f))
        for p in posts:
            open(os.path.join(ROOT, f'preview-insight-{p["slug"]}.html'), 'w', encoding='utf-8', newline='\n').write(page(p))
        print(f'preview: {len(posts)} posts (drafts included) -> preview-insight-*.html, open http://localhost:5700/preview-insight-<slug>.html')
        return

    pub = sorted((p for p in posts if p['status'] == 'published'), key=lambda p: p['date'], reverse=True)
    for f in os.listdir(ROOT):  # remove pages of posts that were unpublished
        if f.startswith('insight-') and f.endswith('.html') and f[8:-5] not in {p['slug'] for p in pub}:
            os.remove(os.path.join(ROOT, f))
    for p in pub:
        open(os.path.join(ROOT, f'insight-{p["slug"]}.html'), 'w', encoding='utf-8', newline='\n').write(page(p))
    listing = [{k: p.get(k) for k in ('slug', 'title', 'type', 'date', 'as_at', 'topic', 'summary')} for p in pub]
    for x in listing:
        x['type_label'] = TYPES.get(x['type'], 'Insight')
    json.dump(listing, open(os.path.join(ROOT, 'data', 'insights.json'), 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'feed.xml'), 'w', encoding='utf-8', newline='\n').write(feed(pub))
    print(f'insights: {len(pub)} published, {len(posts) - len(pub)} not published')


if __name__ == '__main__':
    main()
