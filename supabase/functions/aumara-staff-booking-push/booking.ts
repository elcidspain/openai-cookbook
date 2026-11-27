// Beds24 v2 booking webhook; deliberately retain no guest identity or payment data.
export const PROPERTY = 324882;
export const ROOMS: Record<number,string> = {674465:"Chalet",674466:"Superior Chalet"};
export type BookingEvent = {booking_id:number; property_id:number; room_id:number; arrival:string; departure:string; guests:number; booked_at:string; status:string};
const date = (x:unknown): x is string => typeof x==="string" && /^\d{4}-\d{2}-\d{2}$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0,10)===x;
function integer(x:unknown):number { return typeof x==="number"&&Number.isSafeInteger(x)?x:typeof x==="string"&&/^\d+$/.test(x)&&Number.isSafeInteger(Number(x))?Number(x):NaN; }
export function bookingEvent(payload:unknown, start:number, now=Date.now()):BookingEvent|null {
  if(!Number.isFinite(start)||start>now)throw new Error("Invalid activation time");
  const b=(payload as {booking?:Record<string,unknown>})?.booking;
  if(!b||typeof b!=="object"||Array.isArray(b))throw new Error("Invalid webhook");
  const property=integer(b.propertyId), room=integer(b.roomId), id=integer(b.id);
  if(property!==PROPERTY || !Object.hasOwn(ROOMS,room))return null;
  const status=String(b.status??"").toLowerCase();
  if(!["new","confirmed"].includes(status))return null;
  if(!(id>0)||!date(b.arrival)||!date(b.departure)||b.departure<=b.arrival)throw new Error("Invalid booking dates or id");
  if(typeof b.bookingTime!=="string"||!/(?:Z|[+-]\d\d:\d\d)$/.test(b.bookingTime))throw new Error("Missing booking time zone");
  const created=Date.parse(b.bookingTime);
  if(!Number.isFinite(created)||created>now+5*60_000)throw new Error("Invalid booking time");
  if(created<start)return null;
  if(Date.parse(b.departure+"T23:59:59Z")<now)return null;
  const adults=integer(b.numAdult), children=integer(b.numChild??0);
  if(!(adults>=0&&children>=0&&adults+children>=1&&adults+children<=24))throw new Error("Invalid guest count");
  return {booking_id:id,property_id:property,room_id:room,arrival:b.arrival,departure:b.departure,guests:adults+children,booked_at:new Date(created).toISOString(),status};
}
export function pushEndpoint(raw:unknown):string {
  if(typeof raw!=="string"||raw.length>2048)throw new Error("Invalid push endpoint");
  const u=new URL(raw),host=u.hostname.toLowerCase();
  const allowed=host==="fcm.googleapis.com"||host==="android.googleapis.com"||host==="updates.push.services.mozilla.com"||host==="web.push.apple.com"||host.endsWith(".push.apple.com")||host.endsWith(".notify.windows.com")||host.endsWith(".push.services.mozilla.com");
  if(u.protocol!=="https:"||u.port||u.username||u.password||u.hash||!allowed)throw new Error("Unsupported push endpoint");
  return u.href;
}
export function pushPayload(b:BookingEvent) {
  return {kind:"booking",id:b.booking_id,title:"AUMARA · Новая бронь",body:`${ROOMS[b.room_id]} · ${b.arrival} — ${b.departure} · ${b.guests} гост.`,tag:`aumara-booking-${b.booking_id}`};
}
