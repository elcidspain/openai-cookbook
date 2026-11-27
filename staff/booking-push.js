/* Booking notifications: explicit permission, authenticated device, no guest PII. */
(()=>{
  "use strict";
  const endpoint="https://cguutkghsnhmwzghkmnc.supabase.co/functions/v1/aumara-staff-booking-push";
  const pref="aumara.staff.booking-push.enabled.v1";
  let reg=null, snapshot=null, sub=null, busy=false, refreshing=false, renewed=0, generation=0, readyTask=null;
  const $p=id=>document.getElementById(id);
  const supported=()=>("serviceWorker" in navigator)&&("PushManager" in window)&&("Notification" in window);
  const signedIn=()=>!!state.user&&!$p("app").classList.contains("hidden");
  const setStatus=s=>{$p("bookingPushStatus").textContent=s};
  function render(rows){
    const list=$p("bookingPushList");list.replaceChildren();
    if(!rows.length){const p=document.createElement("p");p.className="muted small";p.textContent="Новых событий после подключения пока нет.";list.append(p);return}
    for(const row of rows){
      const card=document.createElement("div");card.className="panel";card.style.marginTop="8px";
      const title=document.createElement("strong");title.textContent=row.room+" · "+row.guests+" гост.";
      const dates=document.createElement("div");dates.className="small";dates.textContent=row.arrival+" — "+row.departure;
      const meta=document.createElement("div");meta.className="muted small";meta.textContent="Beds24 #"+row.id+" · "+new Date(row.bookedAt).toLocaleString("ru-RU",{timeZone:"Europe/Madrid"});
      card.append(title,dates,meta);list.append(card);
    }
  }
  async function call(op,extra={},credentials=null){
    if(!credentials&&(!signedIn()||!navigator.onLine||!(await ensureToken())))throw Error("Войдите в Staff и подключите интернет.");
    const c=credentials||{token:state.token,deviceId:get(LS.device)};
    if(!c.token||!c.deviceId)throw Error("Требуется активное устройство Staff.");
    const r=await fetch(endpoint,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({op,...extra,...c}),signal:AbortSignal.timeout(22000),keepalive:op==="unsubscribe"});
    const j=await r.json().catch(()=>({}));if(!r.ok||!j.ok)throw Error(j.error||"HTTP "+r.status);return j;
  }
  function updateButtons(){
    const available=supported()&&!!reg&&!!snapshot?.publicKey&&signedIn()&&navigator.onLine;
    $p("bookingPushEnable").disabled=busy||!available||NotificationSafe()==="denied"||!!(sub&&snapshot?.subscribed);
    $p("bookingPushDisable").disabled=busy||(!sub&&!snapshot?.subscribed);
    $p("bookingPushTest").disabled=busy||!available||!sub||!snapshot?.subscribed;
  }
  function NotificationSafe(){return "Notification" in window?Notification.permission:"unsupported"}
  function decode(s){return Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(s.length/4)*4,"=")),c=>c.charCodeAt(0))}
  function sameKey(s,key){
    const a=s?.options?.applicationServerKey;if(!a)return false;
    const x=new Uint8Array(a),y=decode(key);return x.length===y.length&&x.every((v,i)=>v===y[i]);
  }
  async function getRegistration(){
    if(!supported())return null;
    if(!readyTask)readyTask=navigator.serviceWorker.ready;
    return Promise.race([readyTask,new Promise(resolve=>setTimeout(()=>resolve(null),5000))]);
  }
  function describe(){
    if(!supported()){setStatus("На iPhone добавьте Staff на экран «Домой» и откройте его оттуда. На Android или компьютере используйте браузер с Web Push.");return}
    if(NotificationSafe()==="denied"){setStatus("Разрешите уведомления в настройках браузера или телефона.");return}
    if(sub&&snapshot?.subscribed){setStatus("Push включён на этом устройстве.");return}
    setStatus(snapshot?"Включите уведомления о новых бронированиях.":"Проверяем подключение…");
  }
  async function refresh(){
    if(refreshing||busy)return;
    if(!signedIn()){snapshot=null;sub=null;renewed=0;render([]);updateButtons();return}
    const g=generation;
    if(!navigator.onLine){setStatus("Нет сети. События обновятся при подключении.");return}
    refreshing=true;
    try{
      const data=await call("status");if(g!==generation||!signedIn())return;
      snapshot=data;
      reg=await getRegistration();if(g!==generation||!signedIn())return;
      sub=reg?await reg.pushManager.getSubscription():null;if(g!==generation||!signedIn())return;
      if(sub&&(snapshot.subscribed||get(pref)===true)&&NotificationSafe()==="granted"&&sameKey(sub,snapshot.publicKey)&&Date.now()-renewed>3600000){
        snapshot=await call("subscribe",{subscription:sub.toJSON()});renewed=Date.now();
      }else if(snapshot.subscribed&&(!sub||NotificationSafe()!=="granted"||!sameKey(sub,snapshot.publicKey))){
        snapshot=await call("unsubscribe");
      }
      if(g!==generation||!signedIn())return;
      render(snapshot.events||[]);describe();
    }catch(e){if(g===generation&&signedIn())setStatus("Push: "+e.message)}
    finally{refreshing=false;updateButtons()}
  }
  async function enable(){
    if(busy||!reg||!snapshot?.publicKey||!signedIn())return;
    busy=true;updateButtons();const g=generation;
    try{
      const permission=NotificationSafe()==="granted"?"granted":await Notification.requestPermission();
      if(permission!=="granted")throw Error("Разрешение не предоставлено.");
      if(g!==generation||!signedIn())return;
      let current=sub;
      if(current&&!sameKey(current,snapshot.publicKey)){await current.unsubscribe();current=null}
      current=current||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decode(snapshot.publicKey)});
      if(g!==generation||!signedIn()){await current.unsubscribe();return}
      sub=current;snapshot=await call("subscribe",{subscription:sub.toJSON()});renewed=Date.now();
      if(g!==generation||!signedIn()){await current.unsubscribe();return}
      put(pref,true);render(snapshot.events||[]);describe();
    }catch(e){if(g===generation&&signedIn())setStatus("Push: "+e.message)}
    finally{busy=false;updateButtons()}
  }
  async function disable(){
    if(busy)return;busy=true;updateButtons();
    try{
      snapshot=await call("unsubscribe");
      if(sub)await sub.unsubscribe();
      sub=null;renewed=0;del(pref);describe();
    }catch(e){setStatus("Push: "+e.message)}
    finally{busy=false;updateButtons()}
  }
  async function test(){
    if(busy)return;busy=true;updateButtons();
    try{const j=await call("test");setStatus(j.acceptedByProvider?"Тест передан push-сервису. Проверьте уведомление на телефоне.":"Тест не подтверждён.")}
    catch(e){setStatus("Тест: "+e.message)}
    finally{busy=false;updateButtons()}
  }
  // Existing staff logout remains synchronous; do not keep the credential after this request.
  window.aumaraBookingPushLogout=(token,deviceId)=>{
    generation++;const old=sub;sub=null;snapshot=null;renewed=0;del(pref);
    if($p("bookingPushList"))render([]);
    if(token&&deviceId&&navigator.onLine)call("unsubscribe",{},{token,deviceId}).catch(()=>{});
    if(old)old.unsubscribe().catch(()=>{});
    else if(reg)reg.pushManager.getSubscription().then(s=>s?.unsubscribe()).catch(()=>{});
  };
  function openFeed(){
    if(!signedIn())return;
    showTab("home");$p("bookingPushPanel").scrollIntoView({block:"start"});refresh();
  }
  document.addEventListener("DOMContentLoaded",()=>{
    if(!$p("bookingPushPanel"))return;
    $p("bookingPushEnable").addEventListener("click",enable);
    $p("bookingPushDisable").addEventListener("click",disable);
    $p("bookingPushTest").addEventListener("click",test);
    $p("bookingPushRefresh").addEventListener("click",refresh);
    if("serviceWorker" in navigator)navigator.serviceWorker.addEventListener("message",e=>{
      if(e.data?.type==="AUMARA_BOOKING_PUSH")refresh();
      if(e.data?.type==="AUMARA_BOOKING_OPEN")openFeed();
    });
    window.addEventListener("online",refresh);
    document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh()});
    const observer=new MutationObserver(()=>{if(signedIn())refresh();else{generation++;snapshot=null;sub=null;render([]);updateButtons()}});
    observer.observe($p("app"),{attributes:true,attributeFilter:["class"]});
    setInterval(()=>{if(!document.hidden)refresh()},120000);
    if(location.hash==="#bookings")setTimeout(openFeed,1200);
    setTimeout(refresh,1000);
  });
})();
