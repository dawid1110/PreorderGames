"""Rendering and SPA tests in Chromium using inline assets and mocked API.
Does not navigate to a real URL or validate the browser's real SW lifecycle.
Run: python tests/test_browser_inline.py [--capture]
"""
import base64
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / 'v3'
CAPTURE = '--capture' in sys.argv

def image_uri(p):
    return 'data:image/' + ('webp' if p.suffix=='.webp' else 'png') + ';base64,' + base64.b64encode(p.read_bytes()).decode()

assets = {str(p.relative_to(V3)):image_uri(p) for p in (V3/'assets').iterdir() if p.is_file()}
css = (V3/'style.css').read_text().replace('assets/crimson-hero.webp',assets['assets/crimson-hero.webp'])
mock = '''window.testStore={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>testStore[k]??null,setItem:(k,v)=>testStore[k]=String(v),removeItem:k=>delete testStore[k]}});
window.mock={logs:[],signup:true,features:true};
window.fetch=async(url,opts)=>{const path=new URL(url).pathname,method=opts.method;let data=opts.body instanceof URLSearchParams?Object.fromEntries(opts.body):opts.body?JSON.parse(opts.body):null;mock.logs.push({path,method,data,auth:opts.headers.Authorization});const send=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});if(path==='/public/config')return send(200,{signup_enabled:mock.signup,features_enabled:mock.features,privacy_url:'https://example.invalid/privacy',terms_url:'https://example.invalid/terms',policy_version:'test-1'});if(path==='/register'){if(!data.accept_terms||data.policy_version!=='test-1')throw Error('Bad registration payload');return send(200,{status:'success'});}if(path==='/login')return send(200,{access_token:'mock-token',user_id:1,username:'Tester'});if(opts.headers.Authorization!=='Bearer mock-token')return send(401,{detail:'No auth'});if(path==='/get_preorders'||path==='/get_collection')return send(200,[]);if(path==='/account/capabilities')return send(200,{public_features:mock.features,admin:true,can_delete:true});if(path==='/account/export')return send(200,{account:{username:'Tester'},games:[]});if(path==='/feedback'){if(data.category!=='bug')throw Error('Bad category');return send(200,{status:'success'});}if(path==='/admin/overview')return send(200,{users:2,active_7d:1,preorders:3,feedback_count:1,feedback:[{category:'bug',message:'Test <script>unsafe<\\/script>',created_at:'2026-11-24'}]});if(path==='/account/delete'){if(data.confirmation!=='USUN')throw Error('Bad confirmation');return send(200,{status:'success'});}return send(404,{detail:'Unexpected mock route'});};'''

def load_app(page,demo):
    html=(V3/'index.html').read_text()
    html=re.sub(r'<link[^>]+>','',html)
    html=re.sub(r'<script defer src="[^\"]+"></script>','',html)
    js=(V3/'app.js').read_text().replace("const demo=new URLSearchParams(location.search).get('demo')==='1';",f'const demo={str(demo).lower()};').replace('return "/v3/"+value;try{const u=new URL(value);','return window.testAssets[value]||value;try{const u=new URL(value);')
    pwa=(V3/'pwa.js').read_text()
    html=html.replace('</head>','<style>'+css+'</style></head>')
    html=html.replace('</body>','<script>'+mock+'\nwindow.PREORDER_DEMO='+str(demo).lower()+';window.testAssets='+json.dumps(assets)+';\n'+(V3/'config.js').read_text()+'\n'+pwa+'\n'+js+'</script></body>')
    page.set_content(html)

def capture(page,name):
    temp=ROOT/'launch'/f'{name}.tmp.png'
    page.screenshot(path=temp,animations='disabled')
    Image.open(temp).convert('RGB').save(ROOT/'launch'/f'{name}.webp','WEBP',quality=86)
    temp.unlink()

