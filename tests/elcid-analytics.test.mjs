import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {configureElcidAnalytics} from '../scripts/configure-elcid-analytics.mjs';
const src=readFileSync(new URL('../elcid-site/site.js',import.meta.url),'utf8').split('// EL CID public storefront only. No vendor starts before specific consent.')[1];
function browser(url='https://www.elcidspain.com/',id='G-ELCIDTEST',stored=null){
 const source=configureElcidAnalytics(src,id);
 const location=new URL(url);let reloads=0;location.reload=()=>reloads++;
 const store=new Map(),scripts=[],nodes=[],handlers={},docEvents={};
 if(stored!==null)store.set('elcid-analytics-consent-v1',JSON.stringify({analytics:stored,at:Date.now()}));
 function node(tag){const n={tag,hidden:false,children:[],events:{},append(...a){this.children.push(...a)},setAttribute(){},addEventListener(k,f){this.events[k]=f},focus(){}};nodes.push(n);return n;}
 const document={documentElement:{lang:'en'},referrer:'https://example.org/private?token=secret',cookie:'',body:node('body'),head:{append(n){scripts.push(n.src)}},querySelector(){return null},createElement:node,addEventListener(k,f){docEvents[k]=f}};
 const window={addEventListener(k,f){handlers[k]=f}};
 const localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)};
 vm.runInNewContext(source,{window,document,location,URL,URLSearchParams,Date,localStorage});
 return {scripts,nodes,docEvents,window,choose(t){nodes.find(n=>n.textContent===t).events.click()},reloads:()=>reloads,events:()=>Array.from(window.dataLayer||[],x=>Array.from(x))};
}
test('missing or shared GA ID never starts a tracker',()=>{
 const b=browser('https://www.elcidspain.com/','');assert.equal(b.scripts.length,0);assert.equal(b.nodes.length,1);
 assert.throws(()=>configureElcidAnalytics(src,'G-T57TZW9QVK'));
});
test('new visitor and rejection load no Google',()=>{
 const b=browser();assert.equal(b.scripts.length,0);b.choose('Reject');assert.equal(b.scripts.length,0);
});
test('accept starts only verified GA; advertising denied, sanitized event',()=>{
 const b=browser('https://www.elcidspain.com/en?utm_source=threads');b.choose('Accept analytics');
 assert.equal(b.scripts.length,1);assert.ok(b.scripts[0].endsWith('G-ELCIDTEST'));
 const u=b.events().find(e=>e[0]==='consent'&&e[1]==='update');assert.equal(u[2].ad_storage,'denied');
 const p=b.events().find(e=>e[0]==='event'&&e[1]==='page_view');assert.equal(p[2].page_referrer,'https://example.org/');assert.ok(p[2].page_location.includes('utm_source=threads'));
 assert.ok(!JSON.stringify(b.events()).includes('token=secret'));
});
test('private staff routes and unrecognized query never mount analytics',()=>{
 for(const url of ['https://staff.elcidspain.com/','https://www.elcidspain.com/staff','https://www.elcidspain.com/?token=secret','https://preview.vercel.app/']){
  const b=browser(url,'G-ELCIDTEST',true);assert.equal(b.scripts.length,0);assert.equal(b.nodes.length,1);
 }
});
test('booking click records intent, not purchase; withdrawal reloads',()=>{
 const b=browser('https://www.elcidspain.com/','G-ELCIDTEST',true);
 b.docEvents.click({target:{closest(sel){return sel==='a[href]'?{href:'https://beds24.com/booking2.php?propid=1'}:null}}});
 assert.ok(b.events().some(e=>e[0]==='event'&&e[1]==='booking_checkout_click'));
 assert.ok(!b.events().some(e=>e[1]==='purchase'));
 b.choose('Reject');assert.equal(b.reloads(),1);
});
