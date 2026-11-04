/**
 * Audit story (advisory.html), readiness check (advisory.html) and home teaser (index.html).
 * Story: one GSAP timeline, scrubbed by a pinned ScrollTrigger, five labelled scenes.
 * Falls back to a static "tidy ending" + caption list without GSAP or with reduced motion.
 */
(function () {
    'use strict';

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hasGsap = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';

    /* ------------------------------------------------------------------ */
    /* Story                                                               */
    /* ------------------------------------------------------------------ */
    function sizeLabels(section) {
        section.querySelectorAll('.as-lab').forEach(g => {
            const cx = +g.dataset.cx, tx = g.querySelector('.as-lab-tx'), bg = g.querySelector('.as-lab-bg'), ic = g.querySelector('.as-lab-ic');
            let w = 100; try { w = tx.getComputedTextLength(); } catch (e) {}
            const total = 8 + 26 + 8 + w + 16, x = cx - total / 2, y = +bg.getAttribute('y');
            bg.setAttribute('x', x); bg.setAttribute('width', total);
            ic.setAttribute('transform', `translate(${x + 8 + 13} ${y + 18})`);
            tx.setAttribute('x', x + 8 + 26 + 8);
        });
    }

    function initStory() {
        const section = document.getElementById('audit-story');
        if (!section) return;
        const relabel = () => sizeLabels(section);
        relabel();
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(relabel);
        if (!hasGsap || reduce) return;
        section.classList.add('is-animated');
        gsap.registerPlugin(ScrollTrigger);

        const q = s => section.querySelector(s);
        const qa = s => Array.from(section.querySelectorAll(s));
        const caps = qa('.as-cap');
        const dots = qa('.as-dots i');
        const receipts = qa('.as-r');
        const ticks = qa('.as-tick');
        ticks.forEach(t => { const L = t.getTotalLength(); t.style.strokeDasharray = L; t.style.strokeDashoffset = L; });

        const binderSlots = [{ x: 149, y: 300 }, { x: 187, y: 300 }, { x: 225, y: 300 }];

        // ---- initial state (scene 0) ----
        gsap.set('#as-env', { y: -420 });
        gsap.set('#as-letter', { y: 70 });
        gsap.set(['#as-off'], { x: 320 });
        gsap.set('#as-bk', { y: 260, opacity: 0 });
        gsap.set(['#as-bub1', '#as-bub2'], { opacity: 0, scale: 0.6, transformOrigin: '50% 100%' });
        gsap.set('#as-bub3', { opacity: 0, scale: 0.6, transformOrigin: '0% 50%' });
        gsap.set('#as-ledger', { opacity: 0, scale: 0.85, transformOrigin: '50% 50%' });
        gsap.set('.as-flag', { opacity: 0, x: '-=20' });
        gsap.set('.as-hl', { opacity: 0 });
        gsap.set('#as-mag', { x: 250, y: 145 });
        gsap.set('#as-binders > g', { scaleY: 0, transformOrigin: '50% 100%' });
        gsap.set('#as-check', { opacity: 0, y: -24 });
        gsap.set('#as-file', { opacity: 0, y: 40 });
        gsap.set('#as-stamp', { opacity: 0, scale: 2.4, transformOrigin: '50% 50%' });
        gsap.set('#as-tp-smile', { opacity: 0 });
        gsap.set('.as-lab', { scale: 0, opacity: 0, transformOrigin: '50% 100%' });
        gsap.set(['#as-sweat', '#as-headreceipt'], { opacity: 0 });
        gsap.set(receipts, { x: 180, y: 310, scale: 0.2, opacity: 0, rotation: 0 });
        gsap.set('#as-lid', { transformOrigin: '0% 100%' });
        gsap.set('#as-tower', { transformOrigin: '50% 100%' });
        gsap.set('#as-off-head', { transformOrigin: '50% 90%' });
        gsap.set(['#as-cal-p1', '#as-cal-p2'], { transformOrigin: '50% 0%' });

        const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });

        // ---- Scene 1: the letter ----
        tl.addLabel('s1', 0)
          .to('#as-lab-tp', { scale: 1, opacity: 1, duration: 0.18, ease: 'back.out(3)' }, 's1')
          .to('#as-env', { y: 0, duration: 0.45, ease: 'bounce.out' }, 's1')
          .to('#as-letter', { y: 0, duration: 0.3 }, 's1+=0.45')
          .to('#as-cal-p1', { scaleY: 0, duration: 0.15 }, 's1+=0.5')
          .to('#as-cal-p2', { scaleY: 0, duration: 0.15 }, 's1+=0.65')
          .to('#as-sweat', { opacity: 0.75, y: 6, duration: 0.2 }, 's1+=0.7')
          .to({}, { duration: 0.15 });

        // ---- Scene 2: the shoebox ----
        tl.addLabel('s2', 1)
          .to('#as-off', { x: 0, duration: 0.4, ease: 'power3.out' }, 's2')
          .to('#as-lab-off', { scale: 1, opacity: 1, duration: 0.18, ease: 'back.out(3)' }, 's2+=0.32')
          .to('#as-bub1', { opacity: 1, scale: 1, duration: 0.2, ease: 'back.out(2)' }, 's2+=0.35')
          .to('#as-lid', { y: -26, x: -10, rotation: -14, duration: 0.2, ease: 'back.out(2)' }, 's2+=0.45')
          .to(receipts, {
              x: (i, el) => +el.dataset.x, y: (i, el) => +el.dataset.y,
              rotation: (i, el) => +el.dataset.r, scale: 1, opacity: 1,
              duration: 0.35, stagger: 0.03, ease: 'back.out(1.6)'
          }, 's2+=0.55')
          .to('#as-headreceipt', { opacity: 1, duration: 0.1 }, 's2+=0.7')
          .to('#as-tower', { rotation: -7, duration: 0.15 }, 's2+=0.6')
          .to('#as-tower', { rotation: 5, duration: 0.15 }, 's2+=0.75')
          .to('#as-tower', { rotation: -3, duration: 0.1 }, 's2+=0.9');

        // ---- Scene 3: the questions ----
        tl.addLabel('s3', 2)
          .to('#as-bub1', { opacity: 0, scale: 0.6, duration: 0.12 }, 's3')
          .to('#as-env', { opacity: 0, y: 30, duration: 0.15 }, 's3')
          .to('#as-ledger', { opacity: 1, scale: 1, duration: 0.25, ease: 'back.out(1.4)' }, 's3+=0.1')
          .to('#as-mag', { x: 520, y: 145, duration: 0.2 }, 's3+=0.35')
          .to('.as-hl', { opacity: 1, duration: 0.06, stagger: 0.12 }, 's3+=0.4')
          .to('.as-flag', { opacity: 1, x: '+=20', duration: 0.12, stagger: 0.12, ease: 'back.out(2)' }, 's3+=0.42')
          .to('#as-mag', { x: 300, y: 177, duration: 0.15 }, 's3+=0.55')
          .to('#as-mag', { x: 470, y: 209, duration: 0.15 }, 's3+=0.7')
          .to('#as-off-brow', { y: -5, duration: 0.1 }, 's3+=0.5')
          .to('#as-bub2', { opacity: 1, scale: 1, duration: 0.15, ease: 'back.out(2)' }, 's3+=0.8');

        // ---- Scene 4: B&K sorts it ----
        tl.addLabel('s4', 3)
          .to(['#as-ledger', '#as-bub2'], { opacity: 0, scale: 0.9, duration: 0.15 }, 's4')
          .to('#as-off-brow', { y: 0, duration: 0.1 }, 's4')
          .to('#as-bk', { y: 0, opacity: 1, duration: 0.3, ease: 'back.out(1.4)' }, 's4+=0.1')
          .to('#as-lab-bk', { scale: 1, opacity: 1, duration: 0.18, ease: 'back.out(3)' }, 's4+=0.35')
          .to('#as-box', { opacity: 0, scale: 0.6, transformOrigin: '50% 100%', duration: 0.15 }, 's4+=0.25')
          .to('#as-binders > g', { scaleY: 1, duration: 0.2, stagger: 0.06, ease: 'back.out(1.6)' }, 's4+=0.35')
          .to(receipts, {
              x: (i) => binderSlots[i % 3].x, y: (i) => binderSlots[i % 3].y,
              rotation: 0, scale: 0, opacity: 0, duration: 0.3, stagger: 0.025, ease: 'power2.in'
          }, 's4+=0.45')
          .to('#as-headreceipt', { y: 40, opacity: 0, rotation: 30, duration: 0.2 }, 's4+=0.5')
          .to('#as-tower', { rotation: 0, scaleY: 0.4, opacity: 0, duration: 0.2 }, 's4+=0.55')
          .to('#as-check', { opacity: 1, y: 0, duration: 0.2 }, 's4+=0.6')
          .to(ticks, { strokeDashoffset: 0, duration: 0.12, stagger: 0.08 }, 's4+=0.72');

        // ---- Scene 5: file closes ----
        tl.addLabel('s5', 4)
          .to('#as-file', { opacity: 1, y: 0, duration: 0.2 }, 's5')
          .to('#as-stamp', { opacity: 1, scale: 1, duration: 0.18, ease: 'back.out(3)' }, 's5+=0.2')
          .to('#as-off-head', { rotation: 6, duration: 0.1, yoyo: true, repeat: 3 }, 's5+=0.35')
          .to('#as-bub3', { opacity: 1, scale: 1, duration: 0.15, ease: 'back.out(2)' }, 's5+=0.45')
          .to('#as-tp-worry', { opacity: 0, duration: 0.08 }, 's5+=0.5')
          .to('#as-tp-smile', { opacity: 1, duration: 0.08 }, 's5+=0.5')
          .to('#as-sweat', { opacity: 0, duration: 0.1 }, 's5+=0.5')
          .to({}, { duration: 0.35 });

        let current = 0;
        function setStep(i) {
            if (i === current) return;
            current = i;
            caps.forEach((c, k) => c.classList.toggle('is-active', k === i));
            dots.forEach((d, k) => d.classList.toggle('is-active', k <= i));
        }

        ScrollTrigger.create({
            trigger: section,
            start: 'top top',
            end: () => '+=' + Math.round(window.innerHeight * 4),
            pin: section.querySelector('.as-pin'),
            scrub: 0.5,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            animation: tl,
            onUpdate: self => setStep(Math.min(4, Math.floor(self.progress * 5 * 0.999)))
        });

        if (window.BKMotion && window.BKMotion.refresh) window.addEventListener('load', () => ScrollTrigger.refresh());
    }

    /* ------------------------------------------------------------------ */
    /* Readiness check                                                     */
    /* ------------------------------------------------------------------ */
    function initCheck() {
        const root = document.getElementById('audit-check');
        if (!root) return;
        const qs = Array.from(root.querySelectorAll('.ac-q'));
        const result = root.querySelector('.ac-result');
        const answers = {};

        const bands = [
            { min: 6, title: 'Audit-ready. Nicely done.', body: 'Your records look like they could answer an officer\'s questions on the spot. A periodic review keeps it that way as rules and your business change.' },
            { min: 4, title: 'Mostly there. A few loose receipts.', body: 'The foundations are in place, but the gaps you marked "No" are exactly where audit questions tend to start. They are usually quick to close with the right schedules and documents.' },
            { min: 0, title: 'The shoebox is showing.', body: 'Several areas would be hard to explain if an audit letter arrived tomorrow. The good news: records can be rebuilt and reconciled before anyone asks. Better now than under a deadline.' }
        ];

        function render() {
            const done = qs.length === Object.keys(answers).length;
            if (!done) { result.hidden = true; return; }
            const score = Object.values(answers).reduce((a, b) => a + b, 0);
            const band = bands.find(b => score >= b.min);
            result.querySelector('.ac-n').textContent = score;
            result.querySelector('.ac-msg-title').textContent = band.title;
            result.querySelector('.ac-msg-body').textContent = band.body;
            const wasHidden = result.hidden;
            result.hidden = false;
            if (wasHidden) {
                if (hasGsap && !reduce) gsap.from(result, { opacity: 0, y: 16, scale: 0.98, duration: 0.45, ease: 'back.out(1.6)' });
                if (typeof gtag === 'function') gtag('event', 'audit_check_complete', { score: score });
            }
        }

        qs.forEach(li => {
            const id = li.dataset.q;
            li.querySelectorAll('.bk-chip').forEach(btn => {
                btn.setAttribute('aria-pressed', 'false');
                btn.addEventListener('click', () => {
                    li.querySelectorAll('.bk-chip').forEach(b => { b.dataset.on = 'false'; b.setAttribute('aria-pressed', 'false'); });
                    btn.dataset.on = 'true'; btn.setAttribute('aria-pressed', 'true');
                    answers[id] = +btn.dataset.v;
                    render();
                });
            });
        });

        root.querySelector('.ac-reset').addEventListener('click', () => {
            Object.keys(answers).forEach(k => delete answers[k]);
            root.querySelectorAll('.bk-chip').forEach(b => { b.dataset.on = 'false'; b.setAttribute('aria-pressed', 'false'); });
            result.hidden = true;
            const first = root.querySelector('.bk-chip');
            if (first) first.focus();
        });
    }

    /* ------------------------------------------------------------------ */
    /* Home teaser: plays once when scrolled into view                     */
    /* ------------------------------------------------------------------ */
    function initTeaser() {
        const t = document.querySelector('.audit-teaser');
        if (!t) return;
        if (reduce || !('IntersectionObserver' in window)) { t.classList.add('is-in'); return; }
        const io = new IntersectionObserver(entries => {
            entries.forEach(e => { if (e.isIntersecting) { t.classList.add('is-in'); io.disconnect(); } });
        }, { threshold: 0.45 });
        io.observe(t);
    }

    function boot() { initStory(); initCheck(); initTeaser(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
