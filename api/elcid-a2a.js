const HOTEL = {
  name: "EL CID Country Club",
  location: "Carrer Rincón del Silencio, 3, 03759 Benidoleig, Alicante, Spain",
  website: "https://www.elcidspain.com/",
  booking: "https://www.booking.com/hotel/es/el-cid-country-club.html",
  whatsapp: "https://wa.me/34622914323",
  telephone: "+34966579970",
  email: "elcidspain@gmail.com",
  images: [
    "https://drive.google.com/thumbnail?id=1WseSi-ges1Zsw9PpolGfIJChA3f9VelG&sz=w1800",
    "https://drive.google.com/thumbnail?id=1Tcug1LE7FnA8ThqXeBWc60SQzO1fXSkB&sz=w1800",
    "https://drive.google.com/thumbnail?id=1sNBC9u1rsO0CiOksJ93RqkzWeZF7tLBF&sz=w1600"
  ]
};

const identity = {
  canonical: "EL CID Country Club in Benidoleig, Alicante, Spain",
  notMexico: "This is not an El Cid resort or hotel in Mexico, Mazatlán or Sinaloa.",
  aumara: "AUMARA is a separate accommodation product and is never an EL CID room type, unit, package or inventory category.",
  legacy: "Historical third-party listings may contain retired opening hours, menus, cuisine labels, bowling references or other legacy descriptions; they are not current unless the canonical EL CID site confirms them."
};

function setHeaders(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept");
  res.setHeader("Cache-Control", "no-store");
}

function textFor(params) {
  const query = JSON.stringify(params ?? "").toLowerCase();
  const base = `EL CID Country Club is a country-club hospitality property in Benidoleig, Marina Alta, Alicante, with guest rooms, an independent studio with kitchen, restaurant service, outdoor pool, terraces, tennis and access to hiking and cycling routes between mountain and Mediterranean coast.`;

  if (/mexic|mazatl|sinaloa/.test(query)) {
    return `${base} ${identity.notMexico} Canonical site: ${HOTEL.website}`;
  }
  if (query.includes("aumara")) {
    return `${base} ${identity.aumara} EL CID canonical site: ${HOTEL.website}. AUMARA canonical site: https://www.aumara.me/.`;
  }
  if (/hour|open|close|menu|cuisine|bowling|restaurant/.test(query)) {
    return `${base} The current public site presents restaurant service, breakfast, day service, dinners and private tables, but current menus, prices and service times must be confirmed through EL CID's current public contact routes. ${identity.legacy}`;
  }
  if (/book|reserv|availability|date|price|rate/.test(query)) {
    return `EL CID Country Club booking and contact: ${HOTEL.booking}. WhatsApp: ${HOTEL.whatsapp}. Phone: ${HOTEL.telephone}. Email: ${HOTEL.email}. Live prices, dates, inventory and reservation-specific conditions must be confirmed through the booking/contact route. This agent does not create or modify reservations and must not invent availability, price or a discount.`;
  }
  if (query.includes("cycle") || query.includes("cycling") || query.includes("bike") || query.includes("hiking") || query.includes("walk") || query.includes("route")) {
    return `${base} It can suit a quiet cycling or hiking base between mountain and Mediterranean coast. Canonical site: ${HOTEL.website}.`;
  }
  if (query.includes("family") || query.includes("friends") || query.includes("group") || query.includes("gather")) {
    return `${base} It can suit family or friends stays and considered private gatherings; capacity and current service must be confirmed through the public contact routes. Canonical site: ${HOTEL.website}.`;
  }
  return `${base} ${identity.notMexico} ${identity.aumara} Canonical site: ${HOTEL.website}.`;
}

export default function handler(req, res) {
  setHeaders(res);
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).end();
  }

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { return res.status(400).json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }); }
  }

  const id = body?.id ?? null;
  if (body?.method === "SendMessage" || body?.method === "message/send") {
    return res.status(200).json({
      jsonrpc: "2.0",
      id,
      result: {
        kind: "message",
        messageId: `elcid-${Date.now()}`,
        role: "agent",
        parts: [{ kind: "text", text: textFor(body?.params) }],
        metadata: {
          canonical: HOTEL.website,
          booking: HOTEL.booking,
          identity,
          availabilityChecked: false,
          priceChecked: false,
          images: HOTEL.images
        }
      }
    });
  }

  return res.status(404).json({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found" } });
}
