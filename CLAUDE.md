# CLAUDE.md: B & K Group website

Read `HANDOFF.md` before starting work: current status, Keith's decisions, open questions and the next fixes.
`AGENTS.md` and the older planning documents are partly out of date; this file and `HANDOFF.md` take precedence.

## Owner and audience
Keith Leow, Tax Director, B & K Advisory PLT / B & K Academy PLT, Kuala Lumpur. Licensed tax agent (s.153 ITA 1967).
Write for Malaysian practitioners and directors: concise, no beginner explanations, Malaysian context (LHDN, ITA 1967, SST, MyInvois, HRD Corp).

## Commands
```
npm start                 # python3 -m http.server 5700 -> http://localhost:5700
npm run build             # css/site.css bundle + Insights (published posts only)
npm test                  # tests/regression.js + tests/features.js (server must be running)
npm run i18n:collect      # list every translatable string -> i18n-keys.json
```
Windows: use `python` if `python3` is missing. Tests need `npm install` and `npx playwright install chromium` once.
After any CSS change run `python3 tools/bundle-css.py`; pages load only `css/site.css`.

## Rules (from Keith; do not break)
- **Never invent** a figure, date, citation, section number, case or rule. Tax content must come from primary sources (LHDN, Federal Gazette, MOF, published judgments) and be dated "as at".
- **No promised tax outcomes.** General information only.
- **Never claim CPD hours or HRD Corp claimability** beyond what Keith confirmed (see HANDOFF.md).
- **Confidentiality / PDPA 2010:** this repository is **public**. Never commit client documents, TINs, the training-schedule spreadsheet, per-client fees, participant names, unblurred photos, drafts or review notes. Only company names of clients are published.
- No LHDN or other official logos. No Google Analytics.
- Every visible English string needs Chinese and Malay entries in `data/i18n/zh.json` and `data/i18n/ms.json` (never a value identical to its key).
- Respect `prefers-reduced-motion`; keep pages free of horizontal scroll at 390 px; keep forms honest (never show "sent" unless it was).
- Do not create pull requests unless Keith asks; work on branch `ccr-b2fa6464-hgxz8q` (PR #3) unless told otherwise.

## Key files
- Pages: `index, advisory, academy, programmes, insights, about, faq, contact` `.html`; components in `components/`.
- Language: `js/i18n.js`; Forms: `js/supabase.js`; Programmes: `js/programmes.js` + `data/programmes.json`; Assistant: `js/chatbot.js`; Motion: `js/cinematic.js`, `js/motion.js`.
- Styles: edit `css/features.css` (newest) or the other sources, then bundle.
- Insights: `content/insights/*.md` (published), drafts in `content/insights/_drafts/` (git-ignored), built by `tools/build-insights.py`.
- Supabase SQL: `migrations/` (003 = admin-only access, still to be run by Keith).
