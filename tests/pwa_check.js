// PWA の確認: manifest・アイコン・service worker の登録、オフラインで前回の画面を開けること。実行: BASE=http://localhost:8765 node tests/pwa_check.js
const {chromium}=require('playwright');
const BASE=(process.env.BASE||'http://localhost:8765').replace(/\/$/,'');
(async()=>{
  const b=await chromium.launch();const ctx=await b.newContext({viewport:{width:393,height:780}});const p=await ctx.newPage();const errs=[];
  p.on('pageerror',e=>errs.push(e.message));
  await p.goto(BASE+'/index.html');await p.waitForTimeout(1500);
  const man=await p.evaluate(async()=>{const l=document.querySelector('link[rel=manifest]');const r=await fetch(l.href);return r.ok?await r.json():null});
  const icons=await Promise.all(man.icons.map(i=>p.evaluate(async u=>(await fetch(u)).status,BASE+'/'+i.src)));
  const reg=await p.evaluate(async()=>{const r=await navigator.serviceWorker.ready;return !!r.active});
  await p.reload();await p.waitForTimeout(800);
  const ctl=await p.evaluate(()=>!!navigator.serviceWorker.controller);
  await ctx.setOffline(true);
  await p.reload();await p.waitForTimeout(1200);
  const offline=await p.evaluate(()=>({title:document.title,cards:document.querySelectorAll('.card').length,err:!!document.getElementById('loadErr')&&!document.getElementById('loadErr').hidden}));
  console.log(JSON.stringify({name:man.name,display:man.display,icons,reg,ctl,offline,errs}));
  await b.close();
  const ok=man.display==='standalone'&&icons.every(s=>s===200)&&reg&&ctl&&offline.title.includes('ラッフレア')&&!offline.err&&errs.length===0;
  process.exit(ok?0:1);
})();
