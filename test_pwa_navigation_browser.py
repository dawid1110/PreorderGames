"""Regression test for hosts redirecting /v3/index.html to /v3/.
Run: python tests/test_pwa_navigation_browser.py [old_3_2_0_directory]
Requires Chromium/Playwright and loopback networking. API is mocked.
"""
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect, Error

ROOT = Path(__file__).resolve().parents[1]

class RedirectingHost(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path in ('/v3/index.html', '/v3/index'):
            self.send_response(308)
            self.send_header('Location', '/v3/' + ('?' + parsed.query if parsed.query else ''))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def test(browser, root, old=False):
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(RedirectingHost, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    ctx = browser.new_context(viewport={'width': 412, 'height': 860}, is_mobile=True, has_touch=True)
    requests = []

    def mock(route):
        request = route.request
        path = urlsplit(request.url).path
        headers = {'Access-Control-Allow-Origin': base, 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Authorization, Content-Type'}
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=headers, body='')
        requests.append((path, request.method))
        data = {'/login': {'access_token': 'mock-only', 'user_id': 1, 'username': 'Tester'}, '/get_preorders': [], '/get_collection': []}.get(path, {})
        route.fulfill(status=200, headers=headers, content_type='application/json', body=json.dumps(data))

    ctx.route('https://preorder-api-pdjz.onrender.com/**', mock)
    try:
        page = ctx.new_page()
        page.set_default_timeout(12000)
        page.goto(base + '/v3/', timeout=15000)
        expect(page.locator('#auth')).to_be_visible()
        page.evaluate('navigator.serviceWorker.ready.then(() => true)')
        assert page.evaluate('''async () => {
          const keys = await caches.keys();
          const cache = await caches.open(keys.find(k=>k.startsWith('preorderhub-v3-shell-')));
          const response = await cache.match(location.origin + '/v3/index.html');
          return !!response && response.redirected && response.url.endsWith('/v3/');
        }'''), 'Expected actual followed redirect in CacheStorage'
        if old:
            try:
                page.goto(base + '/v3/index.html', timeout=12000)
                expect(page.locator('#auth')).to_be_visible(timeout=4000)
            except (Error, AssertionError) as exc:
                print('OLD release reproduces navigation failure:', str(exc).splitlines()[0])
                return
            raise AssertionError('The old failure was not reproduced')
        page.goto(base + '/v3/index.html', timeout=15000)
        expect(page.locator('#auth')).to_be_visible()
        assert page.evaluate('!!navigator.serviceWorker.controller'), 'Expected a real controlling worker'
        page.locator('#auth-username').fill('Tester')
        page.locator('#auth-password').fill('test-password')
        page.locator('#auth-submit').click()
        expect(page.locator('#app')).to_be_visible()
        expect(page.locator('#connection-text')).to_have_text('Połączono z API')
        assert requests.count(('/login','POST')) == 1
        for entry in ('/v3/index.html', '/v3/', '/v3/index', '/v3/index.html#preorders'):
            page.goto(base + entry, timeout=15000)
            expect(page.locator('#app')).to_be_visible()
            expect(page.locator('#connection-text')).to_have_text('Połączono z API')
        assert requests.count(('/login','POST')) == 1
        page.goto(base + '/v3/index.html?demo=1')
        expect(page.locator('#demo-notice')).to_be_visible()
        assert requests.count(('/login','POST')) == 1
        page.goto(base + '/v3/')
        expect(page.locator('#app')).to_be_visible()
        # A real offline reload must accept the cached followed response after
        # the worker strips redirect metadata. API data still requires network.
        ctx.set_offline(True)
        page.goto(base + '/v3/index.html', timeout=15000)
        expect(page.locator('#app')).to_be_visible()
        assert page.evaluate("localStorage.getItem('access_token')") == 'mock-only'
        print('PASS: real Chromium service worker, redirected precache, mobile login, 4 online routes, demo and offline navigation')
    finally:
        ctx.close()
        server.shutdown()
        server.server_close()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    if len(sys.argv) > 1:
        test(browser, Path(sys.argv[1]).resolve(), old=True)
    test(browser, ROOT)
    browser.close()
