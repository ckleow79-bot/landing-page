# AGENTS.md

> **Partly out of date.** For current commands, decisions and rules read `CLAUDE.md` and `HANDOFF.md`, which take precedence. Analytics (GA4) and Google Fonts are no longer used except Noto Sans SC in 中文 mode; styles are bundled into `css/site.css`; the local server runs on port 5700.

## Project Information
- **Project Name**: B & K Group Website (Advisory, Academy, Programme Calendar) + Finance Dashboard data layer
- **Type**: Static HTML/CSS/JS Website with Supabase Backend; `dashboard/` holds the separate finance-dashboard scaffold
- **Framework**: Vanilla JavaScript. Motion: GSAP 3 + ScrollTrigger + Lenis (vendored in `js/vendor/`), Anime.js for legacy micro-interactions
- **Backend**: Supabase (PostgreSQL + Auth + Realtime)

## Development Commands

### Start Development Server
```bash
npm start
# python3 -m http.server 5700  ->  http://localhost:5700
```

### Build for Production
```bash
npm run build
# css/site.css bundle + Insights pages (tools/bundle-css.py, tools/build-insights.py)
```

### Optimize Images
```bash
npm run optimize:images
# Compresses images in assets/images/
```

## Project Structure
```
landing-page/
├── index.html          # Group home (cinematic hero, pinned pillars, programmes strip)
├── advisory.html       # B & K Advisory PLT services
├── academy.html        # B & K Academy PLT curriculum
├── programmes.html     # Seminar / programme calendar + registration (data-driven)
├── insights.html       # Articles
├── about.html, contact.html, legal pages, 404/500
├── css/
│   ├── main.css        # Variables (navy / gold / teal), base, header, footer
│   ├── pages.css, responsive.css, animations.css, chatbot.css
│   └── cinematic.css   # Hero, pillars, numbers, story, programme cards, modal
├── js/
│   ├── cinematic.js    # GSAP/ScrollTrigger/Lenis layer; respects prefers-reduced-motion
│   ├── programmes.js   # Loads programmes (Supabase -> data/programmes.json fallback), modal, ICS
│   ├── supabase.js     # Client init, contact + newsletter forms
│   ├── chatbot.js, animations.js, main.js
│   └── vendor/         # gsap, ScrollTrigger, lenis, anime, supabase (self-hosted)
├── data/programmes.json   # Seed / fallback programme list (edit to publish without Supabase)
├── migrations/            # Supabase SQL: 001 contact, 002 programmes + registrations
├── components/            # header.html, footer.html, chatbot.html
├── dashboard/             # Finance dashboard: Supabase schema, RLS, views, ingestion, Metabase
└── structured-data/, sitemap.xml, robots.txt
```

## Updating the programme calendar
1. **Preferred**: insert/edit rows in the Supabase `programmes` table (apply `migrations/002_programmes.sql` first). `published = true` rows show on the site immediately.
2. **Fallback**: edit `data/programmes.json` and deploy. Used automatically when Supabase is unreachable or the table is empty.
Registrations land in `programme_registrations` (anon insert requires `consent_pdpa = true`).
3. **Where the real list comes from**: the Drive sheet "KEITH'S TRAINING SCHEDULE" (2026/2027 tabs) and the Pipeline sheet. Only confirmed sessions go on the site. Use `provider: external` plus `organiser` for guest-speaking slots run by third parties (CPA Australia, Symphony Digest, eData Systems); fees and registration then stay with the organiser.
4. **Never claim** CPD hours or HRD Corp claimability for a programme unless confirmed in writing.

## Key Features

### 1. Responsive Design
- Breakpoints: 1200px, 991px, 767px, 480px
- Mobile-first approach
- Hamburger menu on mobile
- Touch-friendly tap targets (min 44px)

### 2. Motion (GSAP + ScrollTrigger + Lenis, js/cinematic.js)
- Hero word reveal, parallax layers, pointer-reactive orbs
- Pinned horizontal 'pillars' track (desktop), stacked on mobile
- Counters, sticky story steps, staggered reveals, magnetic CTAs, film grain
- Disabled under prefers-reduced-motion; content fully visible without JS

### 3. Supabase Integration
- Contact form submissions
- Newsletter subscriptions
- Chat conversation storage
- Row Level Security (RLS) enabled

### 4. Chatbot
- Floating chat interface
- Quick reply options
- Conversation flow logic
- Email capture for offline mode
- Local storage + Supabase sync

### 5. Deployment config
- `netlify.toml`: clean URLs, 301s from the old template pages, 404 for `/dashboard/*`, `/migrations/*` and `*.md`, security headers incl. CSP (allows Supabase, GA4, Google Fonts, cdnjs Font Awesome), long cache for `js/vendor/*`.
- Pages added from the 29 Oct outline: visitor paths on Home (`.paths`), "My Story" scroll timeline on About (`#story`).

