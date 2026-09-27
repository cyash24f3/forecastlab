/* Run against a disposable ForecastLab server: npm run test:ui
   BASE_URL defaults to http://127.0.0.1:8001. Imports test datasets. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async () => {
 const browser = await chromium.launch({headless:true});
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors = [];
 page.on('pageerror',error=>errors.push(error.message));
 const base = process.env.BASE_URL || 'http://127.0.0.1:8001';
 const out = process.env.QA_DIR || 'data/qa';
 fs.mkdirSync(out,{recursive:true});
 try {
  await page.goto(base);
  await page.waitForSelector('#demo-button:visible');
  await page.click('#demo-button');
  await page.waitForFunction(()=>!document.getElementById('train-button').disabled);
  await page.click('#train-button');
  await page.waitForSelector('#overview-kpis .kpi',{timeout:60000});
  assert.equal(await page.locator('#overview-kpis .kpi').count(),4);
  assert.match(await page.locator('#source-label').innerText(),/SYNTHETIC DEMO/);
  await page.screenshot({path:path.join(out,'overview.png'),fullPage:true});
  await page.selectOption('#series-select','Support requests');
  await page.waitForFunction(()=>document.getElementById('forecast-title').textContent.startsWith('Support requests'));
  await page.click('[data-page="models"]');
  await page.waitForSelector('#comparison-table tbody tr');
  assert.equal(await page.locator('#comparison-table tbody tr').count(),4);
  assert.equal(await page.locator('#fold-table tbody tr').count(),6);
  assert.equal(await page.locator('#comparison-table .model-badge').count(),1);
  await page.screenshot({path:path.join(out,'models.png'),fullPage:true});
  const downloadPromise=page.waitForEvent('download');
  await page.click('#download-holdout');
  const download=await downloadPromise;
  assert.match(download.suggestedFilename(),/holdout.csv$/);
  await page.click('[data-page="planner"]');
  await page.waitForSelector('#planner-kpis .kpi');
  await page.fill('#capacity','0');
  await page.click('#scenario-button');
  await page.waitForFunction(()=>document.getElementById('planner-kpis').innerText.includes('14 / 14'));
  await page.fill('#capacity','1000000');
  await page.click('#scenario-button');
  await page.waitForFunction(()=>document.getElementById('planner-kpis').innerText.includes('0 / 14'));
  await page.locator('.scenario-controls summary').click();
  await page.fill('#lead-days','28');
  await page.click('#scenario-button');
  await page.waitForSelector('#notice.error');
  assert.match(await page.locator('#notice').innerText(),/horizon/);
  await page.fill('#lead-days','3');
  await page.click('#scenario-button');
  await page.waitForFunction(()=>document.getElementById('notice').hidden);
  await page.screenshot({path:path.join(out,'planner.png'),fullPage:true});
  await page.click('[data-page="data"]');
  await page.setInputFiles('#csv-file',{name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from('wrong,columns\n1,2')});
  await page.click('#upload-button');
  await page.waitForSelector('#notice.error');
  assert.match(await page.locator('#notice').innerText(),/Required columns/);
  let csv='date,series_id,value\n';
  for(let i=0;i<180;i++) {const d=new Date(Date.UTC(2025,0,1+i));csv+=`${d.toISOString().slice(0,10)},Zero demand,0\n`;}
  await page.fill('#upload-name','Browser test · zero demand');
  await page.setInputFiles('#csv-file',{name:'zero.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
  await page.click('#upload-button');
  await page.waitForFunction(()=>document.getElementById('dataset-title').textContent==='Browser test · zero demand');
  await page.selectOption('#horizon-select','7');
  await page.click('#train-button');
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Forecast complete'),{timeout:60000});
  await page.click('[data-page="overview"]');
  await page.waitForFunction(()=>document.getElementById('forecast-title').textContent.includes('Zero demand'));
  assert.match(await page.locator('#overview-kpis').innerText(),/N\/A/);
  await page.click('[data-page="models"]');
  assert.match(await page.locator('#comparison-table').innerText(),/N\/A/);
  await page.click('[data-page="method"]');
  assert.match(await page.locator('#page-method').innerText(),/Intervals are estimates/);
  await page.setViewportSize({width:390,height:844});
  for (const tab of ['overview','models','planner','data','method']) {
   await page.click(`[data-page="${tab}"]`);
   await page.waitForTimeout(150);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth + 1),`${tab} must not overflow mobile viewport`);
   await page.screenshot({path:path.join(out,`mobile-${tab}.png`),fullPage:true});
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: demo → training → series filters → model evidence → downloads → capacity/inventory → invalid CSV → zero-demand import → retraining → mobile pages. No JavaScript errors.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
