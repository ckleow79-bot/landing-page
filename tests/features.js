// Feature checks for the BM / fees / forms / programmes round. Needs the site on :5700 (npm start). Usage: node tests/features.js tests/out
const { chromium } = require('playwright');
const B = 'http://localhost:5700/';
const englishLeft = () => {
  const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT); const r = []; let n;
  const en = /\b(the|and|your|with|from|we|you)\b/i;
  while ((n = w.nextNode())) { const t = n.nodeValue.trim(); if (t.length > 25 && en.test(t) && !n.parentElement.closest('[data-i18n-skip],script,style,svg')) r.push(t.slice(0, 70)); }
  return r;
};
(async () => {
  const b = await chromium.launch(); const out = process.argv[2] || 'tests/out'; require('fs').mkdirSync(out, { recursive: true });
  const ok = (n, c, x = '') => console.log((c ? 'PASS ' : 'FAIL ') + n + (x ? '  ' + x : ''));
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } }); const p = await ctx.newPage();
  // Malay
  await p.goto(B + 'advisory.html?lang=ms', { waitUntil: 'load' }); await p.waitForTimeout(2000);
  ok('ms: html lang', await p.evaluate(() => document.documentElement.lang) === 'ms');
  ok('ms: switch shows BM pressed', await p.$eval('.lang-switch [data-lang-set="ms"]', e => e.getAttribute('aria-pressed') === 'true'));
  await p.screenshot({ path: out + '/ms-advisory.png' });
  await p.evaluate(() => document.getElementById('fees').scrollIntoView()); await p.waitForTimeout(800); await p.screenshot({ path: out + '/ms-fees.png' });
  await p.click('.lang-switch [data-lang-set="en"]'); await p.waitForLoadState('load'); await p.waitForTimeout(800);
  ok('switch back to English', await p.evaluate(() => document.documentElement.lang) === 'en' && !/lang=/.test(p.url()), p.url());
  for (const lang of ['ms', 'zh']) for (const pg of ['index', 'advisory', 'academy', 'programmes', 'about', 'faq', 'contact', 'insights', 'tools']) {
    await p.goto(B + pg + '.html?lang=' + lang, { waitUntil: 'load' }); await p.waitForTimeout(1500);
    const e2 = await p.evaluate(englishLeft);
    ok(lang + ': ' + pg + ' translated', e2.length < 4, e2.length + ' ' + JSON.stringify(e2.slice(0, 4)));
  }
  await p.goto(B + 'index.html?lang=en', { waitUntil: 'load' });
  // contact: email-only path
  await p.goto(B + 'contact.html', { waitUntil: 'load' }); await p.waitForTimeout(1200);
  await p.fill('#contact-name', 'Sarah'); await p.fill('#contact-message', 'SST question');
  await p.check('input[name=reply][value=email]', { force: true }); await p.click('.contact-form button[type=submit]'); await p.waitForTimeout(300);
  ok('email reply needs email', !!(await p.$('#contact-email.error')));
  await p.fill('#contact-email', 'sarah@example.com'); await p.check('.contact-form .prog-check input', { force: true });
  await p.click('.contact-form button[type=submit]'); await p.waitForTimeout(1200);
  const first = await p.$eval('#contact-message-status .form-fallback a', a => a.href).catch(() => '');
  ok('email-first visitor: fallback leads with email', /^mailto:/.test(first), first.slice(0, 50));
  const vis = await p.$eval('#contact-message-status', e => { const r = e.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; });
  ok('form message in view', vis);
  await p.goto(B + 'contact.html?topic=speaking', { waitUntil: 'load' }); await p.waitForTimeout(800);
  ok('speaking fields shown', await p.$eval('#speak-fields', e => !e.hidden));
  ok('urgency has 30 days', !!(await p.$('#contact-urgency option[value=month]')));
  // programmes
  await p.goto(B + 'programmes.html?when=past', { waitUntil: 'load' }); await p.waitForTimeout(2500);
  ok('past cards: no register/closed/calendar', (await p.$$('.prog-card[data-status=past] [data-register], .prog-card[data-status=past] [data-ics]')).length === 0);
  ok('no "Online · Online"', !(await p.evaluate(() => /Online · Online/.test(document.body.innerText))));
  await p.goto(B + 'programmes.html', { waitUntil: 'load' }); await p.waitForSelector('.prog-card[data-provider="high-impact"] .prog-facts', { timeout: 15000 });
  ok('CPD line on HI cards', /7 CPD hours per full day/.test((await p.$$eval('.prog-card[data-provider="high-impact"]', l => l.map(e => e.innerText).join(' ')))));
  ok('no ping dot on Programmes', await p.evaluate(() => getComputedStyle(document.querySelector('.nav-link-highlight'), '::after').content) === 'none');
  await p.goto(B + 'academy.html', { waitUntil: 'load' }); await p.waitForTimeout(2500);
  const days = await p.$$eval('#upcoming .prog-card', l => l.map(c => c.dataset.slug));
  const cnt = await p.$eval('[data-count-src=upcoming]', e => e.textContent);
  ok('academy upcoming count matches list', String(days.length) === cnt.trim(), days.length + ' vs ' + cnt);
  await p.goto(B + 'index.html', { waitUntil: 'load' }); await p.waitForTimeout(800);
  ok('home book label renamed', await p.evaluate(() => [...document.querySelectorAll('.bl-name')].every(e => e.textContent === 'B&K Group')));
  await p.goto(B + 'faq.html#firms', { waitUntil: 'load' }); await p.waitForTimeout(1200);
  ok('faq #firms opens', await p.$eval('#firms', e => e.open));
  await p.goto(B + 'insights.html', { waitUntil: 'load' }); await p.waitForTimeout(1000);
  ok('insights empty state + rss', !!(await p.$('.ins-empty')) && !!(await p.$('link[type="application/rss+xml"]')));
  // phone
  const m = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
  await m.goto(B + 'advisory.html', { waitUntil: 'load' }); await m.waitForTimeout(2000);
  await m.tap('.action-bar [data-open-chat]'); await m.waitForTimeout(600);
  ok('phone: Ask opens assistant', await m.$eval('.chatbot-window', e => e.classList.contains('active')));
  await m.screenshot({ path: out + '/m-chat.png' });
  await m.tap('.chatbot-window .quick-reply-btn >> nth=0'); await m.waitForTimeout(500);
  const labels = await m.$$eval('.chatbot-window .quick-replies', l => [...l[l.length - 1].querySelectorAll('.quick-reply-btn')].map(x => x.textContent));
  ok('assistant keeps Talk to a person + Something else', labels.includes('Talk to a person') && labels.includes('Something else'), JSON.stringify(labels));
  await m.goto(B + 'index.html', { waitUntil: 'load' }); await m.waitForTimeout(1500);
  await m.screenshot({ path: out + '/m-home.png' });
  await m.tap('.mobile-menu-toggle'); await m.waitForTimeout(500);
  ok('phone menu has Contact', await m.$eval('.nav-link-m', e => getComputedStyle(e).display !== 'none'));
  await m.screenshot({ path: out + '/m-menu.png' });
  await b.close();
})();
