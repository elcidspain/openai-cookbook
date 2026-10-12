const PROPERTY_ID = "324903";
const API_URL = "https://api.beds24.com/json/getAvailabilities";
const ROOMS = [
  ["674484", "Triple Room"],
  ["674485", "Twin Room with Terrace"],
  ["674486", "Studio"],
];

function isoDate(value, field) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error(field + " must be YYYY-MM-DD");
  }
  const date = new Date(value + "T00:00:00Z");
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new Error(field + " is not a valid date");
  }
  return date;
}

function guestCount(value, field, fallback, min) {
  const count = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(count) || count < min || count > 20) {
    throw new Error(field + " must be an integer from " + min + " to 20");
  }
  return count;
}

function checkoutUrl(roomId, checkIn, checkOut) {
  const u = new URL("https://beds24.com/booking2.php");
  u.searchParams.set("propid", PROPERTY_ID);
  u.searchParams.set("checkin", checkIn);
  u.searchParams.set("checkout", checkOut);
  if (roomId) u.searchParams.set("roomid", roomId);
  u.searchParams.set("referer", "ELCID_AI_AGENT");
  return u.toString();
}

export async function quoteElCidAvailability(input = {}) {
  const arrival = isoDate(input.checkIn, "checkIn");
  const departure = isoDate(input.checkOut, "checkOut");
  const nights = Math.round((departure.getTime() - arrival.getTime()) / 86400000);
  if (nights < 1 || nights > 31) throw new Error("stay must be 1 to 31 nights");
  const adults = guestCount(input.adults, "adults", 2, 1);
  const children = guestCount(input.children, "children", 0, 0);
  const payload = {
    propId: PROPERTY_ID,
    checkIn: input.checkIn.replaceAll("-", ""),
    checkOut: input.checkOut.replaceAll("-", ""),
    numAdult: String(adults),
    numChild: String(children),
  };
  const response = await fetch(API_URL, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error("Beds24 availability source returned HTTP " + response.status);
  const raw = await response.json();
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("Unexpected Beds24 response structure");
  const inventory = ROOMS.map(([roomId, name]) => {
    const entry = raw[roomId] ?? {};
    const count = Number(entry.roomsavail);
    const total = typeof entry.price === "number" && Number.isFinite(entry.price) ? entry.price : null;
    const bookable = total !== null && total >= 0 && Number.isFinite(count) && count > 0;
    return {
      roomId, name, bookable,
      availableUnits: bookable ? Math.floor(count) : 0,
      stayTotal: bookable ? total : null,
      nightlyEquivalent: bookable ? Math.round((total / nights) * 100) / 100 : null,
      currency: entry.currency || raw.currency || null,
      checkoutUrl: bookable ? checkoutUrl(roomId, input.checkIn, input.checkOut) : null,
    };
  });
  return {
    property: "EL CID Country Club",
    propertyId: PROPERTY_ID,
    location: "Benidoleig, Alicante, Spain",
    checkIn: input.checkIn,
    checkOut: input.checkOut,
    nights,
    adults,
    children,
    inventory,
    allAvailabilityUrl: checkoutUrl(null, input.checkIn, input.checkOut),
    source: "Beds24 public live availability",
    generatedAt: new Date().toISOString(),
    reservationCreated: false,
    paymentCollected: false,
    bookingNote: "Read-only quote: live availability and published stay totals for the requested party and dates. Final price, fees, cancellation and payment conditions are confirmed during guest-operated Beds24 checkout. No reservation or payment has occurred.",
  };
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Accept, Content-Type");
  res.setHeader("Cache-Control", "no-store");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET, OPTIONS");
    return res.status(405).json({ error: "Method not allowed" });
  }
  try {
    const output = await quoteElCidAvailability(req.query);
    return res.status(200).json(output);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Quote failed";
    const inputError = /must be|valid date|stay must be/.test(message);
    return res.status(inputError ? 400 : 502).json({
      ok: false,
      error: inputError ? message : "Live availability temporarily unavailable",
    });
  }
}
