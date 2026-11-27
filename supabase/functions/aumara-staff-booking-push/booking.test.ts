import assert from "node:assert/strict";
import {test} from "node:test";
import {bookingEvent,pushEndpoint,pushPayload} from "./booking.ts";
const now=Date.parse("2026-11-27T15:00:00Z");
const start=Date.parse("2026-11-27T12:00:00Z");
const fixture={id:12345,propertyId:324882,roomId:674465,arrival:"2026-11-28",departure:"2026-11-29",status:"confirmed",bookingTime:"2026-11-27T14:00:00Z",numAdult:2,numChild:0,guestFirstName:"synthetic",guestEmail:"example@example.invalid",price:149};
test("new real booking maps only operational fields",()=>{
  const e=bookingEvent({booking:fixture},start,now);
  assert.ok(e);assert.equal(e.booking_id,12345);assert.equal(e.guests,2);
  assert.equal(e.room_id,674465);assert.equal(e.arrival,"2026-11-28");
  assert.ok(!JSON.stringify(e).includes("synthetic"));assert.ok(!JSON.stringify(e).includes("example.invalid"));
  const payload=pushPayload(e);
  assert.equal(payload.tag,"aumara-booking-12345");assert.ok(payload.body.includes("Chalet"));
});
test("old, cancelled, inquiry, wrong property and unrecognized room do not trigger",()=>{
  for(const patch of [{bookingTime:"2026-11-27T11:00:00Z"},{status:"cancelled"},{status:"inquiry"},{propertyId:324903},{roomId:999}]){
    assert.equal(bookingEvent({booking:{...fixture,...patch}},start,now),null);
  }
});
test("new status and numeric strings accepted",()=>{
  const e=bookingEvent({booking:{...fixture,status:"new",id:"12345",numAdult:"2",numChild:"1"}},start,now);
  assert.equal(e?.guests,3);
});
test("invalid booking fields fail closed",()=>{
  for(const patch of [{arrival:"2026-02-31"},{departure:"2026-11-27"},{numAdult:0},{numAdult:25},{id:0},{bookingTime:"2026-11-27T14:00:00"},{bookingTime:"2026-11-28T14:00:00Z"}]){
    assert.throws(()=>bookingEvent({booking:{...fixture,...patch}},start,now));
  }
  assert.throws(()=>bookingEvent({},start,now));
  assert.throws(()=>bookingEvent({booking:fixture},NaN,now));
});
test("official HTTPS push providers only",()=>{
  for(const endpoint of ["https://fcm.googleapis.com/fcm/send/abc","https://updates.push.services.mozilla.com/wpush/v2/abc","https://web.push.apple.com/abc"]){
    assert.equal(pushEndpoint(endpoint),endpoint);
  }
  for(const endpoint of ["http://fcm.googleapis.com/a","https://127.0.0.1/a","https://fcm.googleapis.com.evil.example/a","https://evil.example/a","https://user@web.push.apple.com/a","https://web.push.apple.com:444/a","https://web.push.apple.com/a#secret"]){
    assert.throws(()=>pushEndpoint(endpoint));
  }
});
