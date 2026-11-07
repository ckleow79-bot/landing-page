// Regression sweep: errors and overflow on every page at 3 widths, anchors, forms, programmes, Chinese, reduced motion. Needs the site on :5700 (npm start). Usage: node tests/regression.js tests/out
const { chromium } = require('playwright');
const B = 'http://localhost:5700/';
(async () => {
  const out = process.argv[2] || 'tests/out'; require('fs').mkdirSync(out, { recursive: true }); const b = await chromium.launch();
  const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
  // 1. sweep: errors + overflow + hidden-focusable count
  for (const vp of [{ w: 1440, h: 900, t: 'd' }, { w: 1024, h: 768, t: 't' }, { w: 390, h: 844, t: 'm', mobile: true }]) {
    const ctx = await b.newContext({ viewport: { width: vp.w, height: vp.h }, isMobile: !!vp.mobile, hasTouch: !!vp.mobile });
    for (const pg of ['index', 'advisory', 'academy', 'programmes', 'insights', 'about', 'faq', 'tools', 'contact', 'privacy-policy', 'cookie-policy', 'terms-of-service', '404']) {
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && !/ERR_TUNNEL|net::|Failed to load resource/.test(m.text()) && errs.push(m.text()));
      await p.goto(B + pg + '.html', { waitUntil: 'load' }); await p.waitForTimeout(1200);
      await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 800) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); } });
      const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (errs.length || ov > 0) console.log('FAIL sweep', vp.t, pg, 'overflow', ov, JSON.stringify(errs).slice(0, 300));
      await p.close();
    }
    await ctx.close();
  }
  console.log('sweep done');
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await ctx.newPage();
  // 2. academy hero buttons visible
  await p.goto(B + 'academy.html', { waitUntil: 'load' }); await p.waitForTimeout(2000);
  const op = await p.$$eval('.page-hero-cine .hero-ctas .btn, .page-hero-cine .btn', l => l.map(x => getComputedStyle(x).opacity));
  ok('academy hero buttons visible', op.length && op.every(o => o === '1'), JSON.stringify(op));
  ok('academy HRD CC panel', !!(await p.$('#in-house')));
  ok('clients bar present', (await p.$$eval('.cb-clients .cb-list li:not([aria-hidden])', l => l.length)) > 20);
  // 3. anchor landing from another page
  await p.goto(B + 'index.html', { waitUntil: 'load' }); await p.waitForTimeout(1200);
  await p.goto(B + 'advisory.html#einvoice-check', { waitUntil: 'load' }); await p.waitForTimeout(2500);
  const pos = await p.evaluate(() => Math.round(document.querySelector('#einvoice-check').getBoundingClientRect().top));
  ok('lands on #einvoice-check', pos > -50 && pos < 400, 'top=' + pos);
  await p.goto(B + 'advisory.html#letter-decoder', { waitUntil: 'load' }); await p.waitForTimeout(2500);
  const pos2 = await p.evaluate(() => Math.round(document.querySelector('#letter-decoder').getBoundingClientRect().top));
  ok('lands on #letter-decoder', pos2 > -50 && pos2 < 400, 'top=' + pos2);
  // 4. hidden focusables
  const hid = await p.evaluate(() => [...document.querySelectorAll('.chatbot-window button, .ph-screen:not(.is-on) a')].filter(e => getComputedStyle(e).visibility !== 'hidden').length);
  ok('closed chat has no visible focusables', hid === 0, String(hid));
  // 5. contact form: required WhatsApp, inhouse fields, fallback text
  await p.goto(B + 'contact.html?topic=inhouse', { waitUntil: 'load' }); await p.waitForTimeout(1500);
  ok('in-house fields shown for topic=inhouse', await p.$eval('#inhouse-fields', e => !e.hidden));
  await p.fill('#contact-name', 'Test'); await p.fill('#contact-message', 'Need training'); await p.click('.contact-form button[type=submit]'); await p.waitForTimeout(400);
  ok('phone required error', !!(await p.$('#contact-phone.error')));
  await p.fill('#contact-phone', '+60 12-345 6789'); await p.fill('#ih-pax', '25'); await p.selectOption('#ih-lang', 'bm');
  await p.check('.contact-form input[type=checkbox]').catch(() => {});
  await p.click('.contact-form button[type=submit]'); await p.waitForTimeout(800);
  const wa = await p.$eval('#contact-message-status a[href^="https://wa.me"]', a => decodeURIComponent(a.href)).catch(() => '');
  ok('fallback WhatsApp has readable topic + in-house details', /In-house training/.test(wa) && /Participants: 25/.test(wa) && /Bahasa Malaysia/.test(wa), wa.slice(0, 160).replace(/\n/g, ' | '));
  ok('URL has no personal data', !/name=|email=|message=/.test(p.url()), p.url());
  // 6. programmes: past list, card includes, modal
  await p.goto(B + 'programmes.html?when=past', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  const past = await p.$$eval('.prog-card', l => l.length);
  const firstPast = await p.$eval('.prog-card .prog-day', e => e.textContent).catch(() => '');
  ok('past programmes listed', past > 100, past + ' cards, first day ' + firstPast);
  await p.goto(B + 'programmes.html', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  ok('card shows fee includes + HRD provider', !!(await p.$('.prog-includes')) && !!(await p.$('.prog-tp')));
  ok('card shows end time', /–\s*5:00/.test(await p.$eval('.prog-facts li', e => e.textContent)), await p.$eval('.prog-facts li', e => e.textContent));
  await p.click('.prog-card[data-provider="high-impact"] [data-register]'); await p.waitForTimeout(500);
  ok('modal recap shows fee + provider', /High Impact Training Services PLT/.test(await p.$eval('.prog-modal-recap', e => e.textContent)));
  ok('modal has other attendees', !!(await p.$('.prog-form textarea[name=attendees]')));
  for (let i = 0; i < 25; i++) await p.keyboard.press('Tab');
  ok('focus trapped in modal', await p.evaluate(() => !!document.activeElement.closest('#prog-modal')));
  await p.keyboard.press('Escape'); await p.waitForTimeout(300);
  ok('focus restored to Register button', await p.evaluate(() => !!document.activeElement.closest('[data-register]')));
  // 7. Chinese: decoder WhatsApp text
  await p.goto(B + 'advisory.html?lang=zh', { waitUntil: 'load' }); await p.waitForTimeout(1500);
  const zwa = await p.$eval('.ld-panel:not([hidden]) a[href^="https://wa.me"]', a => decodeURIComponent(a.href));
  ok('decoder WhatsApp in Chinese', /您好/.test(zwa), zwa.slice(-60));
  await p.goto(B + 'index.html?lang=en', { waitUntil: 'load' }); await p.waitForTimeout(800);
  // 8. Google Fonts not on English pages
  const gf = []; const p2 = await ctx.newPage(); p2.on('request', r => { if (/fonts\.googleapis/.test(r.url())) gf.push(r.url()); });
  await p2.goto(B + 'about.html?lang=en', { waitUntil: 'load' }); await p2.waitForTimeout(1200);
  ok('no Google Fonts request in English', gf.length === 0, String(gf.length));
  // 9. reduced motion: clients bar static, academy buttons
  const r = await (await b.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' })).newPage();
  await r.goto(B + 'index.html', { waitUntil: 'load' }); await r.waitForTimeout(1200);
  ok('reduced motion: clients bar not animated', await r.$eval('.cb-list', e => getComputedStyle(e).animationName === 'none'));
  ok('home hero buttons visible (reduced)', (await r.$$eval('.hero-ctas .btn', l => l.map(x => getComputedStyle(x).opacity))).every(o => o === '1'));
  await r.evaluate(() => document.querySelector('.clients-bar').scrollIntoView()); await r.waitForTimeout(400);
  await r.screenshot({ path: out + '/r2-clients-reduced.png' });
  const m = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
  await m.goto(B + 'index.html', { waitUntil: 'load' }); await m.waitForTimeout(3500);
  await m.screenshot({ path: out + '/r2-home-m.png' });
  await m.evaluate(() => document.querySelector('.clients-bar').scrollIntoView()); await m.waitForTimeout(600);
  await m.screenshot({ path: out + '/r2-clients-m.png' });
  ok('mobile header language button visible', await m.$eval('.lang-switch-m', e => getComputedStyle(e).display !== 'none'));
  await m.goto(B + 'academy.html', { waitUntil: 'load' }); await m.waitForTimeout(2000);
  await m.evaluate(() => document.querySelector('#in-house').scrollIntoView()); await m.waitForTimeout(500);
  await m.screenshot({ path: out + '/r2-hrdcc-m.png' });
  await b.close();
})();
