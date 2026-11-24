"""Optional browser acceptance tests and actual preview captures.
Requires Playwright and Chromium; no requests to production API.
Run from repo: python tests/test_browser_launch.py [--capture]
"""
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = '--capture' in sys.argv

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
settings = {'signup_enabled': True, 'features_enabled': True, 'operator':'Test operator',
    'contact_email':'test@example.invalid','privacy_url':'https://example.invalid/privacy',
    'terms_url':'https://example.invalid/terms','policy_version':'test-1'}
requests = []

def mock(route):
    req = route.request
    path = urlsplit(req.url).path
    requests.append((path, req.method, req.post_data))
    headers = {'Access-Control-Allow-Origin':base, 'Access-Control-Allow-Methods':'GET, POST, PUT, DELETE, OPTIONS', 'Access-Control-Allow-Headers':'Authorization, Content-Type'}
    if req.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers, body=''); return
    data, status = {}, 200
    if path == '/public/config': data = settings
    elif path == '/register':
        payload = json.loads(req.post_data)
        assert payload['accept_terms'] is True and payload['policy_version'] == 'test-1'
        data = {'status':'success'}
    elif path == '/login': data = {'access_token':'test-only-token','user_id':1,'username':'Tester'}
    elif path == '/get_preorders': data = []
    elif path == '/get_collection': data = []
    elif path == '/account/capabilities': data = {'public_features':True,'admin':True,'can_delete':True}
    elif path == '/account/export': data = {'account': {'username':'Tester'},'games':[]}
    elif path == '/feedback':
        assert json.loads(req.post_data)['category'] == 'bug'
        data = {'status':'success'}
    elif path == '/admin/overview': data = {'users':2,'active_7d':1,'preorders':3,'feedback_count':1,'feedback':[{'id':1,'category':'bug','message':'Test <script>unsafe</script>','created_at':'2026-11-24'}]}
    elif path == '/account/delete':
        assert json.loads(req.post_data)['confirmation']=='USUN'
        data = {'status':'success'}
    else: status=404; data={'detail':'Unexpected mock route'}
    route.fulfill(status=status,headers=headers,content_type='application/json',body=json.dumps(data))

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block',accept_downloads=True)
    context.route('https://preorder-api-pdjz.onrender.com/**', mock)
    context.route('https://example.invalid/**', lambda r:r.fulfill(status=200,body='Test document'))
    page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/v3/index.html?demo=1');expect(page.locator('#app')).to_be_visible();expect(page.locator('#demo-notice')).to_be_visible()
    page.wait_for_timeout(250)
    if CAPTURE:
        from PIL import Image
        page.screenshot(path=ROOT/'launch/dashboard.tmp.png'); Image.open(ROOT/'launch/dashboard.tmp.png').save(ROOT/'launch/dashboard.webp','WEBP',quality=88); (ROOT/'launch/dashboard.tmp.png').unlink()
    assert not requests, requests
    mobile=context.new_page()
    mobile.set_viewport_size({'width':412,'height':860});mobile.goto(base+'/v3/index.html?demo=1');expect(mobile.locator('#app')).to_be_visible();mobile.wait_for_timeout(250)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if CAPTURE:
        from PIL import Image
        mobile.screenshot(path=ROOT/'launch/mobile.tmp.png');Image.open(ROOT/'launch/mobile.tmp.png').save(ROOT/'launch/mobile.webp','WEBP',quality=88);(ROOT/'launch/mobile.tmp.png').unlink()
    mobile.goto(base+'/');expect(mobile.get_by_role('heading',level=1)).to_contain_text('Twój budżet.')
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.get_by_role('link',name='Wypróbuj demo').click();expect(mobile.locator('#demo-notice')).to_be_visible()
    assert not requests,requests
    page.goto(base+'/');expect(page.get_by_role('heading',level=1)).to_contain_text('Twój budżet.')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if CAPTURE:
        page.screenshot(path='/mnt/data/PreorderHub_3.2_landing_desktop.png',full_page=True)
        page.set_viewport_size({'width':1200,'height':630});page.screenshot(path=ROOT/'launch/share.tmp.png');Image.open(ROOT/'launch/share.tmp.png').save(ROOT/'launch/share.webp','WEBP',quality=88);(ROOT/'launch/share.tmp.png').unlink();page.set_viewport_size({'width':1440,'height':1000})
        mobile.goto(base+'/');mobile.screenshot(path='/mnt/data/PreorderHub_3.2_landing_mobile.png',full_page=True)
    page.get_by_role('link',name='Utwórz konto').click();expect(page.locator('#auth-title')).to_have_text('Utwórz konto')
    page.locator('#auth-username').fill('Tester');page.locator('#auth-password').fill('long-test-password');page.locator('#auth-accept').check();page.locator('#auth-submit').click();expect(page.locator('#auth-title')).to_have_text('Witaj ponownie')
    page.locator('#auth-password').fill('long-test-password');page.locator('#auth-submit').click();expect(page.locator('#app')).to_be_visible();expect(page.locator('#connection-text')).to_have_text('Połączono z API')
    page.goto(base+'/v3/index.html#settings');expect(page.get_by_role('button',name='Otwórz narzędzia konta')).to_be_visible();page.get_by_role('button',name='Otwórz narzędzia konta').click();expect(page.get_by_role('heading',name='Eksport danych')).to_be_visible()
    page.get_by_label('Typ zgłoszenia').select_option('bug');page.get_by_label('Wiadomość').fill('Przykładowy błąd w aplikacji');page.get_by_role('button',name='Wyślij zgłoszenie').click();expect(page.locator('.account-message')).to_have_text('Zgłoszenie zapisane. Dziękujemy!')
    with page.expect_download() as download:
        page.get_by_role('button',name='Pobierz dane JSON').click()
    assert download.value.suggested_filename=='preorderhub-export.json'
    page.get_by_role('button',name='Pobierz statystyki').click();expect(page.locator('.admin-stat')).to_have_count(4);expect(page.locator('.admin-item p')).to_have_text('Test <script>unsafe</script>');assert page.locator('.admin-item script').count()==0
    if CAPTURE: page.screenshot(path='/mnt/data/PreorderHub_3.2_account_tools.png')
    page.get_by_label('Potwierdź hasłem').fill('long-test-password');page.get_by_label('Wpisz USUN').fill('USUN');page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Usuń trwale konto').click();expect(page.locator('#auth')).to_be_visible();assert page.evaluate("localStorage.getItem('access_token')") is None
    settings['signup_enabled']=False;page.goto(base+'/v3/index.html?register=1');expect(page.locator('#auth-error')).to_contain_text('zamknięta');expect(page.locator('#auth-title')).to_have_text('Witaj ponownie')
    assert not errors, errors
    print('PASS: desktop/mobile landing, isolated demo, registration, login, feedback, export, admin stats, safe rendering, delete and closed-signup UX')
    context.close()
    # Actual Chromium registration and activation on secure local origin.
    ctx=browser.new_context();ctx.route('https://preorder-api-pdjz.onrender.com/**', mock)
    pg=ctx.new_page();pg.goto(base+'/v3/index.html');expect(pg.locator('#auth')).to_be_visible();pg.evaluate('navigator.serviceWorker.ready');assert pg.evaluate("navigator.serviceWorker.getRegistration().then(r=>r.scope.endsWith('/v3/'))")
    pg.get_by_role('button',name='Zainstaluj aplikację').first.click();expect(pg.locator('#pwa-dialog')).to_be_visible();print('PASS: browser SW registration and installation instructions')
    ctx.close();browser.close()
server.shutdown()
