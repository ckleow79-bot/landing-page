/**
 * B & K guided assistant.
 * Tap-only: visitors choose topics, the assistant answers with short, factual
 * pointers and links (quote form, WhatsApp, self-checks, programmes).
 * Nothing is typed, sent or stored, and all text is set with textContent.
 */
(function () {
    'use strict';
    const zh = () => !!(window.BKi18n && window.BKi18n.lang === 'zh');
    const T = (en, cn) => (zh() && cn ? cn : en);
    const WA = 'https://wa.me/601130636198';
    const wa = msg => WA + '?text=' + encodeURIComponent(msg);

    const FLOWS = {
        home: () => ({
            say: [T("Hi, I'm the B & K assistant. What do you need help with?", '您好，我是 B & K 助理。请问需要哪方面的协助？')],
            options: [
                ['audit', T('LHDN letter or tax audit', 'LHDN 来信或税务审计')],
                ['einvoice', T('e-Invoice', '电子发票')],
                ['tax', T('Tax compliance and planning', '税务申报与规划')],
                ['cfo', T('Fractional CFO or board reports', '外包CFO或董事会报告')],
                ['training', T('Seminars and training', '讲座与培训')],
                ['human', T('Talk to a person', '找真人联系')]
            ]
        }),
        audit: () => ({
            say: [T('If the letter has a reply deadline, contact us now. Send the letter date and reference only, not the letter itself; we will set up a secure way to receive documents.', '如果来信有回复期限，请尽快联系我们。请只发来信日期和参考编号，不要发送信件本身；我们会安排安全的方式接收文件。'),
                  T('We reply the same business day.', '我们会在同一个工作日内回复。')],
            links: [
                ['advisory.html#letter-decoder', T('Decode your letter', '解读您的来信')],
                [wa(T('Hi B & K, I received an LHDN letter dated ... (ref ...).', '您好 B&K，我收到 LHDN 来信，日期 …，参考编号 …。')), T('WhatsApp us', 'WhatsApp 我们'), true],
                ['contact.html?topic=audit#quote', T('Request a quote', '索取报价')],
                ['advisory.html#audit-check', T('1-minute audit check', '1分钟审计自我检测')]
            ]
        }),
        einvoice: () => ({
            say: [T('Most of our e-Invoice work is checking that MyInvois matches the accounts: consolidated, self-billed and credit-note cases. Start with the one-minute check.', '我们大部分电子发票工作，是核对 MyInvois 与账目是否一致，包括综合、自开及贷项通知单。不妨先做1分钟自我检测。')],
            links: [
                ['advisory.html#einvoice-check', T('1-minute e-Invoice check', '1分钟电子发票检测')],
                ['contact.html?topic=sst#quote', T('Request an e-Invoice review', '索取电子发票审阅报价')],
                ['programmes.html?category=e-Invoice', T('e-Invoice seminars', '电子发票讲座')]
            ]
        }),
        tax: () => ({
            say: [T('We handle corporate and individual tax compliance, CP204 estimates, withholding tax and planning, including investment holding companies. Every engagement is quoted after a short scoping conversation.', '我们处理公司与个人税务申报、CP204 预估税、预扣税及税务规划（包括投资控股公司）。每项委托都会在简短了解后报价。')],
            links: [
                ['contact.html?topic=compliance#quote', T('Request a quote', '索取报价')],
                ['advisory.html#services', T('See all services', '查看所有服务')]
            ]
        }),
        cfo: () => ({
            say: [T('As fractional CFO we review your management accounts each cycle and deliver two reports: a detailed one for the finance team and a short, decision-focused one for the board.', '作为外包CFO，我们每期审阅管理账目，并提交两份报告：给财务团队的详细报告，以及给董事会的精简决策摘要。')],
            links: [
                ['contact.html?topic=cfo#quote', T('Request a quote', '索取报价')],
                ['advisory.html#cfo', T('How it works', '服务内容')]
            ]
        }),
        training: () => ({
            say: [T('Upcoming public sessions are below. Programmes marked HRD Corp claimable on the list can be claimed; for any other programme, ask us before you register.', '以下是即将举行的公开课。课程列表上注明可申请 HRD Corp 的课程才可申索；其他课程请在报名前先询问我们。')],
            live: true,
            links: [
                ['programmes.html', T('All programmes', '所有课程')],
                ['contact.html?topic=inhouse#quote', T('In-house training quote', '企业内训报价')]
            ]
        }),
        human: () => ({
            say: [T('Monday to Friday, 9:00 to 18:00. We reply the same business day.', '星期一至五，上午9时至下午6时。我们会在同一个工作日内回复。')],
            links: [
                ['tel:+601130636198', T('Call +60 11-3063 6198', '致电 +60 11-3063 6198')],
                [wa(T('Hi B & K, I would like to ask about ...', '您好 B&K，我想询问 …')), T('WhatsApp', 'WhatsApp'), true],
                ['mailto:keith@bkcorporate.com', T('Email us', '电邮联系')]
            ]
        })
    };

    let box, opened = false;

    function el(tag, cls, text) {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text != null) e.textContent = text;
        return e;
    }
    function scroll() { box.scrollTop = box.scrollHeight; }

    function bot(text) {
        const m = el('div', 'chat-message bot-message');
        const av = el('div', 'message-avatar');
        const img = el('img'); img.src = 'assets/brand/mark-white.svg'; img.alt = ''; img.width = 18; img.height = 18;
        av.appendChild(img);
        const c = el('div', 'message-content');
        c.appendChild(el('p', null, text));
        m.append(av, c);
        box.appendChild(m);
    }
    function me(text) {
        const m = el('div', 'chat-message user-message');
        const c = el('div', 'message-content');
        c.appendChild(el('p', null, text));
        m.appendChild(c);
        box.appendChild(m);
    }
    function replies(items) {
        const wrap = el('div', 'quick-replies');
        items.forEach(it => wrap.appendChild(it));
        box.appendChild(wrap);
    }
    function optionBtn(key, label) {
        const b = el('button', 'quick-reply-btn', label);
        b.type = 'button';
        b.addEventListener('click', () => {
            const wrap = b.closest('.quick-replies'); if (wrap) wrap.remove();
            me(label);
            show(key);
        });
        return b;
    }
    function linkBtn(href, label, external) {
        const a = el('a', 'quick-reply-btn is-link', label);
        a.href = href;
        if (external) { a.target = '_blank'; a.rel = 'noopener'; }
        a.addEventListener('click', () => { if (typeof gtag === 'function') gtag('event', 'assistant_link', { link: href.split('?')[0] }); });
        return a;
    }

    function show(key) {
        const f = (FLOWS[key] || FLOWS.home)();
        f.say.forEach(bot);
        const items = [];
        if (f.options) f.options.forEach(([k, l]) => items.push(optionBtn(k, l)));
        if (f.links) f.links.forEach(([h, l, ext]) => items.push(linkBtn(h, l, ext)));
        if (key !== 'home') items.push(optionBtn('home', T('Something else', '其他问题')));
        if (f.live && window.BKProgrammes) {
            const holder = el('div', 'quick-replies');
            box.appendChild(holder);
            const fmt = new Intl.DateTimeFormat(zh() ? 'zh-CN' : 'en-MY', { day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' });
            window.BKProgrammes.load().then(d => {
                d.list.filter(p => p.status === 'upcoming').slice(0, 3).forEach(p => {
                    const a = linkBtn('programmes.html?open=' + encodeURIComponent(p.slug), fmt.format(new Date(p.start_date)) + ' · ' + p.title);
                    a.setAttribute('data-i18n-skip', '');
                    holder.appendChild(a);
                });
                scroll();
            }).catch(() => holder.remove());
        }
        replies(items);
        scroll();
    }

    function setOpen(state) {
        const win = document.querySelector('.chatbot-window');
        const tog = document.querySelector('.chatbot-toggle');
        opened = state;
        win.classList.toggle('active', state);
        tog.classList.toggle('hidden', state);
        tog.setAttribute('aria-expanded', state ? 'true' : 'false');
        if (state) {
            if (!box.childElementCount) show('home');
            setTimeout(() => { const f = win.querySelector('.quick-reply-btn'); if (f) f.focus(); }, 250);
        } else tog.focus();
    }

    window.initChatbot = function () {
        const tog = document.querySelector('.chatbot-toggle');
        const close = document.querySelector('.chatbot-close');
        box = document.querySelector('.chatbot-messages');
        if (!tog || !box) return;
        tog.addEventListener('click', () => setOpen(!opened));
        if (close) close.addEventListener('click', () => setOpen(false));
        document.addEventListener('keydown', e => { if (e.key === 'Escape' && opened) setOpen(false); });
    };
})();
