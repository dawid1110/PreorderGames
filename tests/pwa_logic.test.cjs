'use strict';
// Regression tests for installation flow and static-only service worker.
// Run: node tests/pwa_logic.test.cjs [path/to/v3]
// This is a simulated runtime; it does not certify installation on a device.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(process.argv[2] || path.join(__dirname, '../v3'));
const source = fs.readFileSync(path.join(root, 'pwa.js'), 'utf8');
const workerSource = fs.readFileSync(path.join(root, 'sw.js'), 'utf8');
let passed = 0;
const tick = () => new Promise(resolve => setImmediate(resolve));
const RELEASE = /const RELEASE = '([^']+)'/.exec(workerSource)[1];

class EventTargetStub {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  addListener(listener) { this.addEventListener('change', listener); }
  async fire(type, fields = {}) {
    const event = { type, currentTarget: this, preventDefault() { this.prevented = true; }, ...fields };
    await Promise.all((this.listeners.get(type) || []).map(fn => fn(event)));
    return event;
  }
}
class NodeStub extends EventTargetStub {
  constructor() { super(); this.hidden = true; this.open = false; this.disabled = false; this.textContent = ''; this.isConnected = true; this.dataset = {}; }
  remove() { this.removed = true; this.isConnected = false; }
  showModal() { this.open = true; }
  close() { this.open = false; return this.fire('close'); }
  focus() { this.focused = true; }
  closest() { return null; }
}

function harness(options = {}) {
  const loc = new URL(options.url || 'https://preorderhub.pl/v3/index.html');
  const ids = Object.fromEntries(['pwa-manifest', 'pwa-native-install', 'pwa-message', 'pwa-dialog', 'pwa-close', 'pwa-done', 'pwa-update', 'pwa-update-title', 'pwa-update-message', 'pwa-update-now', 'pwa-later'].map(k => [k, new NodeStub()]));
  const invites = [new NodeStub(), new NodeStub()];
  const buttons = [new NodeStub(), new NodeStub()];
  const metas = [new NodeStub(), new NodeStub()];
  const guides = ['android', 'ios', 'desktop'].map(key => { const node = new NodeStub(); node.dataset.pwaGuide = key; return node; });
  const media = new Map();
  const registration = new EventTargetStub();
  registration.active = options.active || null;
  registration.waiting = options.waiting || null;
  registration.installing = options.installing || null;
  const calls = [];
  const window = new EventTargetStub();
  const alerts=[]; let reloads=0, redirect=null; const timers=new Map(); let timerId=0;
  loc.reload=()=>{reloads++;};loc.assign=v=>{redirect=v;};
  window.confirm=()=>options.confirm!==false;window.alert=m=>alerts.push(m);
  window.PREORDER_CAN_RELOAD=()=>options.canReload!==false;
  registration.update=async()=>{};
  window.isSecureContext = options.secure !== false;
  window.PREORDER_DEMO = options.demoFlag || false;
  window.matchMedia = query => {
    const m = new EventTargetStub();
    m.matches = !!options.standalone && query.includes('standalone');
    media.set(query, m);
    return m;
  };
  const navigator = {
    userAgent: options.ua || 'Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36',
    platform: options.platform || 'Linux armv8l', maxTouchPoints: options.touchPoints || 1,
    standalone: !!options.appleStandalone,
    serviceWorker: { register(url, opts) { calls.push({url, opts}); return options.rejectRegistration ? Promise.reject(new Error('offline')) : Promise.resolve(registration); } }
  };
  const swTarget=new EventTargetStub();
  navigator.serviceWorker.addEventListener=swTarget.addEventListener.bind(swTarget);
  if(options.regs)navigator.serviceWorker.getRegistrations=async()=>options.regs;
  if (options.noServiceWorker) delete navigator.serviceWorker;
  const document = {
    documentElement: {dataset: {demo: options.demoDataset ? 'true' : 'false'}},
    getElementById(id) { return ids[id] || null; },
    querySelectorAll(selector) {
      if (selector === '[data-pwa-install]') return invites;
      if (selector === '[data-pwa-open]') return buttons;
      if (selector === '[data-pwa-guide]') return guides;
      if (selector.startsWith('meta[')) return metas;
      throw new Error('Unexpected selector: '+selector);
    }
  };
  const context = vm.createContext({window, document, navigator, location: loc, URL, URLSearchParams, console, setTimeout(fn){const id=++timerId;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);}});
  Object.defineProperty(context, 'localStorage', {get() { throw new Error('PWA must not read tokens/storage'); }});
  vm.runInContext(source, context, {filename: 'pwa.js'});
  return {ids, invites, buttons, guides, calls, registration, window, media, metas, swTarget, alerts, timers, get reloads(){return reloads;}, get redirect(){return redirect;}};
}
async function test(name, action) {
  await action(); passed++; console.log('PASS '+name);
}

function swHarness(options={}) {
  const handlers = {}, state = {entries: new Map(), added: [], deleted: [], network: [], opened: [], skips:0};
  const cache = {
    async addAll(requests) { state.added.push(...requests); },
    async match(key) { if(options.matchError)throw Error('cache match failed');return state.entries.get(key); }
  };
  const self = {
    registration: {scope: 'https://preorderhub.pl/v3/'}, location: {origin:'https://preorderhub.pl'},
    addEventListener(type, fn) { handlers[type] = fn; },
    async skipWaiting() { state.skips++; },
    clients: {claim() { throw new Error('Unexpected claim'); }}
  };
  const caches = {
    async open(key) { if(options.openError)throw Error('cache open failed');state.opened.push(key); return cache; },
    async keys() { return ['preorderhub-v3-shell-OLD', 'preorderhub-v3-shell-'+RELEASE, ...(options.legacy?['preorderhub-v3-shell-20261124-2']:[]), 'legacy-root-cache', 'different-app']; },
    async delete(key) { state.deleted.push(key); return true; }
  };
  vm.runInNewContext(workerSource, {self, caches, URL, Request, Response, Set, Promise, fetch: async req => {state.network.push(req.url); if(options.networkError)throw Error('offline');return new Response('network-response');}}, {filename:'sw.js'});
  async function lifecycle(name) {
    let pending;
    handlers[name]({waitUntil(p) {pending = p;}});
    await pending;
  }
  async function fetchEvent(url, {method='GET',mode='cors',authorized=false} = {}) {
    let handled = false, response;
    const request = {url,method,mode,headers:new Headers(authorized?{Authorization:'Bearer TEST'}:{})};
    handlers.fetch({request,respondWith(p) {handled = true; response = p;}});
    return {handled,response:handled?await response:undefined};
  }
  async function message(data){let pending;handlers.message({data,waitUntil(p){pending=p;}});await pending;}
  return {state,lifecycle,fetchEvent,message};
}

