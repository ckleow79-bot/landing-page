/**
 * Programmes loader
 * B & K Group Website
 *
 * Source of truth order:
 *   1. Supabase table `programmes` (published = true)
 *   2. data/programmes.json (fallback / offline / local dev)
 *
 * Renders into:
 *   [data-programmes="featured"]  -> next N featured/upcoming cards (home, academy)
 *   [data-programmes="list"]      -> full filterable list (programmes.html)
 * Handles the registration modal and ICS download.
 */
(function () {
    'use strict';

    const PROVIDERS = {
        'bk-training': { name: 'B & K Training Services PLT', short: 'B & K Training' },
        'high-impact': { name: 'High Impact Training Services PLT', short: 'High Impact' },
        'bk-academy': { name: 'B & K Academy PLT', short: 'B & K Academy' }
    };

    const LOC = (window.BKi18n && window.BKi18n.lang === 'zh') ? 'zh-CN' : 'en-MY';
    const fmtDate = new Intl.DateTimeFormat(LOC, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' });
    const fmtDay = new Intl.DateTimeFormat(LOC, { day: '2-digit', timeZone: 'Asia/Kuala_Lumpur' });
    const fmtMon = new Intl.DateTimeFormat(LOC, { month: 'short', timeZone: 'Asia/Kuala_Lumpur' });
    const fmtTime = new Intl.DateTimeFormat(LOC, { hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur' });
    const fmtMYR = new Intl.NumberFormat('en-MY', { style: 'currency', currency: 'MYR', maximumFractionDigits: 0 });

    let cache = null;

    async function fetchFromSupabase() {
        if (window.BKSupabaseReady) { try { await window.BKSupabaseReady; } catch (e) { /* ignore */ } }
        if (!window.supabaseClient || typeof window.supabaseClient.from !== 'function') return null;
        try {
            const timeout = new Promise(res => setTimeout(() => res({ data: null, error: 'timeout' }), 1500));
            const { data, error } = await Promise.race([window.supabaseClient
                .from('programmes')
                .select('*')
                .eq('published', true)
                .order('start_date', { ascending: true }), timeout]);
            if (error || !data || !data.length) return null;
            return data;
        } catch (e) {
            return null;
        }
    }

    async function fetchFromJson() {
        const res = await fetch('data/programmes.json', { cache: 'no-cache' });
        if (!res.ok) throw new Error('programmes.json not found');
        const json = await res.json();
        return json.programmes || [];
    }

    async function loadProgrammes() {
        if (cache) return cache;
        let list = await fetchFromSupabase();
        let source = 'supabase';
        if (!list) { list = await fetchFromJson(); source = 'json'; }
        else {
            // keep the published history: past sessions from the JSON file that the database does not hold
            try { const json = await fetchFromJson(); const have = new Set(list.map(p => p.slug)); list = list.concat(json.filter(p => p.status === 'past' && !have.has(p.slug))); } catch (e) { /* ignore */ }
        }
        const now = Date.now();
        list = list.map(p => {
            const end = new Date(p.end_date || p.start_date).getTime();
            const status = (p.status === 'upcoming' && end < now) ? 'past' : p.status;
            return { ...p, status, _end: end, _start: new Date(p.start_date).getTime() };
        }).sort((a, b) => a._start - b._start);
        cache = { list, source };
        document.documentElement.setAttribute('data-programmes-source', source);
        return cache;
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    // only https links from the data source are allowed on cards
    const safeUrl = u => (/^https:\/\//i.test(String(u || '').trim()) ? String(u).trim() : '');

    function dateRange(p) {
        const s = new Date(p.start_date), e = new Date(p.end_date || p.start_date);
        const sameDay = fmtDate.format(s) === fmtDate.format(e);
        return sameDay ? fmtDate.format(s) : `${fmtDay.format(s)} ${fmtMon.format(s)} – ${fmtDate.format(e)}`;
    }

    function feeLine(p) {
        if (p.fee_myr == null) return p.provider === 'external'
            ? `<span class="prog-fee prog-fee-na">Fee and registration via ${escapeHtml(p.organiser || 'organiser')}</span>`
            : '<span class="prog-fee prog-fee-na">Fee on enquiry</span>';
        const eb = p.early_bird_fee_myr && p.early_bird_until && new Date(p.early_bird_until + 'T23:59:59+08:00').getTime() > Date.now();
        if (eb) {
            return `<span class="prog-fee"><s>${fmtMYR.format(p.fee_myr)}</s> <strong>${fmtMYR.format(p.early_bird_fee_myr)}</strong><small>early bird until ${fmtDate.format(new Date(p.early_bird_until))}</small></span>`;
        }
        return `<span class="prog-fee"><strong>${fmtMYR.format(p.fee_myr)}</strong><small>per participant</small></span>`;
    }

    function badge(p) {
        const map = { upcoming: '', full: 'Fully booked', past: 'Completed', cancelled: 'Cancelled' };
        return map[p.status] ? `<span class="prog-badge prog-badge-${p.status}">${map[p.status]}</span>` : '';
    }

    function card(p, compact) {
        const s = new Date(p.start_date);
        const prov = p.provider === 'external'
            ? { short: p.organiser || 'External organiser', name: p.organiser || 'External organiser' }
            : (PROVIDERS[p.provider] || { short: p.provider, name: p.provider });
        const highlights = (Array.isArray(p.highlights) ? p.highlights : []).slice(0, compact ? 0 : 4)
            .map(h => `<li>${escapeHtml(h)}</li>`).join('');
        const canRegister = p.status === 'upcoming';
        const regBtn = safeUrl(p.register_url)
            ? `<a class="btn btn-primary btn-sm" href="${escapeHtml(safeUrl(p.register_url))}" target="_blank" rel="noopener">Register</a>`
            : `<button class="btn btn-primary btn-sm" data-register="${escapeHtml(p.slug)}" ${canRegister ? '' : 'disabled'}>${canRegister ? (p.provider === 'external' ? 'Enquire' : 'Register') : 'Closed'}</button>`;
        return `
        <article class="prog-card reveal" data-provider="${escapeHtml(p.provider)}" data-category="${escapeHtml(p.category)}" data-status="${p.status}" data-slug="${escapeHtml(p.slug)}">
            <div class="prog-date">
                <span class="prog-day">${fmtDay.format(s)}</span>
                <span class="prog-mon">${fmtMon.format(s)} ${s.getFullYear()}</span>
            </div>
            <div class="prog-body">
                <div class="prog-meta">
                    <span class="prog-provider">${escapeHtml(prov.short)}</span>
                    <span class="prog-dot"></span>
                    <span>${escapeHtml(p.category)}</span>
                    ${p.hrdc_claimable ? '<span class="prog-dot"></span><span class="prog-hrdc">HRD Corp claimable</span>' : ''}
                    ${badge(p)}
                </div>
                <h3 class="prog-title" data-i18n-skip>${escapeHtml(p.title)}</h3>
                ${p.subtitle ? `<p class="prog-subtitle" data-i18n-skip>${escapeHtml(p.subtitle)}</p>` : ''}
                <ul class="prog-facts">
                    <li><i class="far fa-calendar"></i> ${dateRange(p)}, ${fmtTime.format(s)}${p.end_date ? ' – ' + fmtTime.format(new Date(p.end_date)) : ''}</li>
                    <li><i class="fas fa-map-marker-alt"></i> ${escapeHtml(p.mode || '')}${p.venue ? ' · ' + escapeHtml(p.venue) : ''}</li>
                    ${p.cpd_hours ? `<li><i class="fas fa-certificate"></i> ${p.cpd_hours} CPD hours</li>` : ''}
                    ${p.language ? `<li><i class="fas fa-language"></i> ${escapeHtml(p.language)}</li>` : ''}
                </ul>
                ${highlights ? `<ul class="prog-highlights" data-i18n-skip>${highlights}</ul>` : ''}
                ${p.includes && p.status !== 'past' ? `<p class="prog-includes"><strong>Fee includes:</strong> ${escapeHtml(p.includes)}</p>` : ''}
                ${p.hrdc_claimable && p.status !== 'past' ? `<p class="prog-tp">HRD Corp training provider: <strong>${escapeHtml(prov.name)}</strong></p>` : ''}
            </div>
            <div class="prog-aside">
                ${feeLine(p)}
                <div class="prog-actions">
                    ${regBtn}
                    ${safeUrl(p.brochure_url) ? `<a class="btn btn-outline btn-sm" href="${escapeHtml(safeUrl(p.brochure_url))}" target="_blank" rel="noopener">Brochure</a>` : ''}
                    <button class="btn-link" data-ics="${escapeHtml(p.slug)}"><i class="far fa-calendar-plus"></i> Add to calendar</button>
                </div>
            </div>
        </article>`;
    }

    function renderFeatured(container, list) {
        const n = parseInt(container.getAttribute('data-limit') || '3', 10);
        const items = list.filter(p => p.status === 'upcoming').sort((a, b) => (b.featured - a.featured) || (a._start - b._start)).slice(0, n);
        container.innerHTML = items.length
            ? items.map(p => card(p, true)).join('')
            : '<p class="prog-empty">New programmes are being scheduled. Leave your email below and we will notify you.</p>';
    }

    function renderList(container, list) {
        const params = new URLSearchParams(location.search);
        const state = {
            provider: params.get('provider') || 'all',
            category: params.get('category') || 'all',
            when: params.get('when') || 'upcoming'
        };
        const cats = [...new Set(list.map(p => p.category))].sort();
        const filterBar = document.querySelector('[data-programmes-filters]');
        if (filterBar) {
            filterBar.innerHTML = `
            <div class="prog-filter-group" role="group" aria-label="Provider">
                <button class="category-btn ${state.provider === 'all' ? 'active' : ''}" data-f="provider" data-v="all">All providers</button>
                ${Object.entries(PROVIDERS).map(([k, v]) => `<button class="category-btn ${state.provider === k ? 'active' : ''}" data-f="provider" data-v="${k}">${v.short}</button>`).join('')}
                <button class="category-btn ${state.provider === 'external' ? 'active' : ''}" data-f="provider" data-v="external">Guest speaking</button>
            </div>
            <div class="prog-filter-group" role="group" aria-label="Topic">
                <button class="category-btn ${state.category === 'all' ? 'active' : ''}" data-f="category" data-v="all">All topics</button>
                ${cats.map(c => `<button class="category-btn ${state.category === c ? 'active' : ''}" data-f="category" data-v="${escapeHtml(c)}">${escapeHtml(c)}</button>`).join('')}
            </div>
            <div class="prog-filter-group" role="group" aria-label="Timing">
                <button class="category-btn ${state.when === 'upcoming' ? 'active' : ''}" data-f="when" data-v="upcoming">Upcoming</button>
                <button class="category-btn ${state.when === 'past' ? 'active' : ''}" data-f="when" data-v="past">Past</button>
            </div>`;
            filterBar.addEventListener('click', e => {
                const b = e.target.closest('[data-f]');
                if (!b) return;
                state[b.dataset.f] = b.dataset.v;
                filterBar.querySelectorAll(`[data-f="${b.dataset.f}"]`).forEach(x => x.classList.toggle('active', x === b));
                const url = new URL(location.href);
                Object.entries(state).forEach(([k, v]) => v === 'all' || (k === 'when' && v === 'upcoming') ? url.searchParams.delete(k) : url.searchParams.set(k, v));
                history.replaceState(null, '', url);
                apply();
            });
        }
        function apply() {
            const items = list.filter(p =>
                (state.provider === 'all' || p.provider === state.provider) &&
                (state.category === 'all' || p.category === state.category) &&
                (state.when === 'past' ? p.status === 'past' : p.status !== 'past')
            );
            if (state.when === 'past') items.sort((a, b) => b._start - a._start);
            container.innerHTML = items.length
                ? items.map(p => card(p, false)).join('')
                : '<p class="prog-empty">No programmes match this filter yet. Register your interest and we will notify you when one is scheduled.</p>';
            if (window.BKMotion && window.BKMotion.refresh) window.BKMotion.refresh();
        }
        apply();
    }

    /* ---------- Registration modal ---------- */
    function ensureModal() {
        let m = document.getElementById('prog-modal');
        if (m) return m;
        m = document.createElement('div');
        m.id = 'prog-modal';
        m.className = 'prog-modal';
        m.setAttribute('role', 'dialog');
        m.setAttribute('aria-modal', 'true');
        m.setAttribute('aria-labelledby', 'prog-modal-title');
        m.innerHTML = `
        <div class="prog-modal-backdrop" data-close></div>
        <div class="prog-modal-card">
            <button class="prog-modal-close" data-close aria-label="Close"><i class="fas fa-times"></i></button>
            <p class="prog-modal-kicker">Register</p>
            <h3 class="prog-modal-title" id="prog-modal-title"></h3>
            <p class="prog-modal-sub"></p>
            <div class="prog-modal-recap"></div>
            <form class="prog-form" novalidate>
                <input type="hidden" name="programme_slug">
                <input type="hidden" name="programme_title">
                <div class="form-row">
                    <div class="form-group"><label>Full name *</label><input aria-label="Full name" name="name" required autocomplete="name"></div>
                    <div class="form-group"><label>Email *</label><input aria-label="Email" type="email" name="email" required autocomplete="email"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>Mobile</label><input aria-label="Mobile" type="tel" name="phone" autocomplete="tel" placeholder="+60"></div>
                    <div class="form-group"><label>Company</label><input aria-label="Company" name="company" autocomplete="organization"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>Designation</label><input aria-label="Designation" name="designation" autocomplete="organization-title"></div>
                    <div class="form-group"><label>No. of participants</label><input aria-label="No. of participants" type="number" name="pax" min="1" max="50" value="1"></div>
                </div>
                <div class="form-group prog-others"><label>Other attendees</label><textarea aria-label="Other attendees" name="attendees" rows="3" placeholder="One per line: name, email, designation"></textarea></div>
                <div class="form-group"><label>Message</label><textarea aria-label="Message" name="message" rows="3" placeholder="Invoice details, HRD Corp grant reference, dietary needs..."></textarea></div>
                <label class="prog-check prog-hrdc-check"><input type="checkbox" name="hrdc_claim"> We intend to claim under HRD Corp</label>
                <label class="prog-check"><input type="checkbox" name="consent_pdpa" required> I consent to B &amp; K Group processing my personal data to administer this registration, in line with the <a href="privacy-policy.html" target="_blank">Privacy Notice</a> (PDPA 2010). *</label>
                <button type="submit" class="btn btn-primary btn-full">Submit registration</button>
                <div class="form-message" aria-live="polite"></div>
            </form>
        </div>`;
        document.body.appendChild(m);
        m.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeModal(); });
        document.addEventListener('keydown', e => {
            if (!m.classList.contains('is-open')) return;
            if (e.key === 'Escape') { closeModal(); return; }
            if (e.key !== 'Tab') return;
            const f = [...m.querySelectorAll('button, [href], input:not([type=hidden]), textarea, select')].filter(x => !x.disabled && x.offsetParent !== null);
            if (!f.length) return;
            if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
            else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
        });
        m.querySelector('form').addEventListener('submit', submitRegistration);
        return m;
    }

    let lastTrigger = null;
    function openModal(p) {
        lastTrigger = document.activeElement;
        const m = ensureModal();
        m._prog = p;
        m.querySelector('.prog-modal-title').textContent = p.title;
        m.querySelector('.prog-modal-sub').textContent = `${dateRange(p)} · ${p.mode || ''}${p.venue ? ' · ' + p.venue : ''}`;
        const f = m.querySelector('form');
        f.reset();
        f.programme_slug.value = p.slug;
        f.programme_title.value = p.title;
        const recap = m.querySelector('.prog-modal-recap');
        recap.textContent = '';
        const add = (label, val) => { if (!val) return; const r = document.createElement('p'); const b = document.createElement('strong'); b.textContent = label + ' '; r.append(b, document.createTextNode(val)); recap.appendChild(r); };
        add('Fee:', p.fee_myr != null ? fmtMYR.format(p.fee_myr) + ' per participant' : '');
        add('Includes:', p.includes || '');
        add('HRD Corp training provider:', p.hrdc_claimable ? (PROVIDERS[p.provider] || {}).name : '');
        m.querySelector('.prog-hrdc-check').hidden = p.provider === 'external';
        m.querySelector('.prog-modal-kicker').textContent = p.provider === 'external' ? 'Enquire' : 'Register';
        f.querySelector('.form-message').textContent = '';
        f.querySelector('.form-message').className = 'form-message';
        m.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        setTimeout(() => f.name.focus(), 50);
    }
    function closeModal() {
        const m = document.getElementById('prog-modal');
        if (!m) return;
        m.classList.remove('is-open');
        document.body.style.overflow = '';
        if (lastTrigger && document.contains(lastTrigger)) lastTrigger.focus();
    }

    async function submitRegistration(e) {
        e.preventDefault();
        const f = e.target;
        const msg = f.querySelector('.form-message');
        const btn = f.querySelector('button[type=submit]');
        const data = Object.fromEntries(new FormData(f).entries());
        data.hrdc_claim = !!f.hrdc_claim.checked;
        data.consent_pdpa = !!f.consent_pdpa.checked;
        data.pax = parseInt(data.pax || '1', 10);
        const others = (data.attendees || '').trim();
        delete data.attendees;
        if (others) data.message = ('Other attendees:\n' + others + (data.message ? '\n\n' + data.message : '')).trim();
        const p = (document.getElementById('prog-modal') || {})._prog || {};
        if (!data.name || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
            msg.textContent = 'Please enter your name and a valid email.'; msg.className = 'form-message error'; return;
        }
        if (!data.consent_pdpa) {
            msg.textContent = 'Consent is required to process your registration.'; msg.className = 'form-message error'; return;
        }
        btn.disabled = true; btn.textContent = 'Submitting…';
        try {
            if (!window.supabaseClient) throw new Error('offline');
            const { error } = await window.supabaseClient.from('programme_registrations').insert([data]);
            if (error) throw error;
            msg.textContent = 'Thank you. Your registration is received. We will email the confirmation and invoice details shortly.';
            msg.className = 'form-message success';
            f.querySelectorAll('input:not([type=hidden]),textarea').forEach(i => i.disabled = true);
            btn.textContent = 'Submitted';
            if (typeof gtag === 'function') gtag('event', 'programme_register', { programme: data.programme_slug });
        } catch (err) {
            const lines = [
                'Programme registration from the B & K website',
                `Programme: ${data.programme_title}`,
                p.start_date ? `Date: ${dateRange(p)}, ${fmtTime.format(new Date(p.start_date))}` : '',
                p.venue ? `Venue: ${p.venue}` : '',
                `Name: ${data.name}`, `Email: ${data.email}`, data.phone ? `Phone: ${data.phone}` : '',
                data.company ? `Company: ${data.company}` : '', data.designation ? `Designation: ${data.designation}` : '',
                `Participants: ${data.pax}`, `HRD Corp claim: ${data.hrdc_claim ? 'Yes' : 'No'}`, '', data.message || ''
            ];
            if (window.BKFormFallback) window.BKFormFallback(msg, lines, `Registration: ${data.programme_title}`);
            else { msg.textContent = 'We could not reach the registration service. Please email keith@bkcorporate.com or WhatsApp +60 11-3063 6198.'; msg.className = 'form-message error'; }
            btn.disabled = false; btn.textContent = 'Submit registration';
        }
    }

    /* ---------- ICS ---------- */
    function downloadIcs(p) {
        const toIcs = d => new Date(d).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
        const prov = PROVIDERS[p.provider] || { name: p.provider };
        const ics = [
            'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//B & K Group//Programmes//EN', 'BEGIN:VEVENT',
            `UID:${p.slug}@bkcorporate.com`, `DTSTAMP:${toIcs(Date.now())}`,
            `DTSTART:${toIcs(p.start_date)}`, `DTEND:${toIcs(p.end_date || p.start_date)}`,
            `SUMMARY:${p.title}`, `DESCRIPTION:${(p.subtitle || '')} (${prov.name})`,
            `LOCATION:${p.venue || p.mode || ''}`, 'END:VEVENT', 'END:VCALENDAR'
        ].join('\r\n');
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' }));
        a.download = `${p.slug}.ics`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }

    /* ---------- Boot ---------- */
    async function init() {
        const targets = document.querySelectorAll('[data-programmes]');
        const counts = document.querySelectorAll('[data-count-src="upcoming"]');
        if (!targets.length && !counts.length) return;
        let data;
        try { data = await loadProgrammes(); }
        catch (e) {
            targets.forEach(t => t.innerHTML = '<p class="prog-empty">Programme list is temporarily unavailable.</p>');
            return;
        }
        // live stat: number of upcoming public sessions (counted up by cinematic.js when it scrolls in)
        const n = data.list.filter(p => p.status === 'upcoming' && p.provider !== 'external').length;
        counts.forEach(el => { el.dataset.count = n; if (!el.dataset.counting) el.textContent = n; });
        targets.forEach(t => t.getAttribute('data-programmes') === 'list' ? renderList(t, data.list) : renderFeatured(t, data.list));
        document.addEventListener('click', e => {
            const r = e.target.closest('[data-register]');
            if (r && !r.disabled) { const p = data.list.find(x => x.slug === r.dataset.register); if (p) openModal(p); }
            const i = e.target.closest('[data-ics]');
            if (i) { const p = data.list.find(x => x.slug === i.dataset.ics); if (p) downloadIcs(p); }
        });
        if (window.BKMotion && window.BKMotion.refresh) window.BKMotion.refresh();
        // ?open=<slug> (from the next-programme ribbon): bring that card into view
        const open = new URLSearchParams(location.search).get('open');
        const card = open && document.querySelector(`.prog-card[data-slug="${CSS.escape(open)}"]`);
        if (card) {
            card.classList.add('is-target');
            setTimeout(() => {
                const y = card.getBoundingClientRect().top + window.scrollY - 170;
                if (window.BKMotion && window.BKMotion.lenis) window.BKMotion.lenis.scrollTo(y); else window.scrollTo({ top: y, behavior: 'smooth' });
            }, 350);
        }
    }

    // supabase.js initialises the client on DOMContentLoaded; run after it.
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 0));
    else setTimeout(init, 0);

    window.BKProgrammes = { load: loadProgrammes, openModal };
})();