def load_landing(page):
    html=(ROOT/'index.html').read_text()
    html=re.sub(r'<link[^>]+>','',html)
    html=re.sub(r'<script defer src="[^\"]+"></script>','',html)
    html=html.replace('</head>','<style>'+(ROOT/'launch/style.css').read_text()+'</style></head>')
    for name in ['v3/assets/icon-192.png','launch/dashboard.webp','launch/mobile.webp']:
        html=html.replace('src="'+name+'"','src="'+image_uri(ROOT/name)+'"')
    page.set_content(html)
    page.locator('img').evaluate_all("nodes=>nodes.forEach(n=>n.loading='eager')")
    page.wait_for_function("[...document.images].every(n=>n.complete&&n.naturalWidth>0)")

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    context=browser.new_context(accept_downloads=True,service_workers='block',viewport={'width':1440,'height':1000})
    context.route('**/*',lambda r:r.abort())
    errors=[]
    def new_page(width=None,height=None):
        pg=context.new_page();pg.set_default_timeout(5000);pg.on('pageerror',lambda e:errors.append(str(e)))
        if width:pg.set_viewport_size({'width':width,'height':height})
        return pg
    page=new_page();load_app(page,True);expect(page.locator('#app')).to_be_visible();expect(page.locator('#demo-notice')).to_be_visible();expect(page.locator('#boot-fallback')).to_be_hidden();page.wait_for_timeout(100)
    assert page.evaluate('mock.logs.length')==0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if CAPTURE:capture(page,'dashboard')
    mobile=new_page(412,860);load_app(mobile,True);expect(mobile.locator('#app')).to_be_visible();mobile.wait_for_timeout(100)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if CAPTURE:capture(mobile,'mobile')
    landing=new_page();load_landing(landing);expect(landing.get_by_role('heading',level=1)).to_contain_text('Twój budżet.')
    assert landing.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert landing.locator('img').evaluate_all('(nodes)=>nodes.every(n=>n.complete&&n.naturalWidth>0)')
    if CAPTURE:
        landing.screenshot(path=ROOT.parent/'PreorderHub_3.2_landing_desktop.png',full_page=True)
        landing.set_viewport_size({'width':1200,'height':630});capture(landing,'share')
    mp=new_page(412,860);load_landing(mp);assert mp.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if CAPTURE:mp.screenshot(path=ROOT.parent/'PreorderHub_3.2_landing_mobile.png',full_page=True)
    print('PASS: demo isolated from API, desktop and mobile layouts, landing image assets')
    failed=new_page();failed.set_content((V3/'index.html').read_text());expect(failed.locator('#boot-fallback')).to_be_visible();expect(failed.locator('#auth')).to_be_hidden();
    user=new_page();load_app(user,False);expect(user.locator('#auth')).to_be_visible();user.locator('#auth-toggle').click();expect(user.locator('#auth-title')).to_have_text('Utwórz konto');user.locator('#auth-username').fill('Tester');user.locator('#auth-password').fill('long-test-password');user.locator('#auth-accept').check();user.locator('#auth-submit').click();expect(user.locator('#auth-title')).to_have_text('Witaj ponownie')
    user.locator('#auth-password').fill('long-test-password');user.locator('#auth-submit').click();expect(user.locator('#app')).to_be_visible();expect(user.locator('#connection-text')).to_have_text('Połączono z API');user.locator('#desktop-nav').get_by_role('button',name='Ustawienia').click();expect(user.get_by_role('button',name='Resetuj pamięć PWA')).to_be_visible();user.get_by_role('button',name='Otwórz narzędzia konta').click();expect(user.get_by_role('heading',name='Eksport danych')).to_be_visible()
    user.get_by_label('Typ zgłoszenia').select_option('bug');user.get_by_label('Wiadomość').fill('Przykładowy błąd');user.get_by_role('button',name='Wyślij zgłoszenie').click();expect(user.locator('.account-message')).to_have_text('Zgłoszenie zapisane. Dziękujemy!')
    with user.expect_download() as download:user.get_by_role('button',name='Pobierz dane JSON').click()
    assert download.value.suggested_filename=='preorderhub-export.json'
    user.get_by_role('button',name='Pobierz statystyki').click();expect(user.locator('.admin-stat')).to_have_count(4);expect(user.locator('.admin-item p')).to_have_text('Test <script>unsafe</script>');assert user.locator('.admin-item script').count()==0
    user.get_by_label('Potwierdź hasłem').fill('long-test-password');user.get_by_label('Wpisz USUN').fill('USUN');user.once('dialog',lambda d:d.accept());user.get_by_role('button',name='Usuń trwale konto').click();expect(user.locator('#auth')).to_be_visible();assert user.evaluate("localStorage.getItem('access_token')") is None
    user.evaluate('mock.signup=false');user.locator('#auth-toggle').click();expect(user.locator('#auth-error')).to_contain_text('zamknięta');assert not errors,errors
    print('PASS: register, login, settings, feedback, export, admin stats, literal HTML, account deletion, disabled signup')
    browser.close()
