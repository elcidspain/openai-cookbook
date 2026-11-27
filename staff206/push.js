(()=>{
"use strict";
const API="https://cguutkghsnhmwzghkmnc.supabase.co/functions/v1/aumara-staff-api";
const PUSH="https://cguutkghsnhmwzghkmnc.supabase.co/functions/v1/aumara-staff-booking-push";
const KEY="aumara.staff206.push.device.v1";
const $=id=>document.getElementById(id);
let session=null,token="",reg=null,snapshot=null,sub=null,busy=false;
const supported=()=>("serviceWorker" in navigator)&&("PushManager" in window)&&("Notification" in window);
const standalone=()=>matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;
const ios=()=>/iPhone|iPad|iPod/.test(navigator.userAgent);
const status=s=>{$("status").textContent=s};
function load(){try{return JSON.parse(localStorage.getItem(KEY)||"null")}catch{return null}}
function save(v){if(v)localStorage.setItem(KEY,JSON.stringify(v));else localStorage.removeItem(KEY)}
function context(){return {userAgent:navigator.userAgent,platform:navigator.platform||"",language:navigator.language||"",timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone,standalone:standalone(),origin:location.origin,source:"STAFF206_PUSH"}}
async function request(url,body){const r=await fetch(url,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body),cache:"no-store",signal:AbortSignal.timeout(25000)});const j=await r.json().catch(()=>({}));if(!r.ok||!j.ok)throw Error(j.error||"HTTP "+r.status);return j}
async function rpc(fn,args=[]){return (await request(API,{fn,args})).result}
async function push(op,extra={}){if(!session||!token)throw Error("Войдите в Staff.");return request(PUSH,{op,token,deviceId:session.deviceId,...extra})}
function controls(){
  const signed=!!session&&!!token;
  $("login").classList.toggle("hidden",signed);$("actions").classList.toggle("hidden",!signed);
  $("loginButton").disabled=busy||(ios()&&!standalone());
  $("enable").disabled=busy||!signed||!supported()||!reg||!snapshot?.publicKey||Notification.permission==="denied"||!!(sub&&snapshot.subscribed);
  $("test").disabled=busy||!signed||!sub||!snapshot?.subscribed;
  $("disable").disabled=busy||!signed||(!sub&&!snapshot?.subscribed);
  $("logout").disabled=busy;
  $("user").textContent=signed?(session.name||"Staff"):"";
}
function decode(s){return Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(s.length/4)*4,"=")),c=>c.charCodeAt(0))}
async function update(){
  snapshot=await push("status");
  sub=reg?await reg.pushManager.getSubscription():null;
  if(sub&&snapshot.subscribed&&Notification.permission==="granted"){snapshot=await push("subscribe",{subscription:sub.toJSON()});status("Push включён на этом устройстве.");}
  else if(!supported())status("Установите приложение на экран «Домой», затем откройте его.");
  else if(Notification.permission==="denied")status("Разрешите уведомления в настройках устройства.");
  else status("Нажмите «Включить push».");
}
async function resume(){
  session=load();if(!session?.deviceId||!session?.refresh){session=null;return false}
  const r=await rpc("resumeDeviceSession",[session.deviceId,session.refresh,context()]);
  token=r.token;if(!token)throw Error("Сессия не восстановлена.");
  session.name=r.user?.name||session.name;save(session);return true;
}
async function login(e){
  e.preventDefault();if(busy)return;busy=true;controls();
  try{
    const id=$("staff").value,pin=$("pin").value;
    if(!id||!/^[0-9]{6}$/.test(pin))throw Error("Введите PIN Staff.");
    const deviceId=crypto.randomUUID();
    const r=await rpc("loginDevice",[id,pin,{deviceId,label:"AUMARA Staff 2.0.6 Push"},context()]);
    $("pin").value="";
    if(!r.token||!r.refreshToken||!r.deviceId)throw Error("Устройство не подтверждено.");
    token=r.token;session={deviceId:r.deviceId,refresh:r.refreshToken,name:r.user?.name||"Staff"};save(session);
    await update();
  }catch(e){status(e.message)}
  finally{busy=false;controls()}
}
async function enable(){
  if(busy||!reg||!snapshot?.publicKey)return;busy=true;controls();
  try{
    const p=await Notification.requestPermission();
    if(p!=="granted")throw Error("Разрешение не предоставлено.");
    sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decode(snapshot.publicKey)});
    snapshot=await push("subscribe",{subscription:sub.toJSON()});
    status(snapshot.subscribed?"Push включён. Нажмите «Проверить push».":"Подписка не подтверждена.");
  }catch(e){status(e.message)}finally{busy=false;controls()}
}
async function test(){if(busy)return;busy=true;controls();try{const r=await push("test");status(r.acceptedByProvider?"Тест передан push-сервису. Проверьте уведомление.":"Тест не подтверждён.")}catch(e){status(e.message)}finally{busy=false;controls()}}
async function disable(){if(busy)return;busy=true;controls();try{snapshot=await push("unsubscribe");if(sub)await sub.unsubscribe();sub=null;status("Push выключен.")}catch(e){status(e.message)}finally{busy=false;controls()}}
async function logout(){
 if(busy)return;busy=true;controls();
 try{if(token){await push("unsubscribe");await rpc("revokeCurrentDevice",[token,context()])}if(sub)await sub.unsubscribe();save(null);token="";session=null;snapshot=null;sub=null;status("Устройство отключено.");}
 catch(e){status(e.message)}finally{busy=false;controls()}
}
$("login").addEventListener("submit",login);$("enable").onclick=enable;$("test").onclick=test;$("disable").onclick=disable;$("logout").onclick=logout;
function focusStaff(){ $("openStaff").focus();$("openStaff").scrollIntoView({block:"start"});status("Новая бронь — откройте Staff 2.0.6, раздел «Заезды».");}
if("serviceWorker" in navigator)navigator.serviceWorker.addEventListener("message",e=>{if(e.data?.type==="AUMARA_OPEN_STAFF")focusStaff()});
(async()=>{
 $("install").classList.toggle("hidden",!ios()||standalone());
 try{
   if(supported()){await navigator.serviceWorker.register("/staff206/sw.js",{scope:"/staff206/"});reg=await navigator.serviceWorker.ready}
   const r=await rpc("getLoginOptions");if(r.version!=="2.0.6")throw Error("Версия Staff изменилась: "+r.version);
   $("staff").replaceChildren(new Option("Выберите сотрудника",""));
   for(const u of r.users||[])$("staff").append(new Option(u.name,u.staffId));
   if(await resume())await update();else status("Подключите устройство своим PIN Staff.");
   if(new URLSearchParams(location.search).has("open"))focusStaff();
 }catch(e){status(e.message)}finally{controls()}
})();
document.addEventListener("visibilitychange",async()=>{if(!document.hidden&&!busy&&session&&token){try{await resume();await update()}catch(e){status(e.message)}finally{controls()}}});
})();