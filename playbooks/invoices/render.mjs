// HTML invoices to PDF (with a text layer, like a real emailed PDF) and PNG (for scans and photos).
// From the top folder: npm install && npx playwright install chromium. Then here: node render.mjs
// (set CHROME_EXE to a Chromium binary to use one you already have)
import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';
import { chromium } from 'playwright';
const dir = new URL('./cases/', import.meta.url).pathname;
const browser = await chromium.launch({ executablePath: process.env.CHROME_EXE || undefined });
const page = await browser.newPage({ viewport: { width: 794, height: 1123 } });
let n = 0;
for (const f of readdirSync(dir).filter(f => f.endsWith('.html')).sort()) {
  const id = f.replace('.html', '');
  const truth = JSON.parse(readFileSync(join(dir, id + '.truth.json'), 'utf8'));
  await page.goto('file://' + join(dir, f));
  if (truth.format === 'pdf') await page.pdf({ path: join(dir, id + '.pdf'), format: 'A4', printBackground: true });
  else await page.screenshot({ path: join(dir, id + '.clean.png'), fullPage: true });
  n++;
}
console.log('rendered', n);
await browser.close();
