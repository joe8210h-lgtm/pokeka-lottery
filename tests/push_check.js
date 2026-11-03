// 通知の画面と service worker の確認(実際のpushサービスは使わず、偽の宛先で確認する)。実行: node tests/push_check.js
const {chromium}=require('playwright');const fs=require('fs');const os=require('os');const path=require('path');const http=require('http');
const ROOT=path.resolve(__dirname,'..');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'push-'));
for(const f of ['index.html','sw.js','notify-core.js','manifest.webmanifest','privacy.html'])fs.copyFileSync(path.join(ROOT,f),path.join(tmp,f));
fs.cpSync(path.join(ROOT,'assets/icons'),path.join(tmp,'assets/icons'),{recursive:true});fs.mkdirSync(path.join(tmp,'data'));
for(const f of ['products.json','shops.json','affiliate.json'])if(fs.existsSync(path.join(ROOT,'data',f)))fs.copyFileSync(path.join(ROOT,'data',f),path.join(tmp,'data',f));
const base=JSON.parse(fs.readFileSync(path.join(ROOT,'data/lotteries.json'),'utf8'))[0];
const iso=(ms)=>new Date(Date.now()+ms).toISOString().replace(/\.\d+Z$/,'+00:00');
const mk=(id,o={})=>({...base,id,shop_name:'ビックカメラ池袋本店',product:'拡張パック「アビスアイ」',status:'open',entry_start:iso(-36e5),entry_end:iso(48*36e5),result_date:null,purchase_start:null,purchase_end:null,
  review_needed:false,confidence:.95,source_grade:'store_notice',consistency:{status:'match',checked_at:null,conflict_fields:[]},first_seen_at:iso(-60000),requirements:[],...o});
const write=(items)=>fs.writeFileSync(path.join(tmp,'data/lotteries.json'),JSON.stringify(items));
write([mk('fx-1')]);
const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.webmanifest':'application/manifest+json'};
const srv=http.createServer((q,r)=>{let p=decodeURIComponent(q.url.split('?')[0]);if(p.endsWith('/'))p+='index.html';const f=path.join(tmp,p);
  if(!f.startsWith(tmp)||!fs.existsSync(f)||fs.statSync(f).isDirectory()){r.statusCode=404;return r.end()}
  r.setHeader('content-type',mime[path.extname(f)]||'application/octet-stream');r.end(fs.readFileSync(f))});
(async()=>{
  await new Promise(r=>srv.listen(8766,r));const B='http://localhost:8766';
  const b=await chromium.launch({channel:'chromium'});const ctx=await b.newContext({viewport:{width:393,height:780}});await ctx.grantPermissions(['notifications'],{origin:B});
  const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));
  const calls=[];
  await p.route('**/api/**',async r=>{const u=new URL(r.request().url());calls.push(u.pathname);
    if(u.pathname==='/api/vapid')return r.fulfill({json:{publicKey:'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U'}});
    return r.fulfill({json:{ok:true}})});
  await p.addInitScript(()=>{ // 実際のpushサービス(FCM)には接続できないので、登録を偽物にする
    PushManager.prototype.getSubscription=async function(){return window.__sub||null};
    PushManager.prototype.subscribe=async function(){window.__sub={endpoint:'https://fcm.googleapis.com/fcm/send/test',unsubscribe:async()=>{window.__sub=null;return true}};return window.__sub};
  });
  await p.goto(B+'/index.html');await p.waitForTimeout(1500);await p.evaluate(()=>navigator.serviceWorker.ready);await p.reload();await p.waitForTimeout(1200);
  // 設定の画面: 通知のスイッチがある。オフの間は、種類の選択肢は出ない
  await p.click('nav button[data-v="note"]');await p.waitForTimeout(300);
  const off=await p.evaluate(()=>({sw:!!document.querySelector('[data-nt=on]'),kinds:!!document.querySelector('[data-nt="k.new"]')}));
  await p.check('[data-nt=on]');await p.waitForTimeout(1500);
  const on=await p.evaluate(()=>({pf:JSON.parse(localStorage.getItem('chusen_notify_v1')).on,kinds:!!document.querySelector('[data-nt="k.new"]'),msg:document.querySelector('#set').innerText.includes('通知をオンにしました')}));
  // おやすみ時間は、テストの時刻に左右されないよう切る
  await p.uncheck('[data-nt=quiet]');await p.waitForTimeout(500);
  const idb=await p.evaluate(()=>RaffNotify.kvGet('notified'));await p.waitForTimeout(500);
  const prefs=await p.evaluate(()=>RaffNotify.kvGet('prefs'));
  // push: 登録前からある抽選(fx-1)は通知しない
  const sw=ctx.serviceWorkers()[0];
  const shown=async()=>await sw.evaluate(async()=>(await self.registration.getNotifications()).map(n=>n.title+'|'+n.body));
  await sw.evaluate(()=>{self.dispatchEvent(new PushEvent('push'))});await p.waitForTimeout(1500);
  const n0=await shown();
  // 新しい抽選が出たら通知される
  write([mk('fx-1'),mk('fx-2',{product:'拡張パック「ハドウシーカー」'})]);
  await sw.evaluate(()=>{self.dispatchEvent(new PushEvent('push'))});await p.waitForTimeout(1500);
  const n1=await shown();
  // 同じ抽選は、もう通知しない
  await sw.evaluate(()=>{self.dispatchEvent(new PushEvent('push'))});await p.waitForTimeout(1500);
  const n2=await shown();
  // 未確認の抽選は通知しない
  write([mk('fx-1'),mk('fx-2'),mk('fx-3',{review_needed:true})]);
  await sw.evaluate(()=>{self.dispatchEvent(new PushEvent('push'))});await p.waitForTimeout(1500);
  const n3=await shown();
  // 通知から開く: ?lottery=ID でそのカードへ
  const page2=await ctx.newPage();await page2.route('**/api/**',r=>r.fulfill({json:{ok:true}}));await page2.goto(B+'/index.html?lottery=fx-2');await page2.waitForTimeout(2000);
  const jump=await page2.evaluate(()=>({url:location.search,cur:(O[a]!==undefined&&D[O[a]])?D[O[a]].id:null}));
  // オフにすると、解除が呼ばれ、スイッチが切れる
  await p.click('nav button[data-v="note"]');await p.uncheck('[data-nt=on]');await p.waitForTimeout(1500);
  const offAgain=await p.evaluate(()=>({pf:JSON.parse(localStorage.getItem('chusen_notify_v1')).on,sub:window.__sub}));
  const out={off,on,idb:(idb||[]).join(','),prefsOn:prefs&&prefs.on,n0,n1,n2len:n2.length,n3len:n3.length,jump,offAgain,calls:[...new Set(calls)],errs};
  console.log(JSON.stringify(out));
  const ok=off.sw&&!off.kinds&&on.pf&&on.kinds&&on.msg&&out.idb.includes('fx-1:new')&&out.prefsOn&&n0.length===0
    &&n1.length===1&&n1[0].startsWith('新着の抽選|')&&n1[0].includes('ハドウシーカー')&&n2.length===1&&n3.length===1&&jump.cur==='fx-2'&&jump.url===''
    &&offAgain.pf===false&&offAgain.sub===null&&calls.includes('/api/subscribe')&&calls.includes('/api/unsubscribe')&&errs.length===0;
  await b.close();srv.close();process.exit(ok?0:1);
})();
