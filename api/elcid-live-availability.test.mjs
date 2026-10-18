import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Import the Vercel ESM handler independently of the repository's module mode.
const source = readFileSync(new URL("./elcid-live-availability.js", import.meta.url), "utf8");
const { quoteElCidAvailability } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);

test("quoted party is preserved in both room checkout and all-rooms checkout", async (t) => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "https://api.beds24.com/json/getAvailabilities");
    const payload = JSON.parse(options.body);
    assert.equal(payload.propId, "324903");
    assert.equal(payload.numAdult, "3");
    assert.equal(payload.numChild, "1");
    return new Response(JSON.stringify({
      "674484": { roomsavail: 1, price: 264, currency: "EUR" },
      "674485": { roomsavail: 0, price: 176, currency: "EUR" },
      "674486": { roomsavail: 1, price: null, currency: "EUR" },
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const result = await quoteElCidAvailability({
    checkIn: "2026-10-23", checkOut: "2026-10-25", adults: "3", children: "1",
  });
  assert.equal(result.adults, 3);
  assert.equal(result.children, 1);
  assert.equal(result.reservationCreated, false);
  assert.equal(result.paymentCollected, false);
  const triple = result.inventory.find((x) => x.roomId === "674484");
  assert.equal(triple.bookable, true);
  const link = new URL(triple.checkoutUrl);
  assert.equal(link.protocol, "https:");
  assert.equal(link.hostname, "beds24.com");
  assert.equal(link.pathname, "/booking2.php");
  assert.equal(link.searchParams.get("propid"), "324903");
  assert.equal(link.searchParams.get("roomid"), "674484");
  assert.equal(link.searchParams.get("checkin"), "2026-10-23");
  assert.equal(link.searchParams.get("checkout"), "2026-10-25");
  assert.equal(link.searchParams.get("numadult"), "3");
  assert.equal(link.searchParams.get("numchild"), "1");
  assert.equal(link.searchParams.get("br1-674484"), "Book");
  const all = new URL(result.allAvailabilityUrl);
  assert.equal(all.searchParams.get("numadult"), "3");
  assert.equal(all.searchParams.get("numchild"), "1");
  assert.equal(all.searchParams.get("roomid"), null);
  assert.ok(![...all.searchParams.keys()].some(key => /^br\d+-/.test(key)));
  for (const roomId of ["674485", "674486"]) {
    const room = result.inventory.find((x) => x.roomId === roomId);
    assert.equal(room.bookable, false);
    assert.equal(room.checkoutUrl, null);
  }
});

test("default party is 2 adults and 0 children in checkout links", async (t) => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    "674484": { roomsavail: 1, price: 176, currency: "EUR" },
  }), { status: 200 });
  t.after(() => { globalThis.fetch = originalFetch; });
  const result = await quoteElCidAvailability({
    checkIn: "2026-10-23", checkOut: "2026-10-24",
  });
  const url = new URL(result.inventory[0].checkoutUrl);
  assert.equal(url.searchParams.get("numadult"), "2");
  assert.equal(url.searchParams.get("numchild"), "0");
  assert.equal(url.searchParams.get("br1-674484"), "Book");
  assert.equal(new URL(result.allAvailabilityUrl).searchParams.get("numadult"), "2");
});

test("invalid party is rejected before querying Beds24", async (t) => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw Error("Unexpected external request"); };
  t.after(() => { globalThis.fetch = originalFetch; });
  await assert.rejects(
    quoteElCidAvailability({
      checkIn: "2026-10-23", checkOut: "2026-10-24", adults: "0", children: "0",
    }),
    /adults must be an integer/
  );
});

test("each priced room selects only its configured public offer", async (t) => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(Object.fromEntries(
    ["674484", "674485", "674486"].map(roomId => [roomId, { roomsavail: 1, price: 123, currency: "EUR" }])
  )), { status: 200 });
  t.after(() => { globalThis.fetch = originalFetch; });
  const result = await quoteElCidAvailability({ checkIn: "2026-10-23", checkOut: "2026-10-24", adults: "2", children: "0" });
  for (const room of result.inventory) {
    const url = new URL(room.checkoutUrl);
    const selectors = [...url.searchParams.keys()].filter(key => /^br\d+-/.test(key));
    assert.deepEqual(selectors, [`br1-${room.roomId}`]);
    assert.equal(url.searchParams.get(selectors[0]), "Book");
    assert.equal(url.searchParams.get("roomid"), room.roomId);
    assert.equal(url.searchParams.get("numadult"), "2");
  }
});