### 6. SEO
- Semantic HTML5
- Meta tags on all pages
- Open Graph tags
- XML sitemap
- Robots.txt
- Canonical URLs

## CSS Variables (Main Colors)
```css
/* aliases in css/main.css -> design-system tokens in css/tokens/colors.css */
--primary-color: var(--bk-blue);     /* #3457E5 brand blue */
--primary-dark:  var(--bk-ink);      /* #15213B deep navy ink */
--secondary-color: var(--bk-amber);  /* #FFB23E fills only */
--accent-color:  var(--bk-teal);     /* #15B5A6 */
--bg-primary:    var(--surface-page);/* #FCFBF8 warm paper */
```

## Important Files to Update

### Before Launch:
1. **js/supabase.js**: confirm Supabase URL/anon key; apply `migrations/001` and `002`
2. **HRD Corp TP registration for B & K Training Services PLT: serial LLP0046779LGN, approved 29 Oct 2026, expires 28 Oct 2027 (renewal reminder).
3. **Domain**: `bkcorporate.com` is a placeholder in canonical/OG tags, sitemap.xml, robots.txt, structured-data/
4. **Brand**: the B&K Academy Design System (repo `ckleow79-bot/bk-academy-design-system`) is the source of truth. Tokens are vendored in `css/tokens/` (colors, typography, spacing, fonts, theme-dark, signature); fonts self-hosted in `assets/fonts/`; Ascend logo set in `assets/brand/`. Site variables in `css/main.css` are aliases onto those tokens. Rules: paper `#FCFBF8` not white, ink `#15213B` for text, brand blue `#3457E5` as the only action colour, amber is fill-only (amber text uses `--bk-warning`), max 2 signature moves per view, sentence case for headings and buttons, no heavy gradients.

5. **assets/images/**: replace placeholder `logo.png`; add `og-image.jpg` (1200x630), `favicon.ico`, leadership photo
6. **GA4**: replace `GA_MEASUREMENT_ID` in every page head

### SEO Configuration:
- Update Open Graph image URLs
- Add Google Analytics tracking code
- Set up Google Search Console
- Create and submit XML sitemap

## Testing Checklist

### Functionality:
- [ ] All navigation links work
- [ ] Contact forms submit to Supabase
- [ ] Newsletter subscription works
- [ ] Chatbot opens/closes and flows work
- [ ] Mobile menu toggles correctly
- [ ] Scroll animations trigger properly
- [ ] Testimonials carousel works

### Responsive:
- [ ] Test on desktop (1920px, 1440px, 1280px)
- [ ] Test on tablet (991px, 768px)
- [ ] Test on mobile (767px, 480px, 375px)
- [ ] Touch targets are adequate
- [ ] Text is readable at all sizes

### Performance:
- [ ] Images are optimized (< 200KB each)
- [ ] CSS is minified for production
- [ ] JS is minified for production
- [ ] Lazy loading works on images
- [ ] Page load < 3 seconds

### Accessibility:
- [ ] All images have alt text
- [ ] Form labels are present
- [ ] Focus indicators visible
- [ ] Keyboard navigation works
- [ ] Color contrast meets WCAG AA

## Deployment

### Static Hosting (Recommended):
1. **Netlify**: Drag and drop folder
2. **Vercel**: Connect GitHub repo
3. **Cloudflare Pages**: Connect repo
4. **GitHub Pages**: Enable in settings

### Traditional Hosting:
1. Upload all files via FTP
2. Ensure .htaccess is uploaded
3. Configure SSL certificate
4. Test all forms and functionality

## Post-Launch:
1. Set up Google Analytics 4
2. Configure Google Search Console
3. Submit sitemap to Google
4. Test all contact forms receive data
5. Monitor Supabase usage
6. Set up uptime monitoring

## Troubleshooting

### Common Issues:

**Forms not submitting:**
- Check Supabase URL and key in js/supabase.js
- Verify RLS policies are enabled
- Check browser console for errors

**Animations not working:**
- Ensure js/vendor/gsap.min.js, ScrollTrigger.min.js and lenis.min.js load (check Network tab)
- Check for JavaScript errors in console
- Verify CSS animations file is linked

**Chatbot not opening:**
- Check chatbot.js is loaded
- Verify chatbot.html component exists
- Check z-index values

**Mobile menu not working:**
- Verify main.js is loaded
- Check for JavaScript errors
- Test on actual mobile device

## Contact
For questions about this project, refer to:
- README.md for general info
- SUPABASE_SETUP.md for database setup
- PROGRESS_PLAN.md for development roadmap