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

## Story format (optional)

Add `series: case-story` (a tax case) or `series: ruling-story` (a public ruling or guideline)
to the front matter. The post is then labelled "Case story" / "Ruling story" and appears under
that filter on the Insights page (and still under its `type`). Inside the post:

- A paragraph starting `**Scene 1: ...**` or `**Step 1: ...**` becomes a numbered story card.
- `## Key points` and `## Where this stands` sections are drawn as boxes.

Shape that works: hook question in the title, 3 to 5 scenes or steps in plain words, then
"Why" (the law, with section numbers), "Plot twists" (traps), Key points (5 or 6 lines),
Where this stands (appeal window, as-at date). Keep humour on the situation, never on the
taxpayer. Examples: `content/insights/_drafts/` (local only).

Supported Markdown: `##`/`###` headings, paragraphs, `-` and `1.` lists, `**bold**`, `*italic*`, `[links](https://...)`, `>` quotes.

Netlify runs `python3 tools/build-insights.py` on every deploy. It builds `insight-<slug>.html`,
`data/insights.json` and `feed.xml` from **published** posts only.

**Drafts are public if committed here** (this repository is public). Keep drafts in
`content/insights/_drafts/`: that folder is git-ignored and the build skips subfolders.
When a post is approved, set `status: published` and move it up into `content/insights/`.

To preview drafts privately: `python3 tools/build-insights.py --preview --src content/insights/_drafts`,
start the server (`npm start`) and open `http://localhost:5700/preview-insight-<slug>.html`.
Preview files are git-ignored; never commit them.
