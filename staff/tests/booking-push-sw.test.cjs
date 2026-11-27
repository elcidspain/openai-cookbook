const test=require("node:test");
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const path=require("node:path");
function worker(){
  const handlers={},notices=[],messages=[],opened=[];
  const client={url:"https://elcidspain.com/staff/",focus:async()=>{},postMessage:m=>messages.push(m.type)};
  const self={location:{origin:"https://elcidspain.com"},addEventListener:(n,f)=>{handlers[n]=f},registration:{showNotification:async(title,opts)=>{notices.push({title,opts})}},clients:{matchAll:async()=>[client],openWindow:async url=>opened.push(url)}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"..","sw.js"),"utf8"),{self,URL,Number,console});
  async function push(p){let work;handlers.push({data:{json:()=>p},waitUntil:v=>work=v});await work}
  async function click(tag){let work;handlers.notificationclick({notification:{tag,close(){}},waitUntil:v=>work=v});await work}
  return {push,click,notices,messages,opened};
}
test("a booking push is a native notification with a stable tag and opens Staff",async()=>{
  const w=worker();await w.push({kind:"booking",id:123,body:"Chalet · 2026-11-28 — 2026-11-29 · 2 гост.",title:"ignored",url:"https://evil.invalid"});
  assert.equal(w.notices.length,1);assert.equal(w.notices[0].title,"AUMARA · Новая бронь");
  assert.equal(w.notices[0].opts.tag,"aumara-booking-123");
  assert.equal(w.notices[0].opts.data.bookingId,123);
  await w.click("aumara-booking-123");assert.ok(w.messages.includes("AUMARA_BOOKING_OPEN"));assert.equal(w.opened.length,0);
});
test("test push never represents a booking; malformed events ignored",async()=>{
  const w=worker();await w.push({kind:"test",body:"fake booking"});assert.equal(w.notices[0].opts.data.bookingId,null);
  assert.match(w.notices[0].opts.body,/Реальной брони нет/);
  await w.push({kind:"booking",id:0,body:"bad"});await w.push({kind:"other",body:"bad"});
  assert.equal(w.notices.length,1);
});
