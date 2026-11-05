/**
 * Insights list: reads data/insights.json (built from content/insights/*.md by
 * tools/build-insights.py; published posts only) and renders it with a type filter.
 * With no published posts the "in final review" note stays.
 */
(function () {
    'use strict';
    const root = document.querySelector('[data-insights]');
    if (!root) return;
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const lang = (window.BKi18n && window.BKi18n.lang) || 'en';
    const fmt = new Intl.DateTimeFormat({ zh: 'zh-CN', ms: 'ms-MY' }[lang] || 'en-MY', { day: 'numeric', month: 'short', year: 'numeric' });
    let posts = [];

    function render(type) {
        const list = posts.filter(p => type === 'all' || p.type === type);
        if (!list.length) return;
        root.innerHTML = list.map(p => `
            <a class="ins-card" href="insight-${encodeURIComponent(p.slug)}.html" data-type="${esc(p.type)}">
                <span class="ins-type ins-${esc(p.type)}">${esc(p.type_label)}</span>
                <h3 data-i18n-skip>${esc(p.title)}</h3>
                <p data-i18n-skip>${esc(p.summary)}</p>
                <span class="ins-meta">${esc(fmt.format(new Date(p.date + 'T00:00:00+08:00')))}${p.topic ? ' · ' + esc(p.topic) : ''}</span>
            </a>`).join('');
    }

    fetch('data/insights.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : []).then(d => {
        posts = Array.isArray(d) ? d : [];
        if (!posts.length) { document.querySelector('.ins-filter') && (document.querySelector('.ins-filter').hidden = true); return; }
        render('all');
        document.querySelectorAll('[data-ins]').forEach(b => b.addEventListener('click', () => {
            document.querySelectorAll('[data-ins]').forEach(x => { const on = x === b; x.classList.toggle('active', on); x.setAttribute('aria-pressed', on ? 'true' : 'false'); });
            const t = b.getAttribute('data-ins');
            if (!posts.some(p => t === 'all' || p.type === t)) { root.innerHTML = '<p class="ins-empty">Nothing in this category yet.</p>'; return; }
            render(t);
        }));
    }).catch(() => {});
})();
