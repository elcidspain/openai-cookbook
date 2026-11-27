/* AUMARA Staff 2.0.6: push only. No caches, no intercepted operational requests. */
self.addEventListener("install",e=>e.waitUntil(self.skipWaiting()));
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("push",e=>{
  let p;try{p=e.data?.json()}catch{return}
  if(!p||!["booking","test"].includes(p.kind))return;
  const booking=p.kind==="booking";
  if(booking&&(!Number.isSafeInteger(p.id)||p.id<=0))return;
  const tag=booking?"aumara-booking-"+p.id:"aumara-test";
  // Keep the lock screen free of contact details, guest names and payments.
  const body=booking?"Новая бронь. Откройте Staff → Заезды.":"Проверка уведомлений. Реальной брони нет.";
  e.waitUntil(self.registration.showNotification(booking?"AUMARA · Новая бронь":"AUMARA · Тест push",{body,tag,icon:"/staff206/icon.svg",data:{bookingId:booking?p.id:null}}));
});
self.addEventListener("notificationclick",e=>{
  if(!e.notification.tag?.startsWith("aumara-"))return;
  e.notification.close();
  e.waitUntil((async()=>{
    const target=new URL("/staff206/",self.location.origin).href;
    const windows=await self.clients.matchAll({type:"window",includeUncontrolled:true});
    const w=windows.find(c=>new URL(c.url).origin===self.location.origin&&new URL(c.url).pathname.startsWith("/staff206/"));
    if(w){await w.focus();w.postMessage({type:"AUMARA_OPEN_STAFF"});return}
    await self.clients.openWindow(target+"?open=arrivals");
  })());
});