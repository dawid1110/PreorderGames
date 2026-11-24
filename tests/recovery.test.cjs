'use strict';
const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../launch/recover.js'),'utf8');
async function run(fail=false){
 const removed=[],deleted=[];let redirect='',click;
 const base='https://preorderhub.pl/';
 const reg=(scope,script)=>({scope:base+scope,active:{scriptURL:base+script},unregister:async()=>{if(fail)throw Error('blocked');removed.push(scope);return true;}});
 const button={disabled:false,addEventListener(t,f){click=f;}},status={textContent:''};
 const context={URL,location:{href:base+'recover.html',replace:v=>{redirect=v;}},document:{getElementById:id=>id==='recovery-run'?button:status},window:{caches:{}},navigator:{serviceWorker:{getRegistrations:async()=>[reg('','sw.js'),reg('v3/','v3/sw.js'),reg('other/','other/sw.js'),reg('','unknown.js')]}},caches:{keys:async()=>['preorderhub-v3-shell-20261124-2','preorderhub-v3-shell-20261124-4','different-app'],delete:async k=>{deleted.push(k);return true;}}};
 Object.defineProperty(context,'localStorage',{get(){throw Error('Must not access user session');}});
 vm.runInNewContext(source,context);await click();
 if(fail){assert.equal(button.disabled,false);assert.equal(redirect,'');assert.match(status.textContent,/nie zakończył/);}
 else{assert.deepEqual(removed,['','v3/']);assert.deepEqual(deleted,['preorderhub-v3-shell-20261124-2','preorderhub-v3-shell-20261124-4']);assert.equal(redirect,base+'v3/index.html?pwa-recover=1');}
}
(async()=>{await run();await run(true);console.log('PASS: selective recovery and error fallback (2 cases).');})().catch(e=>{console.error(e);process.exitCode=1;});
