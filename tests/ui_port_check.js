// 画面の確認(Playwright)。確認用データ(tests/fixtures)を、読み込みの代わりに差し込んで実行する。
// 使い方: リポジトリのルートで python3 -m http.server 8765 を起動し、node tests/ui_port_check.js (playwright が必要)
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const FIX=n=>fs.readFileSync(path.join(__dirname,'fixtures',n),'utf8');
const NOW=Date.parse('2026-11-02T13:40:00+09:00');
(async()=>{
  const b=await chromium.launch();const ctx=await b.newContext({viewport:{width:393,height:780},hasTouch:true,isMobile:true,serviceWorkers:'block'});
  const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));
  await p.clock.install({time:NOW});
  await p.route('**/data/lotteries.json',r=>r.fulfill({contentType:'application/json',body:FIX('lotteries.sample29.json')}));
  await p.route('**/data/products.json',r=>r.fulfill({contentType:'application/json',body:FIX('products.sample29.json')}));
  await p.route('**/data/affiliate.json',r=>r.fulfill({status:404,body:''}));
  await p.goto(process.env.BASE||'http://localhost:8765/index.html');
  await p.waitForFunction(()=>window.D&&document.querySelectorAll('.card').length>0,null,{timeout:8000}).catch(()=>{});
  await p.waitForFunction(()=>[...document.querySelectorAll('.card.sel img')].every(i=>i.complete),null,{timeout:5000}).catch(()=>{});
  const r=await p.evaluate(()=>({n:(window.D||[]).length,cards:document.querySelectorAll('.card').length,asof:document.getElementById('asof').textContent,sample:!document.getElementById('sampleNotice').hidden,
    first:window.D&&{p:D[0].p,pr:D[0].pr,lim:D[0].lim,rc:D[0].rc,st:D[0].st,ic:D[0].ic,img:D[0].img,rg:D[0]._rg,src:D[0].src},
    counter:(document.querySelector('.cnt')||{}).textContent,
    imgs:[...document.querySelectorAll('.card.sel img')].map(i=>[i.complete,i.naturalWidth,i.getAttribute('src')]),rgs:[...new Set(D.map(d=>d._rg))],
    states:D.reduce((a,d)=>(a[d.st]=(a[d.st]||0)+1,a),{})}));
  console.log(JSON.stringify(r,null,1));
  await p.screenshot({path:process.env.SHOT||'/tmp/port1.png'});
  console.log('errors',errs);await b.close();
})();
// ---- 追加の確認: 操作・空データ・読み込み失敗 ----
(async()=>{
  const b=await chromium.launch();
  const mk=async(routes)=>{const c=await b.newContext({viewport:{width:393,height:780},hasTouch:true,isMobile:true,serviceWorkers:'block'});const p=await c.newPage();const e=[];p.on('pageerror',x=>e.push(x.message));
    await p.clock.install({time:NOW});
    for(const [pat,fn] of routes)await p.route(pat,fn);await p.goto(process.env.BASE||'http://localhost:8765/index.html');return {p,e,c}};
  const fx=[['**/data/lotteries.json',r=>r.fulfill({contentType:'application/json',body:FIX('lotteries.sample29.json')})],['**/data/products.json',r=>r.fulfill({contentType:'application/json',body:FIX('products.sample29.json')})],['**/data/affiliate.json',r=>r.fulfill({status:404,body:''})]];
  let {p,e}=await mk(fx);await p.waitForFunction(()=>window.D&&document.querySelectorAll('.card').length>0).catch(()=>{});
  const out={};
  out.swipe=await p.evaluate(async()=>{const a0=a;go(a+1);await new Promise(r=>setTimeout(r,50));return[a0,a]});
  await p.click('#dots');out.jumpSheet=await p.evaluate(()=>!document.getElementById('jsheet').hidden);
  await p.click('#jsp button:last-child');out.last=await p.evaluate(()=>a+'/'+O.length);
  await p.click('[data-v="hist"]');out.hist=await p.evaluate(()=>!document.getElementById('vHist').hidden);
  await p.click('[data-v="list"]');
  out.noDemo=await p.evaluate(()=>!/デモ|サンプル/.test(document.body.innerText));
  out.noSampleLabel=await p.evaluate(()=>!document.querySelector('h1 small'));
  out.err1=e.slice();
  console.log('操作',JSON.stringify(out));
  ({p,e}=await mk([['**/data/lotteries.json',r=>r.fulfill({contentType:'application/json',body:'[]'})],['**/data/products.json',r=>r.fulfill({contentType:'application/json',body:'[]'})],['**/data/affiliate.json',r=>r.fulfill({status:404,body:''})]]));
  await p.waitForTimeout(600);console.log('空データ',await p.evaluate(()=>{const x=document.getElementById('loadErr');return[x.hidden,x.textContent]}),e);
  ({p,e}=await mk([['**/data/lotteries.json',r=>r.fulfill({status:500,body:'x'})],['**/data/products.json',r=>r.fulfill({status:500,body:'x'})],['**/data/affiliate.json',r=>r.fulfill({status:404,body:''})]]));
  await p.waitForTimeout(600);console.log('読込失敗',await p.evaluate(()=>{const x=document.getElementById('loadErr');return[x.hidden,x.textContent]}),e);
  await b.close();
})();
