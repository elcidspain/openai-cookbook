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

function setHeaders(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept");
  res.setHeader("Cache-Control", "no-store");
}

function textFor(params) {
  const query = JSON.stringify(params ?? "").toLowerCase();
  if (query.includes("book") || query.includes("reserv") || query.includes("availability") || query.includes("date")) {
    return `EL CID Country Club booking and contact: ${HOTEL.booking}. WhatsApp: ${HOTEL.whatsapp}. Phone: ${HOTEL.telephone}. Email: ${HOTEL.email}. Live prices, dates and conditions must be confirmed through the booking/contact route. This agent does not create or modify reservations.`;
  }
  return `EL CID Country Club is a small rural hotel in Benidoleig, Marina Alta, Alicante, with rooms, an independent studio with kitchen, restaurant, outdoor pool, terraces, tennis and access to hiking and cycling. Canonical site: ${HOTEL.website}.`;
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
        metadata: { canonical: HOTEL.website, booking: HOTEL.booking, images: HOTEL.images }
      }
    });
  }

  return res.status(404).json({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found" } });
}
