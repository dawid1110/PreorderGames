"""Verify deployed asset URLs without contacting production."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
ROOT = Path(__file__).resolve().parents[1]
class Assets(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='script' and a.get('src'): self.urls.append(a['src'])
        if tag=='link' and a.get('rel') in ('icon','apple-touch-icon','manifest','stylesheet'): self.urls.append(a['href'])
        if tag=='img' and a.get('src'): self.urls.append(a['src'])

def test_all_app_entry_paths():
    parser=Assets(); parser.feed((ROOT/'v3/index.html').read_text())
    for path in ['/v3','/v3/','/v3/index','/v3/index.html','/v3/index.html?demo=1']:
        for url in parser.urls:
            resolved=urlsplit(urljoin('https://preorderhub.pl'+path,url))
            assert resolved.path.startswith('/v3/'),(path,url,resolved.path)
            assert (ROOT/resolved.path.lstrip('/')).is_file(),(path,url)

def test_root_is_landing_not_spa():
    html=(ROOT/'index.html').read_text()
    assert 'launch/style.css' in html and 'id="auth"' not in html
    parser=Assets(); parser.feed(html)
    for path in ['/','/index.html','/index']:
        for url in parser.urls:
            resolved=urlsplit(urljoin('https://preorderhub.pl'+path,url))
            assert (ROOT/resolved.path.lstrip('/')).is_file(),(path,url)

def test_no_nav_interception():
    for path in ['sw.js','v3/sw.js']:
        assert 'respondWith(' not in (ROOT/path).read_text()

if __name__=='__main__':
    test_all_app_entry_paths();test_root_is_landing_not_spa();test_no_nav_interception()
    print('PASS: assets on five v3 URL variants; root landing assets; both workers bypass navigation')
