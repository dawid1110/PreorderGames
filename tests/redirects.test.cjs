'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const routes = {
  'index.html':'','pwa-list.html':'#preorders','pwa-index.html':'#dashboard',
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
    assert.equal(redirect,'./v3/index.html'+search+(hash||fragment));
    const resolved = new URL(redirect, 'https://preorderhub.pl/'+file);
    assert.equal(resolved.pathname, '/v3/index.html');
    assert.equal(resolved.origin, 'https://preorderhub.pl');
  }
}
console.log('PASS: 14 legacy URLs, each with 3 query/hash variants (42 checks).');
