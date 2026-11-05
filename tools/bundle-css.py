#!/usr/bin/env python3
"""Bundle the site's stylesheets into css/site.css (one request instead of ~15).

Run after editing any file in css/:  python3 tools/bundle-css.py
Netlify also runs it on every deploy (see netlify.toml), so the bundle cannot go stale online.
Order matters: it is the cascade order the pages used before bundling.
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = [
    'css/tokens/fonts.css', 'css/tokens/colors.css', 'css/tokens/typography.css', 'css/tokens/spacing.css',
    'css/tokens/theme-dark.css', 'css/tokens/signature.css', 'css/main.css', 'css/pages.css', 'css/responsive.css',
    'css/animations.css', 'css/chatbot.css', 'css/cinematic.css', 'css/brand.css', 'css/audit-story.css', 'css/features.css',
]
OUT = os.path.join(ROOT, 'css', 'site.css')

def rebase(css, src):
    """Rewrite relative url(...) so they still resolve from css/site.css."""
    src_dir = os.path.dirname(os.path.join(ROOT, src))
    def fix(m):
        u = m.group(2)
        if re.match(r'^(data:|https?:|/|#)', u):
            return m.group(0)
        abs_path = os.path.normpath(os.path.join(src_dir, u))
        rel = os.path.relpath(abs_path, os.path.dirname(OUT)).replace(os.sep, '/')
        return f'url({m.group(1)}{rel}{m.group(1)})'
    return re.sub(r'url\((["\']?)([^)"\']+)\1\)', fix, css)

def minify(css):
    # Light and safe: drop comments and collapse indentation/newlines. Strings are left
    # untouched apart from runs of whitespace (none of ours rely on those); gzip does the rest.
    css = re.sub(r'/\*(?!!).*?\*/', '', css, flags=re.S)
    css = re.sub(r'[ \t]*\n[ \t\n]*', '\n', css)
    return css.strip()

parts = []
for f in ORDER:
    with open(os.path.join(ROOT, f), encoding='utf-8') as fh:
        parts.append(rebase(fh.read(), f))
out = '/*! B&K Group site styles, bundled from css/*.css by tools/bundle-css.py. Edit the sources, not this file. */\n' + minify('\n'.join(parts)) + '\n'
with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write(out)
print(f'css/site.css: {len(out) // 1024} KB from {len(ORDER)} files')
