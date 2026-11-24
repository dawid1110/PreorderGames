'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const routes = {
  'pwa-list.html':'#preorders','pwa-index.html':'#dashboard',
  'list.html':'#preorders','collection.html':'#collection','pwa-collection.html':'#collection',
  'login.html':'','register.html':'','add.html':'#preorders','edit.html':'#preorders',
  'pwa-add.html':'#preorders','pwa-edit.html':'#preorders','bento.html':'#dashboard','console.html':'#dashboard'
};
for (const [file, fragment] of Object.entries(routes)) {
  const html = fs.readFileSync(path.join(root, file),'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  for (const [search, hash] of [['',''],['?demo=1',''],['?demo=1','#calendar']]) {
    let redirect;
    vm.runInNewContext(script, {location:{search,hash,replace:value=>{redirect=value;}}});
    const expected = file === 'register.html' ? './v3/index.html?register=1' + (search ? '&' + search.slice(1) : '') + (hash||fragment) : './v3/index.html'+search+(hash||fragment);
    assert.equal(redirect, expected);
    const resolved = new URL(redirect, 'https://preorderhub.pl/'+file);
    assert.equal(resolved.pathname, '/v3/index.html');
    assert.equal(resolved.origin, 'https://preorderhub.pl');
  }
}
const landing = fs.readFileSync(path.join(root,'launch/landing.js'),'utf8');
for(const [search,hash,expected] of [['','',''],['','#funkcje',''],['','#android',''],['?demo=1','','./v3/index.html?demo=1'],['','#preorders','./v3/index.html#preorders'],['?register=1','','./v3/index.html?register=1']]){let redirect='';vm.runInNewContext(landing,{URLSearchParams,location:{search,hash,replace:v=>{redirect=v;}}});assert.equal(redirect,expected);}
console.log('PASS: 39 legacy-route checks + 6 landing-route checks.');
