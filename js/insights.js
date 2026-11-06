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
    const fmt = new Intl.DateTimeFormat({ zh: 'zh-CN', ms: 'ms-MY' }[lang] || 'en-MY', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' });
    let posts = [];
    // a story is also its type: a case story shows under Case notes too
    const match = (p, t) => t === 'all' || p.type === t || p.series === t;

    function render(type) {
        const list = posts.filter(p => match(p, type));
        if (!list.length) return;
        root.innerHTML = list.map(p => `
            <a class="ins-card" href="insight-${encodeURIComponent(p.slug)}.html" data-type="${esc(p.type)}">
                <span class="ins-type ins-${esc(p.series || p.type)}">${esc(p.type_label)}</span>
                <h3 data-i18n-skip>${esc(p.title)}</h3>
                <p data-i18n-skip>${esc(p.summary)}</p>
                <span class="ins-meta">${esc(fmt.format(new Date(p.date + 'T00:00:00+08:00')))}${p.topic ? ' · ' + esc(p.topic) : ''}</span>
            </a>`).join('');
    }

    fetch('data/insights.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : []).then(d => {
        posts = Array.isArray(d) ? d : [];
        if (!posts.length) document.querySelector('.ins-filter') && (document.querySelector('.ins-filter').hidden = true);
        else render('all');
        // the series cards and the filter buttons work even before the first post is out
        document.querySelectorAll('[data-ins]').forEach(b => b.addEventListener('click', () => {
            const t = b.getAttribute('data-ins');
            document.querySelectorAll('[data-ins]').forEach(x => { const on = x.getAttribute('data-ins') === t; x.classList.toggle('active', on); x.setAttribute('aria-pressed', on ? 'true' : 'false'); });
            if (b.closest('.ins-series')) document.getElementById('ins-latest-title').scrollIntoView({ block: 'start' });
            if (!posts.some(p => match(p, t))) { root.innerHTML = '<p class="ins-empty">The first stories in this series are in final review. <a href="#subscribe">Subscribe</a> to get them first.</p>'; return; }
            render(t);
        }));
    }).catch(() => {});
})();
