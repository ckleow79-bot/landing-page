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
        zh: { tag: '下一场', starts: '倒数', today: '今天开始', details: '查看详情', close: '关闭提示', d: '天', h: '小时', m: '分', label: '下一场课程' },
        ms: { tag: 'Seterusnya', starts: 'Bermula dalam', today: 'Bermula hari ini', details: 'Butiran', close: 'Tutup', d: 'h', h: 'j', m: 'm', label: 'Program seterusnya' },
        en: { tag: 'Next up', starts: 'Starts in', today: 'Starts today', details: 'Details', close: 'Dismiss', d: 'd', h: 'h', m: 'm', label: 'Next programme' }
    }[lang] || {};
    const fmt = new Intl.DateTimeFormat(zh ? 'zh-CN' : (window.BKi18n && BKi18n.lang === 'ms' ? 'ms-MY' : 'en-MY'), { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' });
    const KEY = 'bk-ribbon-dismissed';
    const SEEN = 'bk-ribbon-next';
    // reserve the ribbon's space before first paint when we already know it will show,
    // so the header never jumps or sits under the ribbon
    try {
        const seen = sessionStorage.getItem(SEEN);
        if (seen && sessionStorage.getItem(KEY) !== seen) document.documentElement.style.setProperty('--ribbon-h', '40px');
    } catch (e) { /* ignore */ }

    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function countdown(ms) {
        if (ms <= 0) return T.today;
        const m = Math.floor(ms / 60000), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
        const parts = d > 0 ? [d + T.d, h + T.h] : [h + T.h, mm + T.m];
        return `${T.starts} ${parts.join(' ')}`;
    }

    function setHeight(px) { document.documentElement.style.setProperty('--ribbon-h', px + 'px'); }

    async function init() {
        if (!window.BKProgrammes) { setHeight(0); return; }
        let data;
        try { data = await window.BKProgrammes.load(); } catch (e) { setHeight(0); return; }
        const now = Date.now();
        const next = data.list.filter(p => p.status === 'upcoming' && p.provider !== 'external' && p._start > now - 8 * 3600e3)
            .sort((a, b) => a._start - b._start)[0];
        if (!next) { setHeight(0); return; }
        try {
            if (sessionStorage.getItem(KEY) === next.slug) { setHeight(0); return; }
            sessionStorage.setItem(SEEN, next.slug);
        } catch (e) { /* ignore */ }

        const bar = document.createElement('div');
        bar.className = 'next-ribbon';
        bar.setAttribute('role', 'region');
        bar.setAttribute('aria-label', T.label);
        const where = next.venue || next.mode || '';
        bar.setAttribute('data-i18n-skip', '');
        bar.innerHTML = `
            <div class="nr-in">
                <span class="nr-tag">${T.tag}</span>
                <span class="nr-title" data-i18n-skip>${esc(next.title)}</span>
                <span class="nr-meta" data-i18n-skip>${esc(fmt.format(new Date(next.start_date)))}${where ? ' · ' + esc(where) : ''}</span>
                <span class="nr-count" aria-live="off"></span>
                <a class="nr-cta" href="programmes.html?open=${encodeURIComponent(next.slug)}">${T.details}</a>
            </div>
            <button type="button" class="nr-x" aria-label="${T.close}">&times;</button>`;
        document.body.prepend(bar);
        setHeight(bar.offsetHeight);

        const out = bar.querySelector('.nr-count');
        const tick = () => { out.textContent = countdown(next._start - Date.now()); };
        tick();
        const timer = setInterval(tick, 30000);

        bar.querySelector('.nr-x').addEventListener('click', () => {
            clearInterval(timer);
            bar.classList.add('is-out');
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
