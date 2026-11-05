/**
 * Interactive pieces:
 *   .hats       "Which hat do you wear?" role picker with a phone-style screen (Home)
 *   .role-ring  orbiting role chips around a profile card (About)
 *   .flow       engagement timeline whose track fills as you scroll (Advisory)
 * All content is in the HTML; without JS the first hat shows, the ring is static
 * and every timeline step is lit.
 */
(function () {
    'use strict';
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hasGsap = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';
    const zh = window.BKi18n && window.BKi18n.lang === 'zh';
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    /* ---------- Which hat do you wear? ---------- */
    function initHats() {
        const root = document.querySelector('.hats');
        if (!root) return;
        root.classList.add('is-live');
        const btns = [...root.querySelectorAll('.hat')];
        const screens = [...root.querySelectorAll('.ph-screen')];
        let current = 0, userPicked = false;
        function set(i, user) {
            if (i === current && !user) return;
            current = i;
            btns.forEach((b, k) => { b.classList.toggle('is-on', k === i); b.setAttribute('aria-pressed', k === i ? 'true' : 'false'); });
            screens.forEach((s, k) => s.classList.toggle('is-on', k === i));
            if (user && typeof gtag === 'function') gtag('event', 'hat_select', { hat: i });
        }
        btns.forEach((b, i) => b.addEventListener('click', () => { userPicked = true; set(i, true); }));
        // desktop: the hat in the middle of the screen becomes active as you scroll
        if ('IntersectionObserver' in window && window.matchMedia('(min-width: 992px)').matches) {
            const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting && !userPicked) set(btns.indexOf(e.target)); }), { rootMargin: '-45% 0px -45% 0px' });
            btns.forEach(b => io.observe(b));
        }
        // accountant screen: next sessions from the live programme list
        const live = root.querySelector('[data-live-programmes]');
        if (live && window.BKProgrammes) {
            const fmt = new Intl.DateTimeFormat(zh ? 'zh-CN' : 'en-MY', { day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' });
            window.BKProgrammes.load().then(d => {
                const next = d.list.filter(p => p.status === 'upcoming').slice(0, 4);
                live.innerHTML = next.length
                    ? next.map(p => `<li><span data-i18n-skip>${esc(p.title)}</span><span class="st-chip st-ready"><i></i>${esc(fmt.format(new Date(p.start_date)))}</span></li>`).join('')
                    : `<li><span>${zh ? '新课程即将公布' : 'New dates coming soon'}</span></li>`;
            }).catch(() => { live.innerHTML = `<li><span>${zh ? '请查看课程页面' : 'See the Programmes page'}</span></li>`; });
        }
    }

    /* ---------- Role ring ---------- */
    function initRing() {
        document.querySelectorAll('.role-ring').forEach(ring => {
            const desc = ring.parentElement.querySelector('.rr-desc');
            const chips = [...ring.querySelectorAll('.rr-item .st-chip')];
            const show = c => {
                chips.forEach(x => x.classList.toggle('is-on', x === c));
                desc.textContent = c.getAttribute('data-desc');
            };
            chips.forEach(c => {
                c.addEventListener('click', () => show(c));
                c.addEventListener('mouseenter', () => show(c));
                c.addEventListener('focus', () => show(c));
            });
        });
    }

    /* ---------- Engagement timeline ---------- */
    function initFlow() {
        document.querySelectorAll('.flow').forEach(sec => {
            const steps = [...sec.querySelectorAll('.tl-step')];
            if (!hasGsap || reduce) { sec.style.setProperty('--fp', 1); steps.forEach(s => s.classList.add('is-on')); return; }
            gsap.registerPlugin(ScrollTrigger);
            sec.classList.add('is-live');
            const n = steps.length;
            ScrollTrigger.create({
                trigger: sec.querySelector('.flow-steps'), start: 'top 80%', end: 'bottom 45%', scrub: 0.4,
                onUpdate: st => {
                    const p = st.progress;
                    sec.style.setProperty('--fp', p.toFixed(4));
                    steps.forEach((s, i) => s.classList.toggle('is-on', p >= (n > 1 ? i / (n - 1) : 0) - 0.02));
                }
            });
        });
    }

    function boot() { initHats(); initRing(); initFlow(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0)); else setTimeout(boot, 0);
})();
