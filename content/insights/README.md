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

**Drafts are public if committed here** (this repository is public). Keep drafts outside the
repository until they are approved, then copy them in with `status: published`.

To preview drafts privately: `python3 tools/build-insights.py --preview review/insights-preview --src <drafts folder>`
(`review/` is not committed).
