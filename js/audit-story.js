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
            if (!w) return;
            const total = 8 + 26 + 8 + w + 16, x = cx - total / 2, y = +bg.getAttribute('y');
            bg.setAttribute('x', x); bg.setAttribute('width', total);
            ic.setAttribute('transform', `translate(${x + 8 + 13} ${y + 18})`);
            tx.setAttribute('x', x + 8 + 26 + 8);
        });
    }

    /* Build one story (tax audit "as" or e-Invoice review "ei") inside its section. */
    function buildStory(section) {
        const P = section.dataset.kind;              // 'as' | 'ei'
        const $ = id => section.querySelector('#' + P + '-' + id);
        const $$ = sel => Array.from(section.querySelectorAll(sel));
        const caps = $$('.as-cap'), dots = $$('.as-dots i'), files = $$('.as-r'), ticks = $$('.as-tick');
        const tags = { tp: $('lab-tp'), off: $('lab-off'), bk: $('lab-bk') };
        ticks.forEach(t => { const L = t.getTotalLength(); t.style.strokeDasharray = L; t.style.strokeDashoffset = L; });
        const binderSlots = [{ x: 149, y: 300 }, { x: 187, y: 300 }, { x: 225, y: 300 }];

        // ---- initial state ----
        gsap.set($('env'), P === 'as' ? { y: -420 } : { opacity: 1 });
        gsap.set($('letter'), P === 'as' ? { y: 70 } : { scale: 0, opacity: 0, transformOrigin: '50% 50%' });
        gsap.set($('off'), { x: 320 });
        gsap.set($('bk'), { y: 260, opacity: 0 });
        gsap.set([$('bub1'), $('bub2')], { opacity: 0, scale: 0.6, transformOrigin: '50% 100%' });
        gsap.set($('bub3'), { opacity: 0, scale: 0.6, transformOrigin: '0% 50%' });
        gsap.set($('ledger'), { opacity: 0, scale: 0.85, transformOrigin: '50% 50%' });
        gsap.set($$('.as-flag'), { opacity: 0, x: '-=20' });
        gsap.set($$('.ei-ok'), { opacity: 0, scale: 0.6, transformOrigin: '50% 50%' });
        gsap.set($$('.as-hl'), { opacity: 0 });
        gsap.set($('mag'), { x: 250, y: P === 'as' ? 145 : 192 });
        gsap.set($$('#' + P + '-binders > g'), { scaleY: 0, transformOrigin: '50% 100%' });
        gsap.set($('check'), { opacity: 0, y: -24 });
        gsap.set($('file'), { opacity: 0, y: 40 });
        gsap.set($('stamp'), { opacity: 0, scale: 2.4, transformOrigin: '50% 50%' });
        gsap.set($('tp-smile'), { opacity: 0 });
        gsap.set([$('sweat'), $('headreceipt')], { opacity: 0 });
        gsap.set(Object.values(tags), { scale: 0, opacity: 0, transformOrigin: '50% 100%' });
        gsap.set(files, { x: P === 'as' ? 180 : 400, y: P === 'as' ? 310 : 275, scale: 0.2, opacity: 0, rotation: 0 });
        gsap.set($('lid'), { transformOrigin: '0% 100%' });
        gsap.set($('tower'), { transformOrigin: '50% 100%' });
        gsap.set($('off-head'), { transformOrigin: '50% 90%' });
        gsap.set([$('cal-p1'), $('cal-p2')], { transformOrigin: '50% 0%' });
        const pop = { scale: 1, opacity: 1, duration: 0.18, ease: 'back.out(3)' };

        const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });

        // ---- Scene 1: the notice ----
        tl.addLabel('s1', 0).to(tags.tp, pop, 's1');
        if (P === 'as') {
            tl.to($('env'), { y: 0, duration: 0.45, ease: 'bounce.out' }, 's1')
              .to($('letter'), { y: 0, duration: 0.3 }, 's1+=0.45');
        } else {
            tl.to($('letter'), { scale: 1, opacity: 1, duration: 0.3, ease: 'back.out(2.2)' }, 's1+=0.15')
              .to($('letter'), { x: 3, duration: 0.04, yoyo: true, repeat: 5 }, 's1+=0.45');
        }
        tl.to($('cal-p1'), { scaleY: 0, duration: 0.15 }, 's1+=0.5')
          .to($('cal-p2'), { scaleY: 0, duration: 0.15 }, 's1+=0.65')
          .to($('sweat'), { opacity: 0.75, y: 6, duration: 0.2 }, 's1+=0.7')
          .to({}, { duration: 0.15 });

        // ---- Scene 2: the records come out ----
        tl.addLabel('s2', 1)
          .to($('off'), { x: 0, duration: 0.4, ease: 'power3.out' }, 's2')
          .to(tags.off, pop, 's2+=0.32')
          .to($('bub1'), { opacity: 1, scale: 1, duration: 0.2, ease: 'back.out(2)' }, 's2+=0.35');
        if (P === 'as') tl.to($('lid'), { y: -26, x: -10, rotation: -14, duration: 0.2, ease: 'back.out(2)' }, 's2+=0.45');
        else tl.to($('lid'), { y: -6, rotation: 10, duration: 0.08, yoyo: true, repeat: 3 }, 's2+=0.45');
        tl.to(files, {
              x: (i, el) => +el.dataset.x, y: (i, el) => +el.dataset.y,
              rotation: (i, el) => +el.dataset.r, scale: 1, opacity: 1,
              duration: 0.35, stagger: 0.03, ease: 'back.out(1.6)'
          }, 's2+=0.55')
          .to($('headreceipt'), { opacity: 1, duration: 0.1 }, 's2+=0.7')
          .to($('tower'), { rotation: -7, duration: 0.15 }, 's2+=0.6')
          .to($('tower'), { rotation: 5, duration: 0.15 }, 's2+=0.75')
          .to($('tower'), { rotation: -3, duration: 0.1 }, 's2+=0.9');

        // ---- Scene 3: the questions ----
        const r1 = P === 'as' ? 145 : 192, step = 32;
        tl.addLabel('s3', 2)
          .to($('bub1'), { opacity: 0, scale: 0.6, duration: 0.12 }, 's3')
          .to($('env'), { opacity: 0, y: 30, duration: 0.15 }, 's3')
          .to($('ledger'), { opacity: 1, scale: 1, duration: 0.25, ease: 'back.out(1.4)' }, 's3+=0.1')
          .to($('mag'), { x: 520, y: r1, duration: 0.2 }, 's3+=0.35')
          .to($$('.as-hl'), { opacity: 1, duration: 0.06, stagger: 0.12 }, 's3+=0.4')
          .to($$('.as-flag'), { opacity: 1, x: '+=20', duration: 0.12, stagger: 0.12, ease: 'back.out(2)' }, 's3+=0.42')
          .to($('mag'), { x: 300, y: r1 + step, duration: 0.15 }, 's3+=0.55')
          .to($('mag'), { x: 470, y: r1 + step * 2, duration: 0.15 }, 's3+=0.7')
          .to($('off-brow'), { y: -5, duration: 0.1 }, 's3+=0.5')
          .to($('bub2'), { opacity: 1, scale: 1, duration: 0.15, ease: 'back.out(2)' }, 's3+=0.8');

        // ---- Scene 4: the tax agent sorts it ----
        tl.addLabel('s4', 3);
        if (P === 'ei') {
            tl.to($('bub2'), { opacity: 0, scale: 0.9, duration: 0.1 }, 's4')
              .to($('mag'), { opacity: 0, duration: 0.1 }, 's4')
              .to($$('.as-hl'), { fill: '#DCF3E9', duration: 0.1, stagger: 0.06 }, 's4+=0.05')
              .to($$('.as-flag'), { opacity: 0, duration: 0.08, stagger: 0.06 }, 's4+=0.05')
              .to($$('.ei-ok'), { opacity: 1, scale: 1, duration: 0.12, stagger: 0.06, ease: 'back.out(2.4)' }, 's4+=0.1')
              .to($('ledger'), { opacity: 0, scale: 0.9, duration: 0.15 }, 's4+=0.4');
        } else {
            tl.to([$('ledger'), $('bub2')], { opacity: 0, scale: 0.9, duration: 0.15 }, 's4');
        }
        tl.to($('off-brow'), { y: 0, duration: 0.1 }, 's4')
          .to($('bk'), { y: 0, opacity: 1, duration: 0.3, ease: 'back.out(1.4)' }, 's4+=0.1')
          .to(tags.bk, pop, 's4+=0.35')
          .to($('box'), { opacity: 0, scale: 0.6, transformOrigin: '50% 100%', duration: 0.15 }, 's4+=0.4')
          .to($$('#' + P + '-binders > g'), { scaleY: 1, duration: 0.2, stagger: 0.06, ease: 'back.out(1.6)' }, 's4+=0.45')
          .to(files, {
              x: (i) => binderSlots[i % 3].x, y: (i) => binderSlots[i % 3].y,
              rotation: 0, scale: 0, opacity: 0, duration: 0.3, stagger: 0.025, ease: 'power2.in'
          }, 's4+=0.5')
          .to($('headreceipt'), { y: 40, opacity: 0, rotation: 30, duration: 0.2 }, 's4+=0.55')
          .to($('tower'), { rotation: 0, scaleY: 0.4, opacity: 0, duration: 0.2 }, 's4+=0.6')
          .to($('check'), { opacity: 1, y: 0, duration: 0.2 }, 's4+=0.65')
          .to(ticks, { strokeDashoffset: 0, duration: 0.1, stagger: 0.07 }, 's4+=0.75');

        // ---- Scene 5: closed ----
        tl.addLabel('s5', 4)
          .to($('file'), { opacity: 1, y: 0, duration: 0.2 }, 's5')
          .to($('stamp'), { opacity: 1, scale: 1, duration: 0.18, ease: 'back.out(3)' }, 's5+=0.2')
          .to($('off-head'), { rotation: 6, duration: 0.1, yoyo: true, repeat: 3 }, 's5+=0.35')
          .to($('bub3'), { opacity: 1, scale: 1, duration: 0.15, ease: 'back.out(2)' }, 's5+=0.45')
          .to($('tp-worry'), { opacity: 0, duration: 0.08 }, 's5+=0.5')
          .to($('tp-smile'), { opacity: 1, duration: 0.08 }, 's5+=0.5')
          .to($('sweat'), { opacity: 0, duration: 0.1 }, 's5+=0.5')
          .to({}, { duration: 0.35 });

        let current = -1;
        function setStep(i) {
            if (i === current) return;
            current = i;
            caps.forEach((c, k) => c.classList.toggle('is-active', k === i));
            dots.forEach((d, k) => d.classList.toggle('is-active', k <= i));
        }
        setStep(0);

        const st = ScrollTrigger.create({
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
        return { kill() { st.kill(true); tl.progress(0).kill(); setStep(0); } };
    }

    function initStory() {
        const sections = Array.from(document.querySelectorAll('.audit-story[data-kind]'));
        if (!sections.length) return;
        sections.forEach(s => {
            const relabel = () => sizeLabels(s);
            relabel();
            if (document.fonts && document.fonts.ready) document.fonts.ready.then(relabel);
        });
        const animate = hasGsap && !reduce;
        if (animate) { gsap.registerPlugin(ScrollTrigger); sections.forEach(s => s.classList.add('is-animated')); }

        let live = null;
        function show(id, scroll) {
            if (live) { live.kill(); live = null; }
            sections.forEach(s => { s.hidden = s.id !== id; });
            const sec = document.getElementById(id);
            document.querySelectorAll('.story-tab').forEach(b => {
                const on = b.dataset.story === id;
                b.classList.toggle('is-on', on); b.setAttribute('aria-selected', on ? 'true' : 'false');
            });
            sizeLabels(sec);
            const lenis = window.BKMotion && window.BKMotion.lenis;
            if (lenis && lenis.resize) lenis.resize();
            if (scroll) {
                const y = sec.getBoundingClientRect().top + window.scrollY;
                if (lenis) lenis.scrollTo(y, { immediate: true, force: true }); else window.scrollTo(0, y);
            }
            if (animate) { ScrollTrigger.refresh(); live = buildStory(sec); ScrollTrigger.refresh(); }
        }
        document.querySelectorAll('.story-tab').forEach(b => b.addEventListener('click', () => show(b.dataset.story, true)));
        const wantEi = location.hash === '#einvoice-review';
        show(wantEi ? 'einvoice-review' : 'audit-story', false);
        if (wantEi) setTimeout(() => show('einvoice-review', true), 300);
        if (animate) window.addEventListener('load', () => ScrollTrigger.refresh());
    }

    /* ------------------------------------------------------------------ */
    /* Readiness check                                                     */
    /* ------------------------------------------------------------------ */
    const BANDS = {
        audit: [
            { min: 6, title: 'Audit-ready. Nicely done.', body: 'Your records look like they could answer an officer\'s questions on the spot. A periodic review keeps it that way as rules and your business change.' },
            { min: 4, title: 'Mostly there. A few loose receipts.', body: 'The foundations are in place, but the gaps you marked "No" are exactly where audit questions tend to start. They are usually quick to close with the right schedules and documents.' },
            { min: 0, title: 'The shoebox is showing.', body: 'Several areas would be hard to explain to a tax officer. The good news: records can be rebuilt and reconciled, even if the letter has already arrived. The sooner you start, the easier it is.' }
        ],
        einvoice: [
            { min: 6, title: 'Your e-Invoices and your books agree.', body: 'Sales, credit notes and self-billed cases all appear to flow through MyInvois and match the ledger. A periodic sample check keeps it that way as LHDN updates its guidelines.' },
            { min: 4, title: 'Close, with a few mismatches waiting.', body: 'The basics are running, but each "No" is a place where your accounts and MyInvois can drift apart. Those gaps are usually fixed with a monthly reconciliation and a short written policy.' },
            { min: 0, title: 'final_v3_REAL is not a control.', body: 'Several areas would be hard to explain in an e-Invoice compliance review. The fix is a reconciliation between your sales ledger and MyInvois, then clear rules for consolidated, self-billed and adjustment notes.' }
        ]
    };

    function initCheck() {
        document.querySelectorAll('.audit-check').forEach(initOneCheck);
    }

    function initOneCheck(root) {
        const kind = root.dataset.check || 'audit';
        const qs = Array.from(root.querySelectorAll('.ac-q'));
        const result = root.querySelector('.ac-result');
        const answers = {};

        const bands = BANDS[kind] || BANDS.audit;

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
            if (score === qs.length && result.dataset.cheered !== '1' && window.BKConfetti) { result.dataset.cheered = '1'; setTimeout(() => window.BKConfetti(result.querySelector('.ac-score')), 250); }
            if (score < qs.length) result.dataset.cheered = '';
            if (wasHidden) {
                if (hasGsap && !reduce) gsap.from(result, { opacity: 0, y: 16, scale: 0.98, duration: 0.45, ease: 'back.out(1.6)' });
                if (typeof gtag === 'function') gtag('event', kind + '_check_complete', { score: score });
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
