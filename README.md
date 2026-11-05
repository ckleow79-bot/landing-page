# B & K Group Website

Static, motion-rich marketing site for **B & K Group** (Kuala Lumpur) at bkcorporate.com: B & K Advisory PLT, B & K Academy PLT and B & K Training Services PLT, with public seminars run alongside training partner High Impact Training Services. Includes a data-driven seminar / programme calendar with online registration, and a `dashboard/` folder scaffolding the group's live finance dashboard.

## Run locally
```bash
npm start          # python3 -m http.server 5700  ->  http://localhost:5700
npm run build      # css/site.css + Insights pages, data/insights.json, feed.xml
npm install && npx playwright install chromium   # once, for the tests
npm test           # regression + feature checks (needs npm start running)
```
Windows: if `python3` is not found, run `python -m http.server 5700`, `python tools/bundle-css.py` and `python tools/build-insights.py` directly.

**Continuing development:** read `CLAUDE.md` and `HANDOFF.md` first.

## Brand
The site implements the **B&K Academy Design System** (`ckleow79-bot/bk-academy-design-system`). Tokens, signature moves and self-hosted fonts are vendored under `css/tokens/` and `assets/fonts/`; the Ascend logo set is in `assets/brand/`. `css/brand.css` maps the components onto the system. Change the brand in the design-system repo, then re-copy the token files.

## Stack
- HTML/CSS/vanilla JS. Type: Bricolage Grotesque, Public Sans, JetBrains Mono (self-hosted). Motion: GSAP 3 + ScrollTrigger + Lenis, self-hosted in `js/vendor/`. Degrades to static content when JS is unavailable or `prefers-reduced-motion` is set.
- Supabase: contact form, newsletter, chatbot transcripts, **programmes** and **programme_registrations** (see `migrations/`).
- Programme calendar reads Supabase first and falls back to `data/programmes.json`.

## Pages
`index.html` · `advisory.html` · `academy.html` · `programmes.html` · `insights.html` · `about.html` · `faq.html` · `contact.html` (Request a quote, service area, click-to-load map) · legal pages

## Publishing a new seminar
Real programme data comes from the Drive sheet "KEITH'S TRAINING SCHEDULE". Third-party guest-speaking slots use `provider: external` with an `organiser`.

Insert a row in the Supabase `programmes` table (or add an object to `data/programmes.json`). Required: `slug`, `title`, `provider` (`bk-training` | `high-impact` | `bk-academy`), `category`, `start_date`. Optional fee, early-bird, CPD hours, HRD Corp flag, highlights, brochure and external register URL.

The next upcoming B & K / High Impact programme also appears in the amber ribbon above the header on every page (`js/next-ribbon.js`); guest-speaking slots are left out. It updates itself from the same data.

## English / Bahasa Malaysia / 中文
Every page has an EN / BM / 中文 switch in the header (`js/i18n.js`). English in the HTML is the source; `data/i18n/zh.json` and `data/i18n/ms.json` map each English string to Simplified Chinese and Malay. Never store a translation identical to its English key. A string with no translation simply stays in English. Programme titles, subtitles and highlights stay in English on purpose (the sessions are delivered in English).

After changing page text:
1. `npm start`, then `node tools/i18n-collect.js new-keys.json` lists every string on the main pages.
2. Add the new or changed strings to `data/i18n/zh.json` and `data/i18n/ms.json` (`text` for plain strings, `html` for sentences that contain a link or highlight; keep the tags).
3. Have the Chinese and Malay reviewed before publishing.

## Motion
`js/motion.js` adds page-to-page wipes, a scroll progress line, headings that rise word by word, card tilt, photo parallax and receipt confetti on a 6/6 self-check. All of it is skipped for visitors with "reduce motion" switched on.

**Hero video:** put a short silent clip at `assets/video/hero.mp4` (10 to 20 s, 1920 px wide, under 6 MB, faces of participants blurred) and add `data-video="assets/video/hero.mp4"` to the `<section class="hero-cine">` in `index.html`. It plays over the photo on desktop only.

## Styles, icons and images
- **Styles:** pages load one file, `css/site.css`, built from the sources in `css/`. After editing any CSS, run `python3 tools/bundle-css.py` (Netlify also runs it on every deploy).
- **Icons:** self-hosted SVG sprite in `assets/icons/sprite.svg` (Lucide, ISC licence; Simple Icons for social logos). Use `<svg class="ic"><use href="assets/icons/sprite.svg#NAME"></use></svg>`; `js/icons.js` converts any old `<i class="fas fa-NAME">` added by scripts.
- **Photos:** each training photo has `.avif` and `.webp` versions (1600 px and 800 px); `<picture>` serves AVIF where supported.

## Finance dashboard
See `dashboard/README.md` for the Supabase warehouse schema, role-based RLS (owner / board / finance), AutoCount Cloud and on-premise ingestion, and Metabase setup.

## Insights (tax updates, case notes)
Markdown posts in `content/insights/` (see its README). Only `status: published` posts are built. Keep drafts in `content/insights/_drafts/` (git-ignored) because this repository is public.

## Before go-live
See `HANDOFF.md` (open questions, Supabase steps). Older planning documents (`PROJECT_PLAN.md`, `FINAL_STATUS.md`, `QUICKSTART.md` and others) describe the original template and are out of date.
