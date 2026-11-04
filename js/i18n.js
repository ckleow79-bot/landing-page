/**
 * English / 中文 switch.
 *
 * One HTML source per page. English is the source text; data/i18n/zh.json maps
 * English strings to Simplified Chinese. Two kinds of keys:
 *   - "text":  a plain text node, whitespace-collapsed
 *   - "html":  the innerHTML of a "leaf block" (an element whose descendants are
 *              all inline tags such as <em>, <a>, <strong>, <br>), whitespace-collapsed
 * Anything without a translation stays in English, so a missing key never breaks a page.
 *
 * Load this as the first script at the end of <body>, before cinematic.js splits
 * the hero heading into words. Switching language reloads the page so every
 * animation is built once, in the right language.
 */
(function () {
    'use strict';

    const KEY = 'bk-lang';
    const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'svg', 'CODE', 'PRE', 'TEXTAREA', 'TEMPLATE', 'IFRAME']);
    const INLINE = new Set(['A', 'ABBR', 'B', 'BR', 'CODE', 'EM', 'I', 'MARK', 'SMALL', 'SPAN', 'STRONG', 'SUB', 'SUP', 'TIME', 'U', 'WBR']);
    const ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];

    const params = new URLSearchParams(location.search);
    const collect = params.get('i18n') === 'collect';
    let lang = 'en';
    try { lang = params.get('lang') || localStorage.getItem(KEY) || 'en'; } catch (e) { lang = params.get('lang') || 'en'; }
    if (lang !== 'zh') lang = 'en';

    const api = window.BKi18n = {
        lang,
        t: (en, zh) => (lang === 'zh' && zh ? zh : en),
        set(next) {
            try { localStorage.setItem(KEY, next); } catch (e) { /* private mode: fall back to the URL */ }
            const url = new URL(location.href);
            url.searchParams.delete('lang');
            if (next === 'zh') url.searchParams.set('lang', 'zh');
            location.replace(url.toString());
        }
    };

    const norm = s => s.replace(/\s+/g, ' ').trim();
    // A "leaf block" mixes its own words with inline elements that also carry words,
    // e.g. <p>Read <a>s.82</a> first</p>. Those are translated as one HTML string so
    // word order can change. Anything else is walked node by node.
    const hasWords = s => /[A-Za-z]/.test(s);
    const isLeafBlock = el => {
        if (!el.firstElementChild) return false;
        const all = el.getElementsByTagName('*');
        let wordyChild = false;
        for (let i = 0; i < all.length; i++) {
            if (!INLINE.has(all[i].tagName)) return false;
            if (!wordyChild && hasWords(all[i].textContent)) wordyChild = true;
        }
        if (!wordyChild) return false;
        for (let c = el.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && hasWords(c.nodeValue)) return true;
        return false;
    };
    const skipped = el => SKIP.has(el.tagName) || el.hasAttribute('data-i18n-skip') || el.namespaceURI === 'http://www.w3.org/2000/svg';

    /* ---------- collect mode: lists every key on the page (used to build zh.json) ---------- */
    const found = { text: new Set(), html: new Set() };
    window.__i18nKeys = () => ({ text: [...found.text], html: [...found.html] });

    let dict = null;

    function translateAttrs(el) {
        ATTRS.forEach(a => {
            const v = el.getAttribute && el.getAttribute(a);
            if (!v || !/[A-Za-z]/.test(v)) return;
            const k = norm(v);
            if (collect) { found.text.add(k); return; }
            if (dict.text[k]) el.setAttribute(a, dict.text[k]);
        });
    }

    function walk(node) {
        if (node.nodeType === 3) {
            const k = norm(node.nodeValue);
            if (!k || !/[A-Za-z]/.test(k)) return;
            if (collect) { found.text.add(k); return; }
            const zh = dict.text[k];
            if (zh) {
                const lead = node.nodeValue.match(/^\s*/)[0] ? ' ' : '';
                const tail = node.nodeValue.match(/\s*$/)[0] ? ' ' : '';
                node.nodeValue = lead + zh + tail;
            }
            return;
        }
        if (node.nodeType !== 1 || skipped(node)) return;
        translateAttrs(node);
        if (isLeafBlock(node)) {
            const k = norm(node.innerHTML);
            if (/[A-Za-z]/.test(node.textContent)) {
                if (collect) { found.html.add(k); return; }
                if (dict.html[k]) { node.innerHTML = dict.html[k]; node.querySelectorAll('*').forEach(translateAttrs); return; }
            }
        }
        for (let c = node.firstChild; c; c = c.nextSibling) walk(c);
    }

    function translateTitle() {
        const k = norm(document.title);
        if (collect) { found.text.add(k); return; }
        if (dict.text[k]) document.title = dict.text[k];
        const md = document.querySelector('meta[name="description"]');
        if (md && dict.text[norm(md.content)]) md.content = dict.text[norm(md.content)];
    }

    function observe() {
        let busy = false;
        new MutationObserver(muts => {
            if (busy) return;
            busy = true;
            muts.forEach(m => {
                if (m.type === 'characterData') walk(m.target);
                m.addedNodes.forEach(n => {
                    // a leaf block whose text was replaced: retry the parent as a whole first
                    const p = n.parentNode;
                    if (p && p.nodeType === 1 && !skipped(p) && isLeafBlock(p)) walk(p); else walk(n);
                });
            });
            busy = false;
        }).observe(document.body, { childList: true, subtree: true, characterData: true });
    }

    function toggleUi() {
        document.addEventListener('click', e => {
            const b = e.target.closest('[data-lang-toggle]');
            if (!b) return;
            e.preventDefault();
            api.set(lang === 'zh' ? 'en' : 'zh');
        });
        const sync = () => document.querySelectorAll('[data-lang-toggle]').forEach(b => {
            b.setAttribute('aria-label', lang === 'zh' ? 'Switch to English' : '切换到中文');
            b.setAttribute('lang', lang === 'zh' ? 'en' : 'zh-Hans');
            b.querySelector('.lang-label') && (b.querySelector('.lang-label').textContent = lang === 'zh' ? 'EN' : '中文');
        });
        sync();
        new MutationObserver(sync).observe(document.getElementById('header-container') || document.body, { childList: true });
    }

    // keep the language when moving between pages opened with ?lang=zh
    if (lang === 'zh') { try { localStorage.setItem(KEY, 'zh'); } catch (e) { /* ignore */ } }

    document.documentElement.setAttribute('data-lang', lang);
    toggleUi();

    if (collect) { translateTitle(); walk(document.body); observe(); return; }
    if (lang !== 'zh') return;

    document.documentElement.lang = 'zh-Hans';
    // synchronous load so the page is translated before animations measure it
    try {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', 'data/i18n/zh.json', false);
        xhr.send();
        if (xhr.status !== 200) throw new Error(xhr.status);
        dict = JSON.parse(xhr.responseText);
        dict.text = dict.text || {}; dict.html = dict.html || {};
    } catch (e) {
        document.documentElement.lang = 'en';
        return;
    }
    translateTitle();
    walk(document.body);
    observe();
})();
