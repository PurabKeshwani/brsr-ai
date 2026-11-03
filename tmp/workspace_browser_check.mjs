import {Browser} from 'file:///C:/Users/amitk/.codex/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {mkdirSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const out='.taste-skill/workspace-qa';mkdirSync(out,{recursive:true});
const browser=await Browser.launch();const page=await browser.newPage({width:1440,height:1000});
const checks=[];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,label,timeout=35000){const start=Date.now();while(Date.now()-start<timeout){if(await page.eval(fn))return;await sleep(200)}throw new Error('Timed out: '+label)}
async function visit(route,text){await page.goto('http://127.0.0.1:3000'+route,{settleMs:600});await waitFor(`document.body.innerText.includes(${JSON.stringify(text)})`,text);await waitFor(`!document.querySelector('[aria-busy="true"]')`,'loading finished');checks.push('Loaded '+route)}
async function clickText(text){await page.eval(t=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.includes(t));if(!b)throw new Error('Button missing '+t);b.click()},text);await sleep(350)}
async function selectOption(label,value){await page.eval(({label,value})=>{const l=[...document.querySelectorAll('label')].find(l=>l.textContent.includes(label));const s=l?.querySelector('select');if(!s)throw new Error('Select missing '+label);s.value=value;s.dispatchEvent(new Event('change',{bubbles:true}))},{label,value});await sleep(350)}
async function shot(name){await page.screenshot({path:`${out}/${name}.png`,format:'png'})}
try{
 await visit('/compare','94');
 assert(await page.eval(()=>document.body.innerText.includes('48.17')));assert(await page.eval(()=>document.body.innerText.includes('9.88')));checks.push('Financial sector totals match paper');
 await shot('compare-1440');
 await selectOption('Reporting basis','2025-03-31');assert(await page.eval(()=>document.querySelector('.metric-strip strong').textContent==='17'));checks.push('FY2024-25 subset = 17');
 await selectOption('Reporting basis','2026-03-31');assert(await page.eval(()=>document.querySelector('.metric-strip strong').textContent==='77'));checks.push('FY2025-26 subset = 77');
 await selectOption('Reporting basis','latest');
 await clickText('Selected peers');await clickText('Use sector sample');assert(await page.eval(()=>document.querySelectorAll('.selected-peers button:not(.text-action)').length===7));checks.push('Select seven-company paper sample');
 await clickText('Load evidence comparison');await waitFor(`document.body.innerText.includes('Evidence loaded')`,'peer evidence',60000);assert(await page.eval(()=>!document.body.innerText.includes('Unable to load evidence')));checks.push('Seven peer source evidence loaded');await shot('peer-evidence-1440');
 await clickText('All sectors');assert(await page.eval(()=>document.querySelector('.metric-strip strong').textContent.replaceAll(',','')==='1164'));assert(await page.eval(()=>document.querySelector('.sector-table tbody').children.length===47));checks.push('All 1,164 scores and 47 eligible sectors');
 await page.eval(()=>document.querySelector('.checkbox-label input').click());await sleep(250);assert(await page.eval(()=>document.querySelector('.sector-table tbody').children.length===72));checks.push('Small-sector filter reveals all 72 sectors');
 await visit('/company/Triveni%20Turbine%20Limited','Reconstruct the transparency score');assert(await page.eval(()=>document.body.innerText.includes('68.91')));assert(await page.eval(()=>document.body.innerText.includes('Snapshot / current-rule difference')));await shot('company-1440');
 await clickText('Metrics & history');assert(await page.eval(()=>document.body.innerText.includes('tCO2e')));assert(await page.eval(()=>document.body.innerText.includes('5,177.03')));checks.push('Triveni numeric series, unit and raw value');await shot('company-metrics-1440');
 await clickText('Evidence review');await page.eval(()=>document.querySelector('.evidence-item summary')?.click());assert(await page.eval(()=>document.querySelectorAll('mark').length>0));assert(await page.eval(()=>document.body.innerText.includes('Source fact #')));checks.push('Evidence expands source paragraph and highlighted sentence');await shot('company-evidence-1440');
 await clickText('Assurance & checks');assert(await page.eval(()=>document.body.innerText.includes('Reasonable assurance')));checks.push('Assurance and consistency details');
 await clickText('Source fact register');assert(await page.eval(()=>document.querySelectorAll('.fact-table tbody tr').length===30));await page.eval(()=>{const input=document.querySelector('.search-control input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(input,'TotalScope1Emissions');input.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(350);assert(await page.eval(()=>document.querySelectorAll('.fact-table tbody tr').length===2));checks.push('Fact search filters to exact Scope 1 records');
 await visit('/time-series','Paired report register');assert(await page.eval(()=>document.querySelector('.metric-strip strong').textContent==='8'));assert(await page.eval(()=>document.body.innerText.includes('+5.23')));assert(await page.eval(()=>document.querySelectorAll('.data-table tbody tr').length===16));await shot('time-series-1440');checks.push('Eight pairs, +5.23 mean change, sixteen reports');
 await selectOption('Company to investigate','L65990KL2016PLC045669');assert(await page.eval(()=>document.body.innerText.includes('+11.51')));checks.push('ESAF component attribution');
 await visit('/company/ESAF%20Small%20Finance%20Bank%20Ltd.?filing=1207','Reconstruct the transparency score');await waitFor(`document.body.innerText.includes('42.59')`,'historical score');checks.push('Historical report selector preserves report #1207 and score 42.59');
 await visit('/companies','1164 companies');await shot('explorer-1440');
 await visit('/upload','Drop a BRSR filing here');await shot('upload-1440');
 await visit('/methodology','Four levels of comparison');await shot('methodology-1440');
 await visit('/','Disclosure overview');await shot('overview-1440');
 await page.setViewport({width:1920,height:1080});await visit('/compare','Compare disclosures');await shot('compare-1920');
 assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth));assert(page.consoleErrors.length===0,JSON.stringify(page.consoleErrors));checks.push('Desktop layout has no horizontal overflow or browser exceptions');
 writeFileSync(`${out}/checks.json`,JSON.stringify({checks,consoleErrors:page.consoleErrors},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}finally{await browser.close()}

