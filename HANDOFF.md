# Handoff: B & K Group website (PR #3, branch `ccr-b2fa6464-hgxz8q`)

Status at 5 November 2026. Read this first in a new session (together with `CLAUDE.md`, which holds the standing rules), then pick up the **Open questions**.

## Run it

```
git checkout ccr-b2fa6464-hgxz8q
npm run build      # python3 tools/bundle-css.py && python3 tools/build-insights.py
npm start          # python3 -m http.server 5700 -> http://localhost:5700
npm install && npx playwright install chromium    # once, for tests
npm test           # tests/regression.js + tests/features.js against :5700; screenshots in tests/out/
```
Windows: if `python3` is not found, use `python` in the same commands.

Netlify (project snazzy-choux-2ee2b7) runs both build steps; preview: https://deploy-preview-3--snazzy-choux-2ee2b7.netlify.app

## How the site is built

- Static HTML, vanilla JS, GSAP + ScrollTrigger + Lenis (js/vendor). Header, footer and assistant are loaded from `components/`.
- **Languages:** English source; `data/i18n/zh.json` and `data/i18n/ms.json` map English text to Chinese / Malay (`text` keys = text nodes, `html` keys = leaf blocks). Switch: `[data-lang-set]` buttons, stored in localStorage `bk-lang` or `?lang=ms|zh`. Never store a translation identical to its English key (it loops; i18n.js now guards this).
  New strings: run the server, then `node tools/i18n-collect.js out.json`, translate the missing keys into both files.
- **Forms** (js/supabase.js): always preventDefault; on failure `BKFormFallback` shows pre-filled WhatsApp / email buttons. Reply preference (WhatsApp / email / video / phone); phone OR email required.
- **Programmes:** Supabase with 1.5 s timeout, falls back to `data/programmes.json`.
- **Insights:** Markdown in `content/insights/` (see its README). Only `status: published` goes live. **The repo is public: do not commit drafts.**
- Tests: `tests/regression.js` (all pages x 3 widths for errors/overflow, anchors, forms, programmes, 中文, reduced motion) and `tests/features.js` (BM/中文 coverage, fees, forms, programmes, phone action bar). Both passed at handoff.
- Insights drafts: put them in `content/insights/_drafts/` (git-ignored); preview with `python3 tools/build-insights.py --preview --src content/insights/_drafts` then open `http://localhost:5700/preview-insight-<slug>.html` (also git-ignored).

## Decisions Keith has made (do not re-ask)

- Prices approved, all **excl. 8% SST**, "final fee confirmed in an engagement letter after scoping": free 15-min call; 60-min consultation from RM 1,000 (credited in full if engaged); reply to an LHDN request for documents from RM 3,000; general audit (desk) from RM 5,000 and comprehensive audit (field) from RM 8,000, each up to 2 YAs, extra years quoted separately; investigation from RM 20,000 (quoted per case, in phases, led by Keith) (quoted per case); Form Q / DRP from RM 5,000; e-Invoice health check from RM 3,000 (fixed); e-Invoice implementation from RM 6,000; Form C from RM 2,500/yr; management accounts review from RM 3,000/month; fractional CFO from RM 6,000/month; in-house training from RM 8,000/day (up to 25 pax).
- CPD: "7 CPD hours per full day, subject to each professional body's assessment and decision". Never name a body or promise recognition.
- Travel: fee covers the course/work only; flights and hotel outside the Klang Valley charged separately.
- No referral fees paid or received (professional ethics); the client engages B & K directly.
- Speaking fee: on request.
- HRD Corp claimable only for the three High Impact Training Services PLT sessions (the HRD Corp training provider).
- Standing rules: no invented figures, citations or rules; no promised tax outcomes; client data confidential (only company names published, participant faces blurred); no TINs; no LHDN logos.

## Open questions for Keith