(async () => {
  await test('Manifest, PNG dimensions and HTML wiring', () => {
    const manifest = JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
    assert.equal(manifest.id,'/'); assert.equal(manifest.scope,'./'); assert.equal(manifest.start_url,'./index.html'); assert.equal(manifest.display,'standalone');
    for(const size of [192,512]) {
      const icon = manifest.icons.find(i=>i.sizes===`${size}x${size}`);
      assert.ok(icon); assert.equal(icon.purpose,'any');
      const bytes=fs.readFileSync(path.join(root,icon.src));
      assert.equal(bytes.subarray(1,4).toString(),'PNG');
      assert.equal(bytes.readUInt32BE(16),size); assert.equal(bytes.readUInt32BE(20),size);
    }
    const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
    assert.ok(html.indexOf('src="config.js?')<html.indexOf('src="pwa.js?'));
    assert.ok(html.indexOf('src="pwa.js?')<html.indexOf('src="app.js?'));
    assert.equal((html.match(/data-pwa-install hidden/g)||[]).length,2);
    assert.ok(html.includes('aria-labelledby="pwa-title"'));
    assert.ok(!fs.readFileSync(path.join(root,'app.js'),'utf8').includes('serviceWorker.register'));
  });
  await test('Android shows instructions before and after login; one SW registration', async () => {
    const h=harness(); await tick();
    assert.equal(h.calls.length,1); assert.equal(h.calls[0].url,'./sw.js'); assert.equal(h.calls[0].opts.scope,'./'); assert.equal(h.calls[0].opts.updateViaCache,'none');
    assert.ok(h.invites.every(n=>!n.hidden)); assert.ok(h.ids['pwa-native-install'].hidden);
    assert.equal(h.guides.find(g=>g.open).dataset.pwaGuide,'android');
    await h.buttons[0].fire('click'); assert.ok(h.ids['pwa-dialog'].open);
    await h.ids['pwa-close'].fire('click'); assert.ok(h.buttons[0].focused);
  });
  await test('Prompt is single-use and success is reported only after appinstalled', async () => {
    const h=harness(); let prompts=0, resolve;
    const event=await h.window.fire('beforeinstallprompt',{prompt:()=>{prompts++;return new Promise(r=>resolve=r);}});
    assert.ok(event.prevented); assert.ok(!h.ids['pwa-native-install'].hidden);
    const first=h.ids['pwa-native-install'].fire('click');
    await h.ids['pwa-native-install'].fire('click'); assert.equal(prompts,1);
    resolve({outcome:'accepted'}); await first;
    assert.ok(h.ids['pwa-message'].textContent.includes('Zgoda'));
    assert.ok(h.invites.every(n=>!n.hidden));
    await h.window.fire('appinstalled');
    assert.ok(h.invites.every(n=>n.hidden)); assert.ok(h.ids['pwa-native-install'].hidden);
  });
  await test('Dismissed or failed prompts offer instructions without automatic retry', async () => {
    for (const failure of [false,true]) {
      const h=harness();let calls=0;
      await h.window.fire('beforeinstallprompt',{prompt:async()=>{calls++;if(failure)throw new Error('rejected');return {outcome:'dismissed'};}});
      await h.ids['pwa-native-install'].fire('click'); await h.ids['pwa-native-install'].fire('click');
      assert.equal(calls,1);assert.ok(h.ids['pwa-native-install'].hidden);assert.ok(!h.ids['pwa-message'].hidden); assert.ok(h.invites.every(n=>!n.hidden));
    }
  });
  await test('Legacy prompt userChoice fallback', async () => {
    const h=harness();
    await h.window.fire('beforeinstallprompt',{prompt:async()=>undefined,userChoice:Promise.resolve({outcome:'accepted'})});
    await h.ids['pwa-native-install'].fire('click');assert.ok(h.ids['pwa-message'].textContent.includes('Zgoda'));
  });
  await test('Demo variants never register, read session or promote installation', async () => {
    for (const opts of [{url:'https://preorderhub.pl/v3/index.html?demo=1'},{demoFlag:true},{demoDataset:true}]) {
      const h=harness(opts);await tick();
      assert.equal(h.calls.length,0);assert.ok(h.ids['pwa-manifest'].removed);assert.ok(h.metas.every(n=>n.removed));assert.ok(h.invites.every(n=>n.hidden));
      const e=await h.window.fire('beforeinstallprompt',{prompt:()=>{throw new Error('Demo prompt');}});assert.ok(e.prevented);
    }
  });
  await test('Insecure LAN and local-file origins receive instructions, not registration', async () => {
    for (const url of ['http://192.168.1.10:5500/v3/index.html','file:///tmp/index.html']) {
      const h=harness({url,secure:false});await tick();assert.equal(h.calls.length,0);assert.ok(h.ids['pwa-message'].textContent.includes('HTTPS'));
    }
    const local=harness({url:'http://localhost:5500/v3/index.html'});await tick();assert.equal(local.calls.length,1);
  });
  await test('Standalone mode hides install invitations but retains update handling', async () => {
    for (const opts of [{standalone:true},{appleStandalone:true}]) {
      const h=harness(opts);await tick(); assert.ok(h.invites.every(n=>n.hidden));assert.equal(h.calls.length,1);
    }
    const h=harness();const q=h.media.get('(display-mode: standalone)');q.matches=true;await q.fire('change');assert.ok(h.invites.every(n=>n.hidden));
  });
  await test('iPad desktop identity shows iOS instructions without a fake native button', () => {
    const h=harness({ua:'Mozilla/5.0 (Macintosh) Version/18.0 Safari',platform:'MacIntel',touchPoints:5});
    assert.equal(h.guides.find(n=>n.open).dataset.pwaGuide,'ios');assert.ok(h.ids['pwa-native-install'].hidden);
  });
  await test('Registration failure is visible and does not imply installation failed universally', async () => {
    const h=harness({rejectRegistration:true});await tick(); assert.ok(h.ids['pwa-message'].textContent.includes('Nie udało'));assert.ok(h.ids['pwa-message'].textContent.includes('może nadal'));
  });
  await test('A waiting update offers explicit activation without forcing a reload', async () => {
    const h=harness({waiting:new EventTargetStub()});await tick();assert.equal(h.ids['pwa-update'].hidden,false);
  });
  await test('Installation progress already in flight is observed before updatefound', async () => {
    const worker=new EventTargetStub(); worker.state='installing';
    const first=harness({installing:worker}); await tick();
    worker.state='redundant'; await worker.fire('statechange');
    assert.ok(first.ids['pwa-message'].textContent.includes('Nie udało'));
    const updating=new EventTargetStub(); updating.state='installing';
    const next=harness({active:{},installing:updating}); await tick();
    next.registration.waiting=updating; updating.state='installed'; await updating.fire('statechange');
    assert.equal(next.ids['pwa-update'].hidden,false);
  });
  await test('Worker install precaches only existing static files with reload semantics', async () => {
    const h=swHarness();await h.lifecycle('install');assert.equal(h.state.added.length,12);
    for(const req of h.state.added){assert.equal(req.cache,'reload');const url=new URL(req.url);assert.equal(url.origin,'https://preorderhub.pl');assert.ok(fs.existsSync(path.join(root,url.pathname.slice('/v3/'.length))));}
  });
  await test('Activation removes only this applications previous caches', async () => {
    const h=swHarness();await h.lifecycle('activate');assert.deepEqual(h.state.deleted,['preorderhub-v3-shell-OLD']);
  });
  await test('Navigation offline serves consistent cached shell for scoped entry points', async () => {
    const h=swHarness();h.state.entries.set('https://preorderhub.pl/v3/index.html','cached-index');
    for(const url of ['https://preorderhub.pl/v3/','https://preorderhub.pl/v3/index.html']){const r=await h.fetchEvent(url,{mode:'navigate'});assert.equal(r.response,'cached-index');}
    assert.equal(h.state.network.length,0);
  });
  await test('API, POST, Authorization, arbitrary paths, outside-scope and demo requests bypass SW', async () => {
    const h=swHarness();
    const scenarios=[['https://preorder-api-pdjz.onrender.com/get_preorders',{}],['https://preorderhub.pl/v3/index.html',{method:'POST'}],['https://preorderhub.pl/v3/index.html',{authorized:true}],['https://preorderhub.pl/v3/private.json',{}],['https://preorderhub.pl/v3/private',{mode:'navigate'}],['https://preorderhub.pl/index.html',{mode:'navigate'}],['https://preorderhub.pl/v3/index.html?demo=1',{mode:'navigate'}],['https://preorderhub.pl/v3/index.html?pwa-recover=1',{mode:'navigate'}]];
    for(const [url,opts] of scenarios)assert.equal((await h.fetchEvent(url,opts)).handled,false,url);
    assert.equal(h.state.opened.length,0);
  });
  await test('Allowed missing asset uses network without dynamically caching the response', async () => {
    const h=swHarness(); const r=await h.fetchEvent('https://preorderhub.pl/v3/pwa.js?v='+RELEASE);assert.equal(await r.response.text(),'network-response');assert.equal(h.state.added.length,0);assert.equal(h.state.network.length,1);
  });
  await test('Migration activates legacy releases only, normal installation waits', async()=>{
    const legacy=swHarness({legacy:true});await legacy.lifecycle('install');assert.equal(legacy.state.skips,1);
    const next=swHarness();await next.lifecycle('install');assert.equal(next.state.skips,0);
    await next.message({type:'UNKNOWN'});assert.equal(next.state.skips,0);await next.message({type:'PREORDER_SKIP_WAITING'});assert.equal(next.state.skips,1);
  });
  await test('Later hides banner, manual check restores it, no auto-reload',async()=>{
    const w=new EventTargetStub();const h=harness({waiting:w});await tick();await h.ids['pwa-later'].fire('click');assert.ok(h.ids['pwa-update'].hidden);await h.window.PREORDER_PWA.checkUpdate();assert.ok(!h.ids['pwa-update'].hidden);assert.equal(h.reloads,0);
  });
  await test('Update is single-use, waits for activation, reloads only once',async()=>{
    const w=new EventTargetStub();let messages=[];w.postMessage=m=>messages.push(m.type);const h=harness({waiting:w});await tick();await h.ids['pwa-update-now'].fire('click');await h.ids['pwa-update-now'].fire('click');assert.deepEqual(messages,['PREORDER_SKIP_WAITING']);assert.equal(h.reloads,0);h.registration.waiting=null;await h.swTarget.fire('controllerchange');assert.equal(h.reloads,1);assert.ok(h.ids['pwa-update'].hidden);w.state='activated';await w.fire('statechange');assert.equal(h.reloads,1);
  });
  await test('Update does not activate with open form or rejected confirmation',async()=>{
    for(const options of [{canReload:false},{confirm:false}]){const w=new EventTargetStub();w.postMessage=()=>{throw Error('must not activate');};const h=harness({waiting:w,...options});await tick();await h.ids['pwa-update-now'].fire('click');assert.equal(h.reloads,0);assert.ok(!h.ids['pwa-update-now'].disabled);}
  });
  await test('External activation hides banner without reloading',async()=>{
    const w=new EventTargetStub();const h=harness({waiting:w});await tick();h.registration.waiting=null;await h.swTarget.fire('controllerchange');assert.ok(h.ids['pwa-update'].hidden);assert.equal(h.reloads,0);
  });
  await test('Timed-out activation restores buttons and offers recovery',async()=>{
    const w=new EventTargetStub();w.postMessage=()=>{};const h=harness({waiting:w});await tick();await h.ids['pwa-update-now'].fire('click');[...h.timers.values()][0]();assert.ok(!h.ids['pwa-update-now'].disabled);assert.ok(h.ids['pwa-update-message'].textContent.includes('Nie udało'));
  });
  await test('Cleanup unregisters only known root registration',async()=>{
    const removed=[];const reg=(scope,script)=>({scope,active:{scriptURL:script},unregister:async()=>{removed.push(scope);return true;}});const h=harness({regs:[reg('https://preorderhub.pl/','https://preorderhub.pl/sw.js'),reg('https://preorderhub.pl/v3/','https://preorderhub.pl/v3/sw.js'),reg('https://preorderhub.pl/other/','https://preorderhub.pl/other/sw.js')]});await tick();assert.deepEqual(removed,['https://preorderhub.pl/']);h.window.PREORDER_PWA.reset();assert.equal(h.redirect,'https://preorderhub.pl/recover.html');
  });
  await test('Cache failure falls through to network; both failing returns readable 503',async()=>{
    const h=swHarness({openError:true});const ok=await h.fetchEvent('https://preorderhub.pl/v3/index.html',{mode:'navigate'});assert.equal(await ok.response.text(),'network-response');const off=swHarness({matchError:true,networkError:true});const r=await off.fetchEvent('https://preorderhub.pl/v3/index.html',{mode:'navigate'});assert.equal(r.response.status,503);assert.ok((await r.response.text()).includes('Napraw pamięć aplikacji'));
  });
  console.log(`\n${passed} test groups passed. Native Android installation and rendering require device/browser acceptance.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
