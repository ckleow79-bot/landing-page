/**
 * Motion layer: playful, site-wide movement on top of cinematic.js.
 *   - page transitions (ink + amber wipe between pages)
 *   - scroll progress line at the very top
 *   - headings rise word by word as they scroll in (per character in Chinese)
 *   - cards tilt toward the pointer with a soft glare
 *   - photos drift slowly against the scroll (parallax)
 *   - window.BKConfetti(): receipts and coins rain down (used on a 6/6 check)
 * Everything is skipped under prefers-reduced-motion; content never depends on it.
 */
(function () {
    'use strict';
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fine = window.matchMedia('(pointer: fine)').matches;
    const hasGsap = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';
    const root = document.documentElement;
    const WIPE = 'bk-wipe';

    /* ---------- Page transitions ---------- */
    function initTransitions() {
        const wipe = document.createElement('div');
        wipe.className = 'page-wipe';
        wipe.setAttribute('aria-hidden', 'true');
        wipe.innerHTML = '<span class="pw-a"></span><span class="pw-b"><img src="assets/brand/mark-white.svg" alt="" width="64" height="64"></span>';
        document.body.appendChild(wipe);

        // arriving: the panels that cover the page slide away
        if (root.classList.contains('wipe-in')) {
            try { sessionStorage.removeItem(WIPE); } catch (e) { /* ignore */ }
            requestAnimationFrame(() => requestAnimationFrame(() => {
                root.classList.add('wipe-out');
                setTimeout(() => root.classList.remove('wipe-in', 'wipe-out'), 900);
            }));
        }
        if (reduce) return;

        document.addEventListener('click', e => {
            if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            const a = e.target.closest('a[href]');
            if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
            const url = new URL(a.href, location.href);
            if (url.origin !== location.origin || !/\.html$|\/$/.test(url.pathname)) return;
            if (url.pathname === location.pathname && url.search === location.search) return; // same page / anchors
            e.preventDefault();
            try { sessionStorage.setItem(WIPE, '1'); } catch (err) { /* ignore */ }
            root.classList.add('wipe-leave');
            setTimeout(() => { location.href = url.href; }, 280);
        });
        // back/forward cache: never come back to a covered page
        window.addEventListener('pageshow', ev => { if (ev.persisted) root.classList.remove('wipe-leave', 'wipe-in', 'wipe-out'); });
    }

    /* ---------- Scroll progress ---------- */
    function initProgress() {
        const bar = document.createElement('div');
        bar.className = 'scroll-progress';
        bar.setAttribute('aria-hidden', 'true');
        document.body.appendChild(bar);
        let ticking = false;
        const update = () => {
            const max = document.documentElement.scrollHeight - innerHeight;
            bar.style.transform = `scaleX(${max > 0 ? Math.min(1, scrollY / max) : 0})`;
            ticking = false;
        };
        window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
        update();
    }

    /* ---------- Headings rise word by word ---------- */
    const HEADINGS = [
        'main .section-title', 'main .flow-head h2', 'main .hats-head h2', 'main .ac-head h2', 'main .faq-cta h2',
        'main .sa-copy h2', 'main .cta-cine h2', 'main .at-copy h2', 'main .in-room h2', 'main .story-sticky h2', 'main .numbers h2'
    ].join(',');
    const TOKEN = /[㐀-鿿豈-﫿][　-〿＀-￯]*|[^\s㐀-鿿豈-﫿]+|\s+/g;
    function splitHeading(h) {
        if (h.dataset.split || h.classList.contains('reveal-up')) return;
        h.dataset.split = '1';
        let n = 0;
        const walk = node => {
            [...node.childNodes].forEach(c => {
                if (c.nodeType === 3) {
                    const parts = c.nodeValue.match(TOKEN);
                    if (!parts) return;
                    const frag = document.createDocumentFragment();
                    parts.forEach(t => {
                        if (/^\s+$/.test(t)) { frag.appendChild(document.createTextNode(' ')); return; }
                        const w = document.createElement('span'); w.className = 'mw';
                        const i = document.createElement('span'); i.className = 'mw-i'; i.style.setProperty('--w', n++); i.textContent = t;
                        w.appendChild(i); frag.appendChild(w);
                    });
                    c.replaceWith(frag);
                } else if (c.nodeType === 1 && !/^(BR|SVG|I)$/i.test(c.tagName)) walk(c);
            });
        };
        walk(h);
        h.classList.add('mw-split');
    }
    function initHeadings(io) {
        document.querySelectorAll(HEADINGS).forEach(h => { splitHeading(h); if (h.classList.contains('mw-split')) io.observe(h); });
    }

    /* ---------- Cards: reveal + tilt ---------- */
    const CARDS = '.service-card, .path-card, .at-card, .faq-item, .contact-item, .tl-card, .sa-map, .ac-card, .pillar-card, .pillar';
    function initCards(io) {
        document.querySelectorAll(CARDS).forEach((c, i) => {
            if (c.closest('.reveal-stagger') || c.classList.contains('reveal-up') || c.dataset.mv) return;
            c.dataset.mv = '1';
            c.style.setProperty('--d', (i % 4) * 70 + 'ms');
            c.classList.add('mv-card');
            io.observe(c);
        });
        if (!fine) return;
        document.querySelectorAll('.service-card, .path-card, .at-card, .prog-card, .faq-item:not([open]), .hats-phone, .rr-card, .pillar').forEach(addTilt);
        // programme cards are rendered later
        new MutationObserver(() => document.querySelectorAll('.prog-card:not([data-tilt])').forEach(addTilt))
            .observe(document.body, { childList: true, subtree: true });
    }
    function addTilt(el) {
        if (el.dataset.tilt) return;
        el.dataset.tilt = '1';
        el.classList.add('tilt');
        const max = el.classList.contains('hats-phone') ? 6 : 5;
        let raf = 0;
        el.addEventListener('pointermove', e => {
            const r = el.getBoundingClientRect();
            const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
            cancelAnimationFrame(raf);
            raf = requestAnimationFrame(() => {
                el.style.setProperty('--mx', (x * 100).toFixed(1) + '%');
                el.style.setProperty('--my', (y * 100).toFixed(1) + '%');
                el.style.transform = `perspective(900px) rotateX(${((0.5 - y) * max).toFixed(2)}deg) rotateY(${((x - 0.5) * max).toFixed(2)}deg) translateY(-4px)`;
            });
        });
        el.addEventListener('pointerleave', () => { cancelAnimationFrame(raf); el.style.transform = ''; });
    }

    /* ---------- Photo parallax ---------- */
    function initParallax() {
        if (!hasGsap) return;
        gsap.registerPlugin(ScrollTrigger);
        document.querySelectorAll('.ir-grid figure img, .ir-grid .ir-item img, .page-hero-cine.has-photo .hero-photo').forEach(img => {
            if (img.dataset.px) return;
            img.dataset.px = '1';
            const hero = img.classList.contains('hero-photo');
            gsap.fromTo(img, { yPercent: hero ? 0 : -7, scale: hero ? 1 : 1.16 }, {
                yPercent: hero ? 14 : 7, scale: hero ? 1 : 1.16, ease: 'none',
                scrollTrigger: { trigger: hero ? img.closest('section') : img, start: hero ? 'top top' : 'top bottom', end: 'bottom top', scrub: true }
            });
        });
    }

    /* ---------- Receipt confetti ---------- */
    window.BKConfetti = function (origin) {
        if (reduce || !document.body.animate) return;
        const r = origin ? origin.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 3, width: 0, height: 0 };
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const layer = document.createElement('div');
        layer.className = 'confetti-layer';
        layer.setAttribute('aria-hidden', 'true');
        document.body.appendChild(layer);
        const kinds = ['cf-receipt', 'cf-receipt', 'cf-coin', 'cf-tick', 'cf-receipt', 'cf-coin'];
        for (let i = 0; i < 34; i++) {
            const p = document.createElement('span');
            p.className = 'cf ' + kinds[i % kinds.length];
            if (p.classList.contains('cf-coin')) p.textContent = 'RM';
            layer.appendChild(p);
            const ang = (-90 + (Math.random() - 0.5) * 140) * Math.PI / 180;
            const pow = 260 + Math.random() * 320;
            const dx = Math.cos(ang) * pow, dy = Math.sin(ang) * pow;
            const fall = innerHeight - cy + 120 + Math.random() * 200;
            const spin = (Math.random() - 0.5) * 900;
            p.animate([
                { transform: `translate(${cx}px, ${cy}px) rotate(0deg) scale(.6)`, opacity: 1 },
                { transform: `translate(${cx + dx}px, ${cy + dy}px) rotate(${spin / 2}deg) scale(1)`, opacity: 1, offset: 0.35 },
                { transform: `translate(${cx + dx * 1.3}px, ${cy + fall}px) rotate(${spin}deg) scale(1)`, opacity: 0 }
            ], { duration: 1700 + Math.random() * 900, easing: 'cubic-bezier(.2,.6,.3,1)', fill: 'forwards' });
        }
        setTimeout(() => layer.remove(), 2900);
    };

    /* ---------- Hero video (optional) ----------
     * Add data-video="assets/video/hero.mp4" to .hero-cine to play a silent loop over the
     * photo. Skipped on data-saver, reduced motion and small screens; the photo stays as poster. */
    function initHeroVideo() {
        const hero = document.querySelector('.hero-cine[data-video]');
        const slot = hero && hero.querySelector('.layer-photo');
        const saver = navigator.connection && navigator.connection.saveData;
        if (!slot || saver || innerWidth < 768) return;
        const v = document.createElement('video');
        v.muted = true; v.loop = true; v.playsInline = true; v.autoplay = true; v.preload = 'metadata';
        v.setAttribute('aria-hidden', 'true');
        const img = slot.querySelector('img'); if (img) v.poster = img.currentSrc || img.src;
        v.src = hero.dataset.video;
        v.addEventListener('canplay', () => { slot.innerHTML = ''; slot.appendChild(v); v.play().catch(() => {}); }, { once: true });
        v.load();
    }

    /* clients bar pause button (WCAG 2.2.2) */
    function initClientsBar() {
        document.querySelectorAll('.clients-bar').forEach(bar => {
            const b = bar.querySelector('.cb-pause');
            if (!b) return;
            b.addEventListener('click', () => {
                const paused = bar.classList.toggle('is-paused');
                b.setAttribute('aria-pressed', paused ? 'true' : 'false');
                b.textContent = paused ? (window.BKi18n && BKi18n.lang === 'zh' ? '播放' : 'Play') : (window.BKi18n && BKi18n.lang === 'zh' ? '暂停' : 'Pause');
            });
        });
    }

    /* arriving with #section from another page: pinned sections and late layout can leave
       the browser at the top, so scroll to the target once the page has settled */
    function initHashLanding() {
        if (!location.hash || location.hash.length < 2) return;
        let target;
        try { target = document.querySelector(location.hash); } catch (e) { return; }
        if (!target) return;
        const go = () => {
            if (window.ScrollTrigger) ScrollTrigger.refresh();
            const offset = (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--ribbon-h'), 10) || 0) + 96;
            const y = target.getBoundingClientRect().top + window.scrollY - offset;
            if (window.BKMotion && window.BKMotion.lenis) window.BKMotion.lenis.scrollTo(y, { immediate: true });
            else window.scrollTo(0, y);
        };
        // aim again after late images and pinned sections settle, unless the visitor has started scrolling
        let userMoved = false;
        ['wheel', 'touchstart', 'keydown', 'mousedown', 'hashchange'].forEach(ev => window.addEventListener(ev, () => { userMoved = true; }, { once: true, passive: true }));
        const run = () => { [450, 1300, 2600].forEach(t => setTimeout(() => { if (!userMoved) go(); }, t)); };
        if (document.readyState === 'complete') run(); else window.addEventListener('load', run, { once: true });
    }

    function boot() {
        initHashLanding();
        initClientsBar();
        initTransitions();
        if (reduce) return;
        initHeroVideo();
        initProgress();
        const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } }), { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
        initHeadings(io);
        // trust-strip marquee pauses on hover / focus (WCAG 2.2.2)
        if (hasGsap) document.querySelectorAll('.trust-strip').forEach(ts => {
            const m = ts.querySelector('.marquee');
            const set = p => gsap.getTweensOf(m).forEach(t => (p ? t.pause() : t.resume()));
            ts.addEventListener('mouseenter', () => set(true)); ts.addEventListener('mouseleave', () => set(false));
            ts.addEventListener('focusin', () => set(true)); ts.addEventListener('focusout', () => set(false));
        });
        initCards(io);
        initParallax();
        if (hasGsap) ScrollTrigger.refresh();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0)); else setTimeout(boot, 0);
})();
