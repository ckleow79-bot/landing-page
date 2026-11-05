# Insights: how to publish

Each post is one Markdown file in this folder, e.g. `2026-11-e-invoice-rm3m.md`.

```
---
title: "e-Invoice: exemption threshold raised to RM3 million"
type: update            # update | case-note | practice-note
date: 2026-11-05        # publication date
as_at: 2026-11-05       # information current to
topic: e-Invoice        # e-Invoice | Budget | Income tax | SST | Case law | CFO | AI in finance
summary: One sentence that appears on the Insights list and in search results.
sources:
  - title: "LHDN e-Invoice Guideline v4.8"
    url: https://www.hasil.gov.my/...
status: draft           # change to: published  (only published posts go live)
---

## What changed
...
```

Supported Markdown: `##`/`###` headings, paragraphs, `-` and `1.` lists, `**bold**`, `*italic*`, `[links](https://...)`, `>` quotes.

Netlify runs `python3 tools/build-insights.py` on every deploy. It builds `insight-<slug>.html`,
`data/insights.json` and `feed.xml` from **published** posts only.

**Drafts are public if committed here** (this repository is public). Keep drafts in
`content/insights/_drafts/`: that folder is git-ignored and the build skips subfolders.
When a post is approved, set `status: published` and move it up into `content/insights/`.

To preview drafts privately: `python3 tools/build-insights.py --preview --src content/insights/_drafts`,
start the server (`npm start`) and open `http://localhost:5700/preview-insight-<slug>.html`.
Preview files are git-ignored; never commit them.
