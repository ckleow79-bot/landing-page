/**
 * Icons: turns any <i class="fas fa-NAME"> added by scripts into an inline SVG from
 * assets/icons/sprite.svg (self-hosted Lucide + Simple Icons). Static pages already
 * use the SVG markup directly; this covers markup rendered at runtime.
 */
(function () {
    'use strict';
    const SPRITE = 'assets/icons/sprite.svg#';
    const SKIP = /^(fa|fas|far|fab|fa-solid|fa-regular|fa-brands)$/;
    function swap(i) {
        let name = null; const keep = ['ic'];
        i.classList.forEach(c => { if (SKIP.test(c)) return; if (c.indexOf('fa-') === 0) { if (!name) name = c.slice(3); return; } keep.push(c); });
        if (!name) return;
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', keep.join(' '));
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('focusable', 'false');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        use.setAttribute('href', SPRITE + name);
        svg.appendChild(use);
        i.replaceWith(svg);
    }
    const scan = root => { if (root.querySelectorAll) root.querySelectorAll('i[class*="fa-"]').forEach(swap); };
    scan(document);
    new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) { if (n.matches('i[class*="fa-"]')) swap(n); else scan(n); } })))
        .observe(document.documentElement, { childList: true, subtree: true });
})();
