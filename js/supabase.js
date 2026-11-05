/**
 * Forms and data: Supabase client, quote form, newsletter.
 *
 * - The client is created as soon as this file runs and exposed as window.supabaseClient,
 *   with window.BKSupabaseReady resolving when it is ready (programmes.js waits for it).
 * - Every form is always handled here (preventDefault), so nothing ever ends up in the URL,
 *   even when the Supabase library failed to load.
 * - When the database cannot be reached the visitor is told plainly and offered
 *   WhatsApp / email with their details filled in. Nothing pretends to be sent.
 * - Access to stored data is admin-only (see migrations/003_admin_only_access.sql).
 */
(function () {
    'use strict';

    const SUPABASE_URL = (window.ENV && window.ENV.SUPABASE_URL) || 'https://uloodavzquardkeecrlx.supabase.co';
    const SUPABASE_KEY = (window.ENV && window.ENV.SUPABASE_KEY) || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVsb29kYXZ6cXVhcmRrZWVjcmx4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5MTc3MjMsImV4cCI6MjA4ODQ5MzcyM30.VqUNZWMKcqLolTnFDlOP874871r6AQmIEVnihdrAtwk';
    const WA = '601130636198';
    const MAIL = 'keith@bkcorporate.com';
    const zh = () => !!(window.BKi18n && window.BKi18n.lang === 'zh');
    const T = (en, cn) => (zh() ? cn : en);

    let client = null;
    try {
        if (window.supabase && typeof window.supabase.createClient === 'function') client = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
    } catch (e) { client = null; }
    window.supabaseClient = client;
    window.BKSupabaseReady = Promise.resolve(client);

    /* ---------- helpers ---------- */
    const validEmail = v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
    const validPhone = v => /^[\d\s\-+()]{8,}$/.test(v);
    const optText = sel => (sel && sel.value ? sel.options[sel.selectedIndex].text : '');

    function fieldError(input, msg) {
        if (!input) return;
        input.classList.add('error');
        input.setAttribute('aria-invalid', 'true');
        let el = input.parentElement.querySelector('.field-error');
        if (!el) { el = document.createElement('span'); el.className = 'field-error'; el.id = input.id + '-err'; input.parentElement.appendChild(el); }
        el.textContent = msg;
        input.setAttribute('aria-describedby', el.id);
        input.addEventListener('input', () => { input.classList.remove('error'); input.removeAttribute('aria-invalid'); el.remove(); }, { once: true });
    }
    function clearErrors(form) {
        form.querySelectorAll('.field-error').forEach(e => e.remove());
        form.querySelectorAll('.error').forEach(e => { e.classList.remove('error'); e.removeAttribute('aria-invalid'); });
    }
    function status(el, msg, type, keep) {
        el.textContent = msg;
        el.className = 'form-message ' + type;
        el.style.display = 'block';
        el.setAttribute('role', type === 'error' ? 'alert' : 'status');
        if (!keep && type === 'success') setTimeout(() => { el.style.display = 'none'; }, 8000);
    }

    /** The message could not be sent: say so and offer one-tap WhatsApp / email with everything filled in. */
    function fallback(el, lines, subject, prefer) {
        const body = lines.filter(Boolean).join('\n');
        el.textContent = '';
        el.className = 'form-message error';
        el.style.display = 'block';
        el.setAttribute('role', 'alert');
        const p = document.createElement('p');
        p.textContent = T('Sorry, the form could not be sent and your message has NOT reached us. Please use one of these instead (your details are filled in). We reply the same business day.',
                          '抱歉，表格暂时无法发送，您的信息尚未送出。请用以下方式联系我们（内容已帮您填好），我们会在同一个工作日内回复。');
        const row = document.createElement('div'); row.className = 'form-fallback';
        const wa = document.createElement('a'); wa.className = 'btn btn-primary btn-sm'; wa.target = '_blank'; wa.rel = 'noopener';
        wa.href = 'https://wa.me/' + WA + '?text=' + encodeURIComponent(body); wa.textContent = 'WhatsApp';
        const em = document.createElement('a'); em.className = 'btn btn-outline btn-sm';
        em.href = 'mailto:' + MAIL + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body); em.textContent = T('Email', '电邮');
        if (prefer === 'email') { em.className = 'btn btn-primary btn-sm'; wa.className = 'btn btn-outline btn-sm'; row.append(em, wa); } else row.append(wa, em);
        el.append(p, row);
        el.setAttribute('tabindex', '-1');
        el.focus({ preventScroll: true });
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    window.BKFormFallback = fallback; // used by the programme registration modal

    /* ---------- quote / contact form ---------- */
    function initContact() {
        const form = document.getElementById('contact-form');
        if (!form) return;
        const $ = id => form.querySelector('#' + id);
        form.addEventListener('submit', async e => {
            e.preventDefault();
            clearErrors(form);
            const msgEl = document.getElementById('contact-message-status');
            const btn = form.querySelector('button[type="submit"]');
            const d = {
                name: $('contact-name').value.trim(),
                email: $('contact-email').value.trim(),
                phone: $('contact-phone').value.trim(),
                company: $('contact-company').value.trim(),
                topic: $('contact-industry').value,
                topicText: optText($('contact-industry')),
                location: optText($('contact-location')),
                urgency: optText($('contact-urgency')),
                message: $('contact-message').value.trim(),
                reply: (form.querySelector('input[name="reply"]:checked') || {}).value || 'whatsapp'
            };
            const replyText = { whatsapp: 'WhatsApp', email: T('Email', '电邮'), video: T('Video call', '视频通话'), phone: T('Phone call', '电话') }[d.reply];
            const speak = d.topic === 'speaking' ? [
                $('sp-date') && $('sp-date').value ? T('Event date: ', '活动日期：') + $('sp-date').value : '',
                $('sp-aud') && $('sp-aud').value ? T('Audience: ', '听众人数：') + $('sp-aud').value : '',
                optText($('sp-lang')) ? T('Language: ', '语言：') + optText($('sp-lang')) : '',
                optText($('sp-fmt')) ? T('Format: ', '形式：') + optText($('sp-fmt')) : ''
            ].filter(Boolean) : [];
            const inhouse = d.topic === 'inhouse' ? [
                $('ih-pax') && $('ih-pax').value ? T('Participants: ', '人数：') + $('ih-pax').value : '',
                optText($('ih-lang')) ? T('Language: ', '语言：') + optText($('ih-lang')) : '',
                $('ih-month') && $('ih-month').value ? T('Preferred month: ', '希望月份：') + $('ih-month').value : '',
                optText($('ih-hrdc')) ? T('HRD Corp claim: ', 'HRD Corp 申索：') + optText($('ih-hrdc')) : ''
            ].filter(Boolean) : [];

            let ok = true;
            if (!d.name) { fieldError($('contact-name'), T('Please enter your name', '请填写姓名')); ok = false; }
            const needPhone = d.reply === 'whatsapp' || d.reply === 'phone';
            if (!d.phone && !d.email) {
                fieldError(needPhone ? $('contact-phone') : $('contact-email'), T('Please give a phone number or an email so we can reply', '请留下电话或电邮，以便我们回复')); ok = false;
            } else {
                if (d.phone && !validPhone(d.phone)) { fieldError($('contact-phone'), T('Please check the number (at least 8 digits)', '请检查号码（至少8位数字）')); ok = false; }
                else if (needPhone && !d.phone) { fieldError($('contact-phone'), T('You chose ' + replyText + ': please add a number', '您选择了' + replyText + '，请填写号码')); ok = false; }
                if (d.email && !validEmail(d.email)) { fieldError($('contact-email'), T('Please check the email address', '请检查电邮地址')); ok = false; }
                else if (d.reply === 'email' && !d.email) { fieldError($('contact-email'), T('You chose email: please add your email address', '您选择了电邮，请填写电邮地址')); ok = false; }
            }
            if (!d.message) { fieldError($('contact-message'), T('Please tell us briefly what you need', '请简单说明您的需要')); ok = false; }
            if (!ok) { status(msgEl, T('Please correct the highlighted fields.', '请更正标示的栏位。'), 'error', true); const f = form.querySelector('.error'); if (f) f.focus(); msgEl.scrollIntoView({ block: 'nearest' }); return; }

            const header = [d.location && T('Location: ', '地点：') + d.location, d.urgency && T('Urgency: ', '紧急程度：') + d.urgency, T('Reply by: ', '回复方式：') + replyText].concat(inhouse, speak).filter(Boolean).join(' | ');
            const lines = [
                T('Quote request from the B & K website', 'B & K 网站报价请求'),
                T('Name: ', '姓名：') + d.name,
                d.phone && T('Phone / WhatsApp: ', '电话／WhatsApp：') + d.phone,
                d.email && T('Email: ', '电邮：') + d.email,
                d.company && T('Company: ', '公司：') + d.company,
                d.topicText && T('Topic: ', '主题：') + d.topicText,
                header, '', d.message
            ];
            if (!client) { fallback(msgEl, lines, 'Quote request: ' + d.name, d.reply); return; }
            const original = btn.textContent; btn.disabled = true; btn.textContent = T('Sending…', '发送中…');
            try {
                const { error } = await client.from('contact_submissions').insert([{
                    name: d.name, email: d.email || '', phone: d.phone || '', company: d.company || null,
                    industry: d.topic || null, message: header ? '[' + header + '] ' + d.message : d.message, type: 'quote'
                }]);
                if (error) throw error;
                status(msgEl, T(`Thank you, ${d.name}. Your request has reached us. We reply the same business day.`, `谢谢您，${d.name}。我们已收到您的请求，会在同一个工作日内回复。`), 'success', true);
                msgEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
                form.reset(); toggleInhouse();
                if (typeof gtag === 'function') gtag('event', 'quote_request', { topic: d.topic });
            } catch (err) {
                fallback(msgEl, lines, 'Quote request: ' + d.name, d.reply);
            } finally { btn.disabled = false; btn.textContent = original; }
        });
        const sel = $('contact-industry');
        function toggleInhouse() {
            const box = document.getElementById('inhouse-fields');
            if (box) box.hidden = !(sel && sel.value === 'inhouse');
            const sp = document.getElementById('speak-fields');
            if (sp) sp.hidden = !(sel && sel.value === 'speaking');
        }
        if (sel) { sel.addEventListener('change', toggleInhouse); toggleInhouse(); }
    }

    /* ---------- newsletter ---------- */
    function subscribeByMail(el, email) {
        status(el, T('Subscriptions are offline right now. Tap below to send us a one-line email and we will add you.', '订阅功能暂时无法使用。请点击下方按钮发一封简短电邮，我们会为您加入。'), 'error', true);
        const a = document.createElement('a'); a.className = 'btn btn-primary btn-sm'; a.style.marginTop = '.6rem';
        a.href = 'mailto:' + MAIL + '?subject=' + encodeURIComponent('Subscribe: B & K tax updates') + '&body=' + encodeURIComponent('Please add ' + email + ' to the B & K tax update list. I consent to receiving these emails.');
        a.textContent = T('Email us to subscribe', '电邮订阅');
        el.appendChild(document.createElement('br')); el.appendChild(a);
    }
    function initNewsletter() {
        document.querySelectorAll('.newsletter-form').forEach(form => {
            form.addEventListener('submit', async e => {
                e.preventDefault();
                const input = form.querySelector('input[type="email"]');
                const consent = form.querySelector('input[type="checkbox"]');
                let msgEl = form.querySelector('.form-message');
                if (!msgEl) { msgEl = document.createElement('div'); msgEl.className = 'form-message'; form.appendChild(msgEl); }
                const email = (input && input.value.trim()) || '';
                if (!validEmail(email)) { status(msgEl, T('Please enter a valid email address.', '请输入有效的电邮地址。'), 'error', true); input && input.focus(); return; }
                if (consent && !consent.checked) { status(msgEl, T('Please tick the consent box to subscribe.', '请勾选同意栏以订阅。'), 'error', true); consent.focus(); return; }
                if (!client) { subscribeByMail(msgEl, email); return; }
                try {
                    const { error } = await client.from('newsletter_subscribers').insert([{ email, consent: true }]);
                    if (error && error.code !== '23505') throw error;
                    status(msgEl, error ? T('You are already subscribed. Thank you!', '您已订阅，谢谢！') : T('Thank you for subscribing.', '感谢您的订阅。'), 'success');
                    form.reset();
                } catch (err) {
                    subscribeByMail(msgEl, email);
                }
            });
        });
    }

    function boot() { initContact(); initNewsletter(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
