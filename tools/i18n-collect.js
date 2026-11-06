// Lists every translatable string on the main pages (run `npm start` first).
// Usage: node tools/i18n-collect.js out.json  -> {text:{english:page}, html:{english_html:page}}
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const pages = ["index", "advisory", "academy", "programmes", "insights", "about", "contact", "faq", "tools", "terms-of-service", "cookie-policy"];
  const b = await chromium.launch();
  const all = { text: {}, html: {} };
  for (const pg of pages) {
    const p = await (await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })).newPage(); // no word-splitting while collecting
    await p.goto(`http://localhost:5700/${pg}.html?i18n=collect`, { waitUntil: 'load' });
    await p.waitForTimeout(2500);
    const k = await p.evaluate(() => window.__i18nKeys());
    k.text.forEach(t => (all.text[t] = all.text[t] || pg));
    k.html.forEach(t => (all.html[t] = all.html[t] || pg));
    await p.close();
  }
  // strings set from JS after interaction
  const src = fs.readFileSync('js/audit-story.js', 'utf8');
  const re = /(title|body): '((?:[^'\\]|\\.)*)'/g; let m;
  while ((m = re.exec(src))) all.text[m[2].replace(/\\'/g, "'")] = 'advisory-js';
  // tap-only assistant, form messages, ribbon and programme modal: English side of T('en', 'zh')
  for (const f of ['js/chatbot.js', 'js/supabase.js', 'js/programmes.js']) {
    const t = fs.readFileSync(f, 'utf8');
    const r2 = /\b[TL]\(\s*(['"])((?:\\.|(?!\1).)*)\1\s*,/g; let n;
    while ((n = r2.exec(t))) { const v = n[2].replace(/\\'/g, "'").replace(/\\"/g, '"'); if (/[A-Za-z]{3}/.test(v) && !/\$\{/.test(v)) all.text[v.replace(/\s+/g, ' ').trim()] = f; }
  }
  fs.writeFileSync(process.argv[2], JSON.stringify(all, null, 1));
  console.log('text', Object.keys(all.text).length, 'html', Object.keys(all.html).length);
  await b.close();
})();
