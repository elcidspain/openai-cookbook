const CACHE='aumara-staff-pwa-v2.3.1-booking-push3';
const SHELL=['/staff/','/staff/index.html','/staff/styles.css?v=231','/staff/app.js?v=233','/staff/bootfix231.js?v=231','/staff/patch.js?v=231','/staff/legacy.js?v=231','/staff/planner23-guard.js?v=232','/staff/planner23.js?v=232','/staff/planner23-unguard.js?v=232','/staff/booking-push.js?v=233','/staff/manifest.webmanifest','/staff/icon.svg'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('aumara-staff-pwa-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET') return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin) return;
  if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request,{cache:'no-store'}).then(response=>{
      if(response&&response.ok){const copy=response.clone();caches.open(CACHE).then(c=>c.put('/staff/',copy))}
      return response;
    }).catch(()=>caches.match('/staff/')));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached=>{
    const fresh=fetch(event.request).then(response=>{if(response&&response.ok){const copy=response.clone();caches.open(CACHE).then(c=>c.put(event.request,copy))}return response}).catch(()=>cached);
    return cached||fresh;
  }));
});
self.addEventListener('message',event=>{if(event.data==='SKIP_WAITING')self.skipWaiting()});

self.addEventListener('push',event=>{
  let p;try{p=event.data?.json()}catch{return}
  if(!p||!['booking','test'].includes(p.kind)||typeof p.body!=='string'||p.body.length>200)return;
  const booking=p.kind==='booking';
  if(booking&&(!Number.isSafeInteger(p.id)||p.id<=0))return;
  const title=booking?'AUMARA · Новая бронь':'AUMARA · Тест уведомлений';
  const tag=booking?'aumara-booking-'+p.id:'aumara-test';
  const body=booking?p.body:'Проверка доставки. Реальной брони нет.';
  event.waitUntil((async()=>{
    await self.registration.showNotification(title,{body,tag,data:{bookingId:booking?p.id:null},icon:'/staff/icon.svg'});
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows)client.postMessage({type:'AUMARA_BOOKING_PUSH'});
  })());
});
self.addEventListener('notificationclick',event=>{
  if(!event.notification.tag?.startsWith('aumara-booking-')&&event.notification.tag!=='aumara-test')return;
  event.notification.close();
  event.waitUntil((async()=>{
    const target=new URL('/staff/#bookings',self.location.origin).href;
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    const client=windows.find(c=>new URL(c.url).origin===self.location.origin&&new URL(c.url).pathname.startsWith('/staff/'));
    if(client){await client.focus();client.postMessage({type:'AUMARA_BOOKING_OPEN'});return}
    await self.clients.openWindow(target);
  })());
});
