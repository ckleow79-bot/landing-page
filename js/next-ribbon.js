/**
 * "Next programme" ribbon: a slim bar above the header showing the next upcoming
 * public programme with a live countdown. Reads the same programme list as the
 * Programmes page (Supabase, else data/programmes.json), so it updates itself.
 * Needs js/programmes.js on the page. Dismissal lasts for the browser session.
 */
(function () {
    'use strict';

    const lang = (window.BKi18n && window.BKi18n.lang) || 'en';
    const zh = lang === 'zh';
    const T = {
        zh: { tag: '下一场', starts: '倒数', today: '今天开始', details: '报名', close: '关闭提示', d: '天', h: '小时', m: '分', s: '秒', label: '下一场课程' },
        ms: { tag: 'Seterusnya', starts: 'Bermula dalam', today: 'Bermula hari ini', details: 'Daftar', close: 'Tutup', d: 'h', h: 'j', m: 'm', s: 's', label: 'Program seterusnya' },
        en: { tag: 'Next up', starts: 'Starts in', today: 'Starts today', details: 'Register', close: 'Dismiss', d: 'd', h: 'h', m: 'm', s: 's', label: 'Next programme' }
    }[lang] || {};
    const fmt = new Intl.DateTimeFormat(zh ? 'zh-CN' : (window.BKi18n && BKi18n.lang === 'ms' ? 'ms-MY' : 'en-MY'), { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' });
    const KEY = 'bk-ribbon-dismissed';
    const SEEN = 'bk-ribbon-next';
    // Put an empty bar in place straight away (this script runs before the header is
    // loaded), so the header never jumps down when the programme data arrives.
    // Skipped only when the visitor already dismissed the programme we showed last.
    let bar = null;
    try {
        const seen = sessionStorage.getItem(SEEN);
        if (!(seen && sessionStorage.getItem(KEY) === seen)) bar = document.createElement('div');
    } catch (e) { bar = document.createElement('div'); }
    if (bar) {
        bar.className = 'next-ribbon';
        bar.setAttribute('aria-hidden', 'true');
        document.body.prepend(bar);
        document.documentElement.style.setProperty('--ribbon-h', '40px');
    }
    const drop = () => { if (bar && !bar.querySelector('.nr-in')) bar.remove(); setHeight(0); };

    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // [value, unit] pairs: d h m s, or h m s on the last day
    function parts(ms) {
        const t = Math.floor(ms / 1000), d = Math.floor(t / 86400), h = Math.floor(t % 86400 / 3600), m = Math.floor(t % 3600 / 60), sec = t % 60;
        const p2 = n => String(n).padStart(2, '0');
        const list = [[p2(h), T.h], [p2(m), T.m], [p2(sec), T.s]];
        return d > 0 ? [[String(d), T.d]].concat(list) : list;
    }

    function setHeight(px) { document.documentElement.style.setProperty('--ribbon-h', px + 'px'); }

    async function init() {
        if (!window.BKProgrammes) { drop(); return; }
        let data;
        try { data = await window.BKProgrammes.load(); } catch (e) { drop(); return; }
        const now = Date.now();
        const next = data.list.filter(p => p.status === 'upcoming' && p.provider !== 'external' && p._start > now - 8 * 3600e3)
            .sort((a, b) => a._start - b._start)[0];
        if (!next) { drop(); return; }
        try {
            if (sessionStorage.getItem(KEY) === next.slug) { drop(); return; }
            sessionStorage.setItem(SEEN, next.slug);
        } catch (e) { /* ignore */ }

        if (!bar) { bar = document.createElement('div'); bar.className = 'next-ribbon'; document.body.prepend(bar); }
        bar.removeAttribute('aria-hidden');
        bar.setAttribute('role', 'region');
        bar.setAttribute('aria-label', T.label);
        // the city, so three sessions of the same seminar can be told apart
        const city = (next.venue || next.mode || '').split(',').pop().trim();
        const title = window.BKi18n && BKi18n.tr ? BKi18n.tr(next.title) : next.title;
        bar.setAttribute('data-i18n-skip', '');
        bar.innerHTML = `
            <div class="nr-in">
                <span class="nr-tag"><i class="nr-dot" aria-hidden="true"></i><span class="nr-tag-t">${T.tag}</span></span>
                <span class="nr-title" data-i18n-skip>${esc(title)}${city ? ' · ' + esc(city) : ''}</span>
                <span class="nr-meta" data-i18n-skip>${esc(fmt.format(new Date(next.start_date)))}${next.venue && next.venue.indexOf(',') > 0 ? ' · ' + esc(next.venue.slice(0, next.venue.lastIndexOf(','))) : ''}</span>
                <span class="nr-count" aria-live="off"></span>
                <a class="nr-cta" href="programmes.html?open=${encodeURIComponent(next.slug)}">${T.details}<span class="nr-arrow" aria-hidden="true">&rarr;</span></a>
            </div>
            <button type="button" class="nr-x" aria-label="${T.close}">&times;</button>`;
        setHeight(bar.offsetHeight);

        // phones: give the screen back while reading (large text makes ribbon + header + action bar tall)
        const phone = window.matchMedia('(max-width: 767px)');
        let tucked = false;
        const onScroll = () => {
            if (bar.classList.contains('is-gone')) return;
            const t = phone.matches && window.scrollY > 120;
            if (t === tucked) return;
            tucked = t;
            bar.classList.toggle('is-out', t);
            setHeight(t ? 0 : bar.offsetHeight);
        };
        window.addEventListener('scroll', onScroll, { passive: true });

        // ticking countdown; each unit that changes rolls in (CSS turns the roll off for reduced motion)
        const out = bar.querySelector('.nr-count');
        let shown = [];
        const tick = () => {
            const ms = next._start - Date.now();
            if (ms <= 0) { out.textContent = T.today; clearInterval(timer); return; }
            const p = parts(ms);
            if (p.length !== shown.length) {
                out.innerHTML = `<span class="nr-sl">${T.starts}</span>` + p.map(() => '<span class="nr-u"><b></b><small></small></span>').join('');
                shown = [];
            }
            out.querySelectorAll('.nr-u').forEach((u, i) => {
                if (shown[i] && shown[i][0] === p[i][0]) return;
                const b = document.createElement('b');
                b.textContent = p[i][0];
                if (shown.length) b.className = 'roll';
                u.replaceChild(b, u.firstChild);
                u.lastChild.textContent = p[i][1];
            });
            shown = p;
        };
        const timer = setInterval(tick, 1000);
        tick();

        bar.querySelector('.nr-x').addEventListener('click', () => {
            clearInterval(timer);
            bar.classList.add('is-out', 'is-gone');
            setHeight(0);
            setTimeout(() => bar.remove(), 400);
            try { sessionStorage.setItem(KEY, next.slug); } catch (e) { /* ignore */ }
        });
        bar.querySelector('.nr-cta').addEventListener('click', () => {
            if (typeof gtag === 'function') gtag('event', 'ribbon_click', { programme: next.slug });
        });
        if (window.BKMotion && window.BKMotion.refresh) window.BKMotion.refresh();
    }

    // programmes.js waits one tick after DOMContentLoaded for Supabase; do the same
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 0));
    else setTimeout(init, 0);
})();
