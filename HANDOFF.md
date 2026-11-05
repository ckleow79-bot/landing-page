# Handoff: B & K Group website (PR #3, branch `ccr-b2fa6464-hgxz8q`)

Status at 5 November 2026. Read this first in a new session, then continue with **Next fixes** below.

## Run it

```
git checkout ccr-b2fa6464-hgxz8q
python3 tools/bundle-css.py        # css/*.css -> css/site.css (pages load only site.css)
python3 tools/build-insights.py    # content/insights/*.md (published only) -> insight-*.html, data/insights.json, feed.xml
python3 -m http.server 5700        # http://localhost:5700
```

Netlify (project snazzy-choux-2ee2b7) runs both build steps; preview: https://deploy-preview-3--snazzy-choux-2ee2b7.netlify.app

## How the site is built

- Static HTML, vanilla JS, GSAP + ScrollTrigger + Lenis (js/vendor). Header, footer and assistant are loaded from `components/`.
- **Languages:** English source; `data/i18n/zh.json` and `data/i18n/ms.json` map English text to Chinese / Malay (`text` keys = text nodes, `html` keys = leaf blocks). Switch: `[data-lang-set]` buttons, stored in localStorage `bk-lang` or `?lang=ms|zh`. Never store a translation identical to its English key (it loops; i18n.js now guards this).
  New strings: run the server, then `node tools/i18n-collect.js out.json`, translate the missing keys into both files.
- **Forms** (js/supabase.js): always preventDefault; on failure `BKFormFallback` shows pre-filled WhatsApp / email buttons. Reply preference (WhatsApp / email / video / phone); phone OR email required.
- **Programmes:** Supabase with 1.5 s timeout, falls back to `data/programmes.json`.
- **Insights:** Markdown in `content/insights/` (see its README). Only `status: published` goes live. **The repo is public: do not commit drafts.**
- Tests used: Playwright scripts (regression + new-feature checks) against port 5700.

## Decisions Keith has made (do not re-ask)

- Prices approved, all **excl. 8% SST**, "final fee confirmed in an engagement letter after scoping": free 15-min call; 60-min consultation from RM 500 (credited if engaged); desk audit from RM 3,000; field audit from RM 8,000 (up to 3 years); investigation from RM 15,000 (quoted per case); Form Q / DRP from RM 5,000; e-Invoice health check from RM 2,500 (fixed); e-Invoice implementation from RM 6,000; Form C from RM 2,500/yr; management accounts review from RM 2,500/month; fractional CFO from RM 6,000/month; in-house training from RM 8,000/day (up to 25 pax).
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
6. Insights drafts (e-Invoice RM3m exemption, Budget 2027, *Kind Action* case note) were sent to Keith outside the repo; figures unverified, he must check sources before publishing.
7. Still to do in Supabase: run `migrations/003_admin_only_access.sql`; disable public sign-ups.

## Next fixes (from 10-visitor test round 2, no input needed)

- Every pre-filled WhatsApp/email text in the visitor's language (bottom action bar, menu/footer, contact page, FAQ, fee section "free 15-minute call", urgent-deadline link, post pages), and email subjects include topic + company (currently "Quote request: <name>" in English).
- 中文/BM leftovers: contact message placeholder; ribbon title "E-Invoice Latest Update" (consider per-language title in programmes.json).
- Form: if only email is filled, switch reply preference to email instead of erroring; phone placeholder not "+60"-only (foreign visitors); "Where is the business based?" should allow individuals; speaking topic gets its own submit label and email subject.
- New form topics: "JA / appeal (Form Q)" (decoder JA card should preselect it) and "Accounting firm"; the accounting-firms card on advisory.html#who should open the form (topic preselected), not only the FAQ. "Senior review" card should preselect audit/investigation, not M&A.
- Letter decoder cards: add "Clients outside KL served by video call, on site when needed" and the free 15-minute call line. Investigation WhatsApp text says "LHDN investigation letter from LHDN": fix wording.
- Home: add an "Individual / landlord" hat; assistant first menu should include property tax and speaking; assistant session buttons show the city (three e-Invoice dates look identical); ribbon shows the city too.
- Copy: "Startup package" -> "Startup enquiry"; e-Invoice self-check result must not show the "final_v3_REAL" joke out of context; "Sample screen" note under real programme dates.
- Layout: advisory.html#fees "CFO and training" card amounts overflow at 1440 px (allow wrap / wider min column); ribbon still pushes the header on first load on some pages (reserve height earlier or show without layout shift); newsletter consent label splits into columns on phones (index.html); programme registration modal: on empty submit, focus the first invalid field and keep the error in view; with large text, ribbon + header + action bar take too much height (hide ribbon on scroll on phones); assistant should open scrolled to the greeting.
- Make "Book Keith to speak" easier to find on the home page.

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
