/**
 * Free tax tools: stamp duty calculator and tax deadline calendar.
 * Everything runs in the browser; nothing is sent anywhere.
 * Rates and rules below were checked against primary sources as at 7 Nov 2026:
 *  - LHDN, Garis Panduan Pengenaan Duti Setem, Jadual Pertama Akta Setem 1949 (30 Jun 2026)
 *  - MOF, Budget 2026 speech, Lampiran 14-15
 *  - LHDN, Program Memfail Borang Nyata 2026 (updated 1 Apr 2026); LHDN CP204 page (s.107C ITA 1967)
 * Update the numbers here when the law changes, and the "as at" line on tools.html.
 * English strings are translated by js/i18n.js (dictionary keys in data/i18n/*.json).
 */
(function () {
    'use strict';
    const lang = (window.BKi18n && window.BKi18n.lang) || 'en';
    const locale = lang === 'zh' ? 'zh-CN' : lang === 'ms' ? 'ms-MY' : 'en-MY';
    const rm = n => 'RM ' + n.toLocaleString('en-MY', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    // ---------- Stamp duty ----------
    // Item 32(a): RM per RM100 or part, by band
    const TRANSFER = [[100000, 1, 'First RM 100,000'], [400000, 2, 'Next RM 400,000'], [500000, 3, 'Next RM 500,000'], [Infinity, 4, 'Above RM 1,000,000']];
    const FOREIGN = { res: 8, other: 4 }; // items 32(ab) from 1 Jan 2026, 32(aa)
    const LOAN_PER_1000 = 5;              // item 22(1)(a)
    const TENANCY = { 1: 1, 3: 3, 5: 5, 7: 7 }; // item 49(a): RM per RM250 of annual rent or part, by term

    const sd = document.getElementById('sd-form');
    if (sd) {
        const out = document.getElementById('sd-result');
        const num = id => { const v = parseFloat(String(document.getElementById(id).value).replace(/[^\d.]/g, '')); return isFinite(v) && v > 0 ? v : 0; };
        const show = () => {
            const kind = sd.querySelector('input[name=sd-kind]:checked').value;
            sd.querySelectorAll('[data-for]').forEach(el => { el.hidden = el.dataset.for !== kind; });
            let total = 0, rows = [], notes = [];
            if (kind === 'transfer') {
                const base = Math.max(num('sd-price'), num('sd-mv'));
                const buyer = document.getElementById('sd-buyer').value;
                if (base) {
                    if (buyer === 'local') {
                        let left = base;
                        TRANSFER.forEach(([band, rate, label]) => {
                            if (left <= 0) return;
                            const part = Math.min(left, band); left -= part;
                            const duty = Math.ceil(part / 100) * rate;
                            total += duty; rows.push([label, rate + '%', duty]);
                        });
                        if (base <= 500000) notes.push('First home bought by a Malaysian citizen for up to RM 500,000? Budget 2026 proposes a full exemption on the transfer and the loan agreement, for agreements signed from 1 January 2026 to 31 December 2027. Check that the exemption order is in force before relying on it.');
                    } else {
                        const rate = FOREIGN[buyer];
                        total = Math.ceil(base / 100) * rate;
                        rows.push([buyer === 'res' ? 'Foreign buyer, residential property' : 'Foreign buyer, other property', rate + '%', total]);
                    }
                    notes.push('Duty is charged on the higher of the price and the market value.');
                }
            } else if (kind === 'loan') {
                const loan = num('sd-loan');
                if (loan) { total = Math.ceil(loan / 1000) * LOAN_PER_1000; rows.push(['RM 5 for every RM 1,000 or part', '0.5%', total]); }
            } else {
                const annual = num('sd-rent') * 12;
                const term = document.getElementById('sd-term').value;
                if (annual) {
                    const units = Math.ceil(annual / 250);
                    total = units * TENANCY[term];
                    rows.push(['Annual rent', '', annual, true]);
                    rows.push(['Rate per RM 250 or part', 'RM ' + TENANCY[term], total]);
                    notes.push('Since 1 January 2026, tenancy agreements are stamped under self-assessment on e-Duti Setem in MyTax.');
                }
            }
            if (!rows.length) { out.innerHTML = '<p class="tl-empty">Enter an amount to see the duty.</p>'; return; }
            out.innerHTML =
                '<p class="tl-k">Estimated stamp duty</p>' +
                `<p class="tl-total" data-i18n-skip>${rm(total)}</p>` +
                '<ul class="tl-rows">' + rows.map(([l, r, v, plain]) =>
                    `<li><span>${esc(l)}</span><b data-i18n-skip>${plain ? rm(v) : (r ? esc(r) + ' · ' : '') + rm(v)}</b></li>`).join('') + '</ul>' +
                notes.map(n => `<p class="tl-note">${esc(n)}</p>`).join('');
        };
        sd.addEventListener('input', show);
        sd.addEventListener('change', show);
        sd.addEventListener('submit', e => e.preventDefault());
        show();
    }

    // ---------- Deadline calendar ----------
    const dl = document.getElementById('dl-form');
    if (dl) {
        const list = document.getElementById('dl-list');
        const icsBtn = document.getElementById('dl-ics');
        const fyeSel = document.getElementById('dl-fye');
        const monthName = new Intl.DateTimeFormat(locale, { month: 'long' });
        for (let m = 0; m < 12; m++) {
            const o = document.createElement('option');
            o.value = m; o.textContent = monthName.format(new Date(2026, m, 15));
            o.setAttribute('data-i18n-skip', '');
            if (m === 11) o.selected = true;
            fyeSel.appendChild(o);
        }
        const fmt = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
        const endOf = (y, m) => new Date(y, m + 1, 0); // last day of month m (0-based, may overflow)
        const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const horizon = addDays(today, 366);
        const inDays = n => n === 0 ? ({ zh: '今天', ms: 'hari ini' }[lang] || 'today') : ({ zh: `${n} 天后`, ms: `dalam ${n} hari` }[lang] || `in ${n} days`);
        let items = [];

        const build = () => {
            const who = dl.querySelector('input[name=dl-who]:checked').value;
            dl.querySelectorAll('[data-for]').forEach(el => { el.hidden = el.dataset.for !== who; });
            items = [];
            const add = (date, title, monthly) => { if (date >= today && date <= horizon) items.push({ date, title, monthly }); };
            const y = today.getFullYear();
            if (who === 'company') {
                const m = +fyeSel.value;
                for (let fy = y - 2; fy <= y + 1; fy++) {
                    const fye = endOf(fy, m);
                    add(endOf(fy, m + 7), 'Form C due (7 months after year end)');
                    add(endOf(fy, m + 8), 'Form C: last day with the e-Filing grace period');
                    add(addDays(fye, -29), 'CP204: submit the tax estimate for the next year');
                    const start = addDays(fye, 1); // next basis period
                    [[6, 'CP204A: revise the estimate by the end of the 6th month'], [9, 'CP204A: revise the estimate by the end of the 9th month'], [11, 'CP204A: revise the estimate by the end of the 11th month']]
                        .forEach(([k, t]) => add(endOf(start.getFullYear(), start.getMonth() + k - 1), t));
                }
                let next15 = new Date(y, today.getMonth(), 15); if (next15 < today) next15 = new Date(y, today.getMonth() + 1, 15);
                add(next15, 'CP204 instalment due (the 15th of every month)', true);
            } else if (who === 'individual') {
                for (const yy of [y, y + 1]) {
                    add(new Date(yy, 3, 30), 'Form BE due (no business income)');
                    add(new Date(yy, 4, 15), 'Form BE: last day with the e-Filing grace period');
                    add(new Date(yy, 5, 30), 'Form B due (with business income)');
                    add(new Date(yy, 6, 15), 'Form B: last day with the e-Filing grace period');
                }
            } else {
                for (const yy of [y, y + 1]) {
                    add(new Date(yy, 1, 28), 'EA forms to employees');
                    add(new Date(yy, 2, 31), 'Form E due (employer return)');
                }
            }
            items.sort((a, b) => a.date - b.date);
            list.innerHTML = items.map(it => {
                const n = Math.round((it.date - today) / 864e5);
                return `<li class="${n <= 30 ? 'is-soon' : ''}"><time data-i18n-skip datetime="${iso(it.date)}">${fmt.format(it.date)}</time><span>${esc(it.title)}</span><em data-i18n-skip>${inDays(n)}</em></li>`;
            }).join('');
            icsBtn.disabled = !items.length;
        };
        const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        const tr = s => (window.BKi18n && window.BKi18n.tr ? window.BKi18n.tr(s) : s);

        icsBtn.addEventListener('click', () => {
            const stamp = iso(new Date()).replace(/-/g, '') + 'T000000Z';
            const ev = items.map((it, i) => {
                const d = iso(it.date).replace(/-/g, ''), e = iso(addDays(it.date, 1)).replace(/-/g, '');
                return ['BEGIN:VEVENT', `UID:bk-${d}-${i}@bkcorporate.com`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${d}`, `DTEND;VALUE=DATE:${e}`,
                    `SUMMARY:${tr(it.title).replace(/[,;]/g, m => '\\' + m)}`, it.monthly ? 'RRULE:FREQ=MONTHLY;BYMONTHDAY=15;COUNT=12' : '',
                    'DESCRIPTION:B & K Group tax deadline calendar. General guide only; check LHDN for your case.', 'END:VEVENT'].filter(Boolean).join('\r\n');
            });
            const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//B & K Group//Tax deadlines//EN', 'CALSCALE:GREGORIAN', ...ev, 'END:VCALENDAR'].join('\r\n');
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' }));
            a.download = 'bk-tax-deadlines.ics';
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        });
        dl.addEventListener('change', build);
        dl.addEventListener('submit', e => e.preventDefault());
        build();
    }
})();
