import webpush from "npm:web-push@3.6.7";
import {bookingEvent,pushEndpoint,pushPayload,ROOMS,type BookingEvent} from "./booking.ts";

const URL_BASE=Deno.env.get("SUPABASE_URL")??"";
const SERVICE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
const ORIGINS=new Set(["https://elcidspain.com","https://www.elcidspain.com"]);
const CONFIG="aumara_staff_push_config", DEVICES="aumara_staff_push_devices", EVENTS="aumara_staff_booking_events", OUTBOX="aumara_staff_push_outbox";
type Config={vapid_public:string;vapid_private:string;webhook_secret:string;active_from:string};
type Device={device_id:string;endpoint:string;p256dh:string;auth:string;lease_until:string;last_test_at?:string};
type Delivery=Device & {booking_id:number;attempts:number};
class HttpError extends Error{constructor(public status:number,message:string){super(message)}}
const query=(p:Record<string,string>)=>new URLSearchParams(p).toString();
async function db<T>(table:string,params:Record<string,string>={},method="GET",body?:unknown,prefer=""):Promise<T>{
  if(!URL_BASE||!SERVICE)throw new HttpError(503,"Storage unavailable");
  const res=await fetch(URL_BASE+"/rest/v1/"+table+"?"+query(params),{
    method,headers:{apikey:SERVICE,authorization:"Bearer "+SERVICE,"content-type":"application/json",...(prefer?{prefer}:{})},
    ...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(10000)
  });
  if(!res.ok)throw new HttpError(503,"Storage operation failed");
  const raw=await res.text();return (raw?JSON.parse(raw):null) as T;
}
async function config(create:boolean):Promise<Config|null>{
  let rows=await db<Config[]>(CONFIG,{id:"eq.1",limit:"1"});
  if(!rows.length&&create){
    const keys=webpush.generateVAPIDKeys();
    await db(CONFIG,{on_conflict:"id"},"POST",{id:1,vapid_public:keys.publicKey,vapid_private:keys.privateKey,webhook_secret:crypto.randomUUID()+crypto.randomUUID()},"resolution=ignore-duplicates,return=minimal");
    rows=await db<Config[]>(CONFIG,{id:"eq.1",limit:"1"});
  }
  return rows[0]??null;
}
async function authenticate(b:Record<string,unknown>):Promise<{deviceId:string;lease:string}>{
  const token=b.token, deviceId=b.deviceId;
  if(typeof token!=="string"||!token||token.length>8192||typeof deviceId!=="string"||!/^[A-Za-z0-9._:-]{1,160}$/.test(deviceId))throw new HttpError(401,"Staff login required");
  const r=await fetch(URL_BASE+"/functions/v1/aumara-staff-api",{
    method:"POST",headers:{"content-type":"application/json",origin:"https://elcidspain.com"},
    body:JSON.stringify({fn:"listMyDevices",args:[token]}),signal:AbortSignal.timeout(12000)
  });
  if(!r.ok)throw new HttpError(401,"Staff device not authorized");
  const j=await r.json();
  if(j.ok!==true||!Array.isArray(j.result))throw new HttpError(401,"Staff device not authorized");
  const d=j.result.find((x:Record<string,unknown>)=>x.deviceId===deviceId);
  const expiry=typeof d?.expiresAt==="string"?Date.parse(d.expiresAt):NaN;
  if(!Number.isFinite(expiry)||expiry<=Date.now())throw new HttpError(401,"Staff device expired");
  return {deviceId,lease:new Date(Math.min(expiry,Date.now()+7*86400000)).toISOString()};
}
function safeEqual(a:string,b:string):boolean{
  const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b);
  let result=x.length^y.length;for(let i=0;i<y.length;i++)result|=(x[i]??0)^y[i];return result===0;
}
function key(raw:unknown,n:number):string{
  if(typeof raw!=="string"||raw.length!==n||!/^[A-Za-z0-9_-]+$/.test(raw))throw new HttpError(400,"Invalid subscription key");
  return raw;
}
async function readJson(req:Request):Promise<Record<string,unknown>>{
  if(Number(req.headers.get("content-length")||0)>1048576)throw new HttpError(413,"Request too large");
  const raw=await req.text();if(raw.length>1048576)throw new HttpError(413,"Request too large");
  try{const b=JSON.parse(raw);if(!b||typeof b!=="object"||Array.isArray(b))throw Error();return b}catch{throw new HttpError(400,"Invalid JSON")}
}
async function send(c:Config,d:Device,payload:unknown,topic?:string){
  await webpush.sendNotification({endpoint:pushEndpoint(d.endpoint),keys:{p256dh:d.p256dh,auth:d.auth}},JSON.stringify(payload),{
    vapidDetails:{subject:"mailto:elcidspain@gmail.com",publicKey:c.vapid_public,privateKey:c.vapid_private},TTL:1800,urgency:"high",timeout:10000,...(topic?{topic}:{})
  });
}
function pushCode(e:unknown):number{return Number((e as {statusCode?:number})?.statusCode)||0}
async function dispatch(c:Config,event:BookingEvent):Promise<boolean>{
  // Each recipient gets a durable, leased outbox row. A failed webhook is retried by Beds24.
  const lease=crypto.randomUUID();
  const claimed=await db<Delivery[]>("rpc/aumara_staff_push_claim",{},"POST",{p_booking:event.booking_id,p_lease:lease});
  await Promise.all(claimed.map(async d=>{
    const f={booking_id:"eq."+d.booking_id,device_id:"eq."+d.device_id,lease_id:"eq."+lease};
    try{
      await send(c,d,pushPayload(event),"booking-"+event.booking_id);
      await db(OUTBOX,f,"PATCH",{state:"sent",sent_at:new Date().toISOString(),lease_id:null,lease_until:null});
    }catch(e){
      const code=pushCode(e);
      if(code===404||code===410){
        // Guard endpoint so a freshly renewed subscription is not removed by an old delivery.
        await db(DEVICES,{device_id:"eq."+d.device_id,endpoint:"eq."+d.endpoint},"DELETE");
      }
      const retry=code===0||code===429||code>=500;
      await db(OUTBOX,f,"PATCH",{state:retry&&d.attempts<6?"pending":"failed",next_attempt_at:new Date(Date.now()+30000*Math.min(d.attempts,6)).toISOString(),lease_id:null,lease_until:null});
    }
  }));
  // Expired devices and exhausted leases should not keep the upstream webhook retrying indefinitely.
  await db(DEVICES,{lease_until:"lte."+new Date().toISOString()},"DELETE");
  await db(OUTBOX,{booking_id:"eq."+event.booking_id,state:"eq.sending",attempts:"gte.6",lease_until:"lte."+new Date().toISOString()},"PATCH",{state:"failed",lease_id:null,lease_until:null});
  const pending=await db<unknown[]>(OUTBOX,{booking_id:"eq."+event.booking_id,state:"in.(pending,sending)",select:"booking_id",limit:"1"});
  return pending.length===0;
}
function response(req:Request,status:number,value:unknown){
  const origin=req.headers.get("origin")||"";
  return new Response(JSON.stringify(value),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store",...(ORIGINS.has(origin)?{"access-control-allow-origin":origin,vary:"Origin","access-control-allow-methods":"POST, OPTIONS","access-control-allow-headers":"content-type"}:{})}});
}
Deno.serve(async req=>{
  try{
    if(req.method==="OPTIONS")return response(req,ORIGINS.has(req.headers.get("origin")||"")?200:403,{ok:true});
    if(req.method!=="POST")throw new HttpError(405,"POST required");
    if(new URL(req.url).pathname.endsWith("/webhook")){
      const c=await config(false);
      if(!c||!safeEqual(req.headers.get("x-aumara-webhook")||"",c.webhook_secret))throw new HttpError(401,"Unauthorized webhook");
      const b=await readJson(req);
      let event:BookingEvent|null;
      try{event=bookingEvent(b,Date.parse(c.active_from))}catch{throw new HttpError(400,"Invalid booking event")}
      if(!event)return response(req,200,{ok:true,ignored:true});
      const created=await db<boolean>("rpc/aumara_staff_push_ingest",{},"POST",{p_event:event});
      // Retry the stored event, not data from a later modification.
      const rows=await db<BookingEvent[]>(EVENTS,{booking_id:"eq."+event.booking_id,limit:"1"});
      if(!rows[0])throw new HttpError(503,"Event unavailable");
      const done=await dispatch(c,rows[0]);
      return response(req,done?200:503,{ok:done,created});
    }
    if(!ORIGINS.has(req.headers.get("origin")||""))throw new HttpError(403,"Staff origin required");
    const b=await readJson(req),op=b.op;
    if(!["status","subscribe","unsubscribe","test"].includes(String(op)))throw new HttpError(400,"Unknown operation");
    const {deviceId,lease}=await authenticate(b);
    const c=await config(true);if(!c)throw new HttpError(503,"Configuration unavailable");
    const f={device_id:"eq."+deviceId};
    if(op==="subscribe"){
      const sub=b.subscription as {endpoint?:unknown;keys?:{p256dh?:unknown;auth?:unknown}}|undefined;
      if(!sub?.keys)throw new HttpError(400,"Subscription required");
      let endpoint:string;try{endpoint=pushEndpoint(sub.endpoint)}catch{throw new HttpError(400,"Invalid push endpoint")}
      await db(DEVICES,{on_conflict:"device_id"},"POST",{device_id:deviceId,endpoint,p256dh:key(sub.keys.p256dh,87),auth:key(sub.keys.auth,22),lease_until:lease},"resolution=merge-duplicates,return=minimal");
    }else if(op==="unsubscribe"){
      await db(DEVICES,f,"DELETE");
    }else if(op==="test"){
      const d=(await db<Device[]>(DEVICES,{...f,lease_until:"gt."+new Date().toISOString(),limit:"1"}))[0];
      if(!d)throw new HttpError(409,"Enable notifications first");
      const cutoff=new Date(Date.now()-60000).toISOString();
      const lock=await db<Device[]>(DEVICES,{...f,or:"(last_test_at.is.null,last_test_at.lt."+cutoff+")"},"PATCH",{last_test_at:new Date().toISOString()},"return=representation");
      if(!lock.length)throw new HttpError(429,"Test cooldown");
      try{await send(c,d,{kind:"test",title:"AUMARA · Тест уведомлений",body:"Проверка доставки. Реальной брони нет.",tag:"aumara-test"});}
      catch(e){if([404,410].includes(pushCode(e)))await db(DEVICES,{...f,endpoint:"eq."+d.endpoint},"DELETE");throw new HttpError(502,"Push provider rejected the test")}
      return response(req,200,{ok:true,acceptedByProvider:true});
    }
    const subscribed=(await db<unknown[]>(DEVICES,{...f,lease_until:"gt."+new Date().toISOString(),select:"device_id",limit:"1"})).length>0;
    const events=await db<BookingEvent[]>(EVENTS,{select:"booking_id,room_id,arrival,departure,guests,booked_at",order:"booked_at.desc",limit:"40"});
    return response(req,200,{ok:true,publicKey:c.vapid_public,subscribed,events:events.map(e=>({id:e.booking_id,room:ROOMS[e.room_id],arrival:e.arrival,departure:e.departure,guests:e.guests,bookedAt:e.booked_at}))});
  }catch(e){return response(req,e instanceof HttpError?e.status:503,{ok:false,error:e instanceof HttpError?e.message:"Temporary service failure"})}
});
