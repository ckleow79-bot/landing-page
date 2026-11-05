/**
 * Cinematic motion layer
 * B & K Group Website
 *
 * Libraries (loaded via CDN before this file): GSAP 3 + ScrollTrigger, Lenis.
 * Everything degrades gracefully: if a library is missing or the visitor prefers
 * reduced motion, content is simply shown static.
 */
(function () {
    'use strict';

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hasGsap = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';
    const BK = window.BKMotion = { refresh: () => {}, lenis: null };

    if (!hasGsap || reduce) {
        document.documentElement.classList.remove('has-gsap');
        return;
    }

    document.documentElement.classList.add('has-gsap');
    gsap.registerPlugin(ScrollTrigger);

    /* ---------- Smooth scroll (Lenis) ---------- */
    if (typeof Lenis !== 'undefined' && window.innerWidth > 767) {
        const lenis = new Lenis({ lerp: 0.09, smoothWheel: true });
        BK.lenis = lenis;
        lenis.on('scroll', ScrollTrigger.update);
        gsap.ticker.add(t => lenis.raf(t * 1000));
        gsap.ticker.lagSmoothing(0);
        // anchor links
        document.addEventListener('click', e => {
            const a = e.target.closest('a[href^="#"]');
            if (!a || a.getAttribute('href') === '#') return;
            const el = document.querySelector(a.getAttribute('href'));
            if (!el) return;
            e.preventDefault();
            lenis.scrollTo(el, { offset: -80 });
        });
    }

    /* ---------- Film grain + cursor glow ---------- */
    if (!document.querySelector('.grain')) {
        const g = document.createElement('div'); g.className = 'grain'; document.body.appendChild(g);
    }
    if (window.matchMedia('(pointer: fine)').matches) {
        document.body.classList.add('has-pointer');
        const glow = document.createElement('div'); glow.className = 'cursor-glow'; document.body.appendChild(glow);
        const qx = gsap.quickTo(glow, 'x', { duration: 0.6, ease: 'power3' });
        const qy = gsap.quickTo(glow, 'y', { duration: 0.6, ease: 'power3' });
        window.addEventListener('pointermove', e => { qx(e.clientX); qy(e.clientY); }, { passive: true });
    }

    /* ---------- Hero ---------- */
    function initHero() {
        const hero = document.querySelector('.hero-cine');
        if (!hero) return;
        const h1 = hero.querySelector('h1');
        if (h1 && !h1.dataset.split) {
            h1.dataset.split = '1';
            h1.querySelectorAll('.line').forEach(line => {
                const html = line.innerHTML.trim();
                line.innerHTML = html.split(/(\s+)/).map(t => /^\s+$/.test(t) ? ' ' : (t.includes('<') ? t.replace(/>([^<]+)</g, (m, w) => '>' + w.split(' ').map(x => `<span class="word">${x}</span>`).join(' ') + '<') : `<span class="word">${t}</span>`)).join('');
            });
        }
        const tl = gsap.timeline({ defaults: { ease: 'power4.out' } });
        // "Open the books": two ledger covers swing open to reveal the room
        // the book opens once per visit; later home visits go straight to the headline
        let book = hero.querySelector('.book');
        let seen = false;
        try { seen = sessionStorage.getItem('bk-book') === '1'; sessionStorage.setItem('bk-book', '1'); } catch (e) { /* ignore */ }
        if (book && seen) { book.remove(); book = null; hero.classList.add('is-open'); }
        const o = book ? 1.0 : 0;
        if (book) {
            const L = book.querySelector('.book-l'), R = book.querySelector('.book-r');
            tl.from(book.querySelectorAll('.book-label'), { opacity: 0, y: 14, duration: 0.6, ease: 'power2.out' }, 0)
              .to(book.querySelectorAll('.book-clasp'), { scaleY: 0.2, opacity: 0, duration: 0.3, ease: 'back.in(2)' }, 0.25)
              .to(L, { rotateY: -100, xPercent: -6, duration: 1.2, ease: 'power3.inOut' }, 0.5)
              .to(R, { rotateY: 100, xPercent: 6, duration: 1.2, ease: 'power3.inOut' }, 0.5)
              .to(book.querySelectorAll('.book-cover'), { opacity: 0, duration: 0.35, ease: 'none' }, 1.3)
              .add(() => hero.classList.add('is-open'));
        }
        tl.from(hero.querySelectorAll('.hero-layer'), { opacity: 0, scale: 1.08, duration: 1.6, stagger: 0.1 }, o * 0.6)
          .from(hero.querySelector('.hero-kicker'), { y: 20, opacity: 0, duration: 0.8 }, 0.3 + o)
          .from(hero.querySelectorAll('h1 .word'), { yPercent: 110, opacity: 0, duration: 1.1, stagger: 0.045 }, 0.45 + o)
          .from(hero.querySelector('p.lead'), { y: 24, opacity: 0, duration: 0.9 }, 1.0 + o)
          .fromTo(hero.querySelectorAll('.hero-ctas .btn'), { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, stagger: 0.1 }, 1.15 + o)
          .from(hero.querySelector('.hero-scroll-cue'), { opacity: 0, duration: 0.8 }, 1.6 + o);

        // Parallax layers on scroll
        hero.querySelectorAll('.hero-layer').forEach((layer, i) => {
            gsap.to(layer, { yPercent: 12 + i * 8, ease: 'none', scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true } });
        });
        gsap.to(hero.querySelector('.hero-cine-content'), { yPercent: -10, opacity: 0.2, ease: 'none', scrollTrigger: { trigger: hero, start: '40% top', end: 'bottom top', scrub: true } });

        // Pointer tilt
        if (window.matchMedia('(pointer: fine)').matches) {
            const orbs = hero.querySelectorAll('.layer-orb, .layer-orb-2');
            hero.addEventListener('pointermove', e => {
                const r = hero.getBoundingClientRect();
                const dx = (e.clientX - r.left) / r.width - 0.5, dy = (e.clientY - r.top) / r.height - 0.5;
                orbs.forEach((o, i) => gsap.to(o, { x: dx * (40 + i * 30), y: dy * (30 + i * 20), duration: 1.2, ease: 'power2.out' }));
            }, { passive: true });
        }
    }

    /* ---------- Marquee ---------- */
    function initMarquee() {
        document.querySelectorAll('.marquee').forEach(m => {
            if (m.dataset.cloned) return;
            m.dataset.cloned = '1';
            m.innerHTML += m.innerHTML;
            const w = m.scrollWidth / 2;
            gsap.to(m, { x: -w, duration: Math.max(20, w / 60), ease: 'none', repeat: -1 });
        });
    }

    /* ---------- Pillars horizontal pin ---------- */
    function initPillars() {
        const section = document.querySelector('.pillars-pin');
        const track = section && section.querySelector('.pillars-track');
        if (!track) return;
        ScrollTrigger.matchMedia({
            '(min-width: 992px)': function () {
                const getX = () => -(track.scrollWidth - document.documentElement.clientWidth + 64);
                const tween = gsap.to(track, {
                    x: getX, ease: 'none',
                    scrollTrigger: {
                        trigger: section, pin: true, scrub: 0.6, start: 'top top',
                        end: () => '+=' + (track.scrollWidth - document.documentElement.clientWidth + 64),
                        invalidateOnRefresh: true, anticipatePin: 1,
                        onUpdate: self => { const bar = section.querySelector('.pillars-progress i'); if (bar) bar.style.width = (self.progress * 100) + '%'; }
                    }
                });
                track.querySelectorAll('.pillar').forEach(p => {
                    gsap.from(p, { scale: 0.92, opacity: 0.4, ease: 'none', scrollTrigger: { trigger: p, containerAnimation: tween, start: 'left 90%', end: 'left 55%', scrub: true } });
                });
            }
        });
    }

    /* ---------- Counters ----------
     * Big numbers count up from zero when they scroll into view. The real figure
     * is in the HTML so it shows without JS or with reduced motion. Each card in a
     * .numbers-grid also draws an amber rule and lifts its label, staggered. */
    function initCounters() {
        const fmt = (v, dec) => v.toLocaleString('en-MY', { maximumFractionDigits: dec, minimumFractionDigits: dec });
        function run(el, delay) {
            const target = parseFloat(el.dataset.count);
            if (isNaN(target)) return;
            const dec = (el.dataset.decimals | 0), obj = { v: 0 };
            el.dataset.counting = '1';
            el.textContent = fmt(0, dec);
            gsap.fromTo(el, { filter: 'blur(6px)', opacity: 0.35 }, { filter: 'blur(0px)', opacity: 1, duration: 0.9, delay, ease: 'power2.out' });
            gsap.to(obj, { v: target, duration: 2.2, delay, ease: 'expo.out', onUpdate: () => { el.textContent = fmt(obj.v, dec); }, onComplete: () => { el.textContent = fmt(target, dec); } });
        }
        document.querySelectorAll('.numbers-grid').forEach(grid => {
            const cards = grid.querySelectorAll('.number');
            grid.classList.add('is-counting');
            // the real figures stay visible until the grid scrolls in, then count up from zero
            ScrollTrigger.create({
                trigger: grid, start: 'top 82%', once: true,
                onEnter: () => cards.forEach((c, i) => {
                    const d = i * 0.16;
                    setTimeout(() => c.classList.add('is-in'), d * 1000);
                    c.querySelectorAll('[data-count]').forEach(el => run(el, d));
                })
            });
        });
        // stray counters outside a numbers grid
        document.querySelectorAll('[data-count]').forEach(el => {
            if (el.closest('.numbers-grid')) return;
            ScrollTrigger.create({ trigger: el, start: 'top 85%', once: true, onEnter: () => run(el, 0) });
        });
    }

    /* ---------- Sticky story ---------- */
    function initStory() {
        const steps = document.querySelectorAll('.story-step');
        steps.forEach(step => {
            ScrollTrigger.create({
                trigger: step, start: 'top 60%', end: 'bottom 40%',
                onToggle: self => step.classList.toggle('is-active', self.isActive)
            });
        });
        if (steps[0]) steps[0].classList.add('is-active');
    }

    /* ---------- Timeline ---------- */
    function initTimeline() {
        const tl = document.querySelector('.tl');
        if (!tl) return;
        const bar = tl.querySelector('.tl-line i');
        if (bar) gsap.to(bar, { height: '100%', ease: 'none', scrollTrigger: { trigger: tl, start: 'top 60%', end: 'bottom 60%', scrub: 0.4 } });
        tl.querySelectorAll('.tl-item').forEach(item => {
            ScrollTrigger.create({ trigger: item, start: 'top 62%', end: 'bottom 30%', onToggle: self => item.classList.toggle('is-active', self.isActive) });
        });
    }

    /* ---------- Generic reveals ---------- */
    function initReveals() {
        document.querySelectorAll('.reveal:not([data-revealed]), .reveal-up:not([data-revealed])').forEach(el => {
            el.dataset.revealed = '1';
            gsap.to(el, { y: 0, opacity: 1, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%', once: true } });
        });
        document.querySelectorAll('.reveal-stagger:not([data-revealed])').forEach(group => {
            group.dataset.revealed = '1';
            gsap.to(group.children, { y: 0, opacity: 1, duration: 0.9, ease: 'power3.out', stagger: 0.08, scrollTrigger: { trigger: group, start: 'top 85%', once: true } });
        });
    }

    /* ---------- Magnetic buttons ---------- */
    function initMagnetic() {
        if (!window.matchMedia('(pointer: fine)').matches) return;
        document.querySelectorAll('.btn-magnetic:not([data-mag])').forEach(btn => {
            btn.dataset.mag = '1';
            const xTo = gsap.quickTo(btn, 'x', { duration: 0.5, ease: 'power3' });
            const yTo = gsap.quickTo(btn, 'y', { duration: 0.5, ease: 'power3' });
            btn.addEventListener('pointermove', e => {
                const r = btn.getBoundingClientRect();
                xTo((e.clientX - r.left - r.width / 2) * 0.3);
                yTo((e.clientY - r.top - r.height / 2) * 0.3);
            });
            btn.addEventListener('pointerleave', () => { xTo(0); yTo(0); });
        });
    }

    /* ---------- Header colour swap on dark/light sections ---------- */
    function initHeaderTheme() {
        const header = () => document.querySelector('.header');
        document.querySelectorAll('[data-theme-dark]').forEach(sec => {
            ScrollTrigger.create({
                trigger: sec, start: 'top 80px', end: 'bottom 80px',
                onToggle: self => { const h = header(); if (h) h.classList.toggle('on-dark', self.isActive); }
            });
        });
    }

    BK.refresh = function () {
        initReveals(); initMagnetic();
        ScrollTrigger.refresh();
    };

    document.querySelectorAll('.page-hero-cine.has-photo').forEach(h => { const img = h.querySelector('.hero-photo img'); const done = () => h.classList.add('is-loaded'); if (img && !img.complete) img.addEventListener('load', done); else done(); });

    function boot() {
        initHero(); initMarquee(); initPillars(); initCounters(); initStory(); initTimeline(); initReveals(); initMagnetic();
        // components (header/footer) are injected async; re-scan when they land
        const obs = new MutationObserver(() => { initMagnetic(); });
        obs.observe(document.body, { childList: true, subtree: true });
        window.addEventListener('load', () => ScrollTrigger.refresh());
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