1. Does Keith **present in Bahasa Malaysia** himself? About/speaking/FAQ say English or Mandarin; other pages offer BM delivery. Make every page consistent with the answer.
2. Starting fees still missing: company set-up + secretarial retainer, transfer pricing review, a startup bundle, personal / property tax for individuals.
3. Seminar payment terms (how/when to pay) and cancellation / replacement policy (B & K's or High Impact's).
4. Wording on working with referring accounting firms (beyond referral fees: not soliciting the firm's work, keeping it informed with client consent, coordinating with auditors). Needs Keith's approval.
5. Proof: portrait photo, named second reviewer/team, anonymised case outcomes, testimonials.
6. Insights drafts (e-Invoice RM3m exemption, Budget 2027, *Kind Action* case note) were sent to Keith outside the repo (move pack, folder `insights-drafts`); figures unverified (the cloud sandbox could not open LHDN, MOF or eLaw), he must check sources before publishing.
7. Still to do in Supabase: run `migrations/003_admin_only_access.sql`; disable public sign-ups.

## Done during the handoff audit
- Build scripts are Windows-safe (LF line endings, no `%-d` date format); `.gitattributes` forces LF.
- `.gitignore` covers `review/`, `content/insights/_drafts/`, `preview-insight-*.html`, `tests/out/`, `*.xlsx`.
- `package.json` scripts point at the real build (the old npm minify/live-server scripts were wrong).
- Insights list date shown in Malaysia time (was a day early); Insights type filter no longer hides the "In the pipeline" cards; pipeline cards styled.

## Done after the handoff (5 November 2026, round 2 fixes)

All "Next fixes" from visitor test round 2 are in; `npm test` passes with no failures.
- Pre-filled WhatsApp text and email subject/body follow the page language: `js/i18n.js` translates `wa.me` / `mailto:` links from the dictionary (`<a data-msg="..." data-msg-tail="...">` for a sentence plus an untranslated tail, used on post pages). JS-built text uses `BKi18n.tr(en)`. Subjects now read "Quote request: <topic> – <company or name>", "Speaking enquiry: …", "Registration: <programme> – <city> – <company>".
- `?lang=en` now resets the saved language (it used to keep 中文 on the next page; this was the cause of the "CPD line" test failure). Textarea placeholders are translated.
- Form: email-only switches the reply to email (phone-only + email reply switches to WhatsApp); phone placeholder shows the country code; "Where are you or your business based?"; speaking topic has its own button label and subject; new topics `ja` (JA / appeal, Form Q) and `firm` (Accounting firm).
- Decoder: JA quote opens `topic=ja`; investigation WhatsApp wording fixed; free 15-minute call and outside-KL video line added. Who-we-help: firms card opens the form (FAQ link below the cards); "Senior review" opens audit; "Startup enquiry".
- Home: hats "Individual / landlord" and "Event or chamber organiser" (Book Keith to speak); "Sample screen" hidden on the live programme screen; assistant first menu has property tax and speaking, opens at the greeting; session lists, ribbon and home programme screen show the city; ribbon title translated.
- Layout: fee cards wrap amounts (no overflow at 1440 px); newsletter consent is one text block on phones; ribbon placeholder is inserted before the header loads (no jump) and tucks away on phone scroll; registration modal focuses the first invalid field.
- e-Invoice self-check: the "final_v3_REAL" result title is replaced.

Windows note: the folder name contains `&`, which breaks `npx` (.cmd shim). Use `node node_modules/playwright/cli.js install chromium`.

## Visitor test results (fictional personas; all 10 made contact both rounds)

| Persona | Round 1 | Round 2 |
|---|---|---|
| Penang restaurant owner, JA letter, 中文, phone | 8 | 8 |
| Construction subcontractor, BM, laptop | 7 | 7 |
| SaaS startup founder | 6 | 6 |
| Listed-group CFO, email only | 6 | 6 |
| Ipoh audit-firm partner, EN/中文 | 7 | 7 |
| HR manager, Kuching, iPad | 8 | 8 |
| Junior accountant, Puchong, phone | 7 | 8 |
| Retired landlord, 中文, large text | 6 | 6 |
| Singapore finance director, email only | 6 | 7 |
| Chamber programme manager, speaker booking | 7 | 7 |

Average 6.8 -> 7.0. What now limits scores is mostly the open questions above (proof, BM, missing prices, terms), not code.
