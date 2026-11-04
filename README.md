# B & K Group Website

Static, motion-rich marketing site for **B & K Group** (Kuala Lumpur) at bkcorporate.com: B & K Advisory PLT, B & K Academy PLT and B & K Training Services PLT, with public seminars run alongside training partner High Impact Training Services. Includes a data-driven seminar / programme calendar with online registration, and a `dashboard/` folder scaffolding the group's live finance dashboard.

## Run locally
```bash
npm install
npm start          # http://localhost:5500
npm run build      # minified CSS/JS bundles
```

## Brand
The site implements the **B&K Academy Design System** (`ckleow79-bot/bk-academy-design-system`). Tokens, signature moves and self-hosted fonts are vendored under `css/tokens/` and `assets/fonts/`; the Ascend logo set is in `assets/brand/`. `css/brand.css` maps the components onto the system. Change the brand in the design-system repo, then re-copy the token files.

## Stack
- HTML/CSS/vanilla JS. Type: Bricolage Grotesque, Public Sans, JetBrains Mono (self-hosted). Motion: GSAP 3 + ScrollTrigger + Lenis, self-hosted in `js/vendor/`. Degrades to static content when JS is unavailable or `prefers-reduced-motion` is set.
- Supabase: contact form, newsletter, chatbot transcripts, **programmes** and **programme_registrations** (see `migrations/`).
- Programme calendar reads Supabase first and falls back to `data/programmes.json`.

## Pages
`index.html` · `advisory.html` · `academy.html` · `programmes.html` · `insights.html` · `about.html` · `contact.html` · legal pages

## Publishing a new seminar
Real programme data comes from the Drive sheet "KEITH'S TRAINING SCHEDULE". Third-party guest-speaking slots use `provider: external` with an `organiser`.

Insert a row in the Supabase `programmes` table (or add an object to `data/programmes.json`). Required: `slug`, `title`, `provider` (`bk-training` | `high-impact` | `bk-academy`), `category`, `start_date`. Optional fee, early-bird, CPD hours, HRD Corp flag, highlights, brochure and external register URL.

## Finance dashboard
See `dashboard/README.md` for the Supabase warehouse schema, role-based RLS (owner / board / finance), AutoCount Cloud and on-premise ingestion, and Metabase setup.

## Before go-live
See the checklist in `AGENTS.md` (placeholders for address, phone, registration numbers, domain, GA4 ID, brand colours).
