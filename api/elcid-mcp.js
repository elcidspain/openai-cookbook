const PROTOCOL_VERSION = "2025-06-18";

const guestGuideSchema = {
  type: "object",
  properties: {
    query: {
      type: "string",
      maxLength: 500,
      description: "Optional guest question used only to select relevant public guidance."
    },
    language: {
      type: "string",
      enum: ["en", "es", "ru"],
      description: "Preferred response language hint. Current canonical facts remain unchanged."
    }
  },
  additionalProperties: false
};

const bookingIntentSchema = {
  type: "object",
  properties: {
    checkIn: { type: "string", pattern: "^\\d{4}-\\d{2}-\\d{2}$", description: "Requested arrival date, YYYY-MM-DD." },
    checkOut: { type: "string", pattern: "^\\d{4}-\\d{2}-\\d{2}$", description: "Requested departure date, YYYY-MM-DD." },
    adults: { type: "integer", minimum: 1, maximum: 20 },
    children: { type: "integer", minimum: 0, maximum: 20 },
    accommodationType: {
      type: "string",
      enum: ["double-terrace", "family-room", "studio-kitchen", "unspecified"]
    },
    dining: {
      type: "string",
      enum: ["none", "breakfast", "dinner", "private-table", "unspecified"]
    }
  },
  additionalProperties: false
};

const tools = [
  {
    name: "elcid_guest_guide",
    title: "EL CID Country Club guest guide",
    description: "Return current public EL CID identity, stay, restaurant, contact and policy guidance with entity-disambiguation guards. Read-only.",
    inputSchema: guestGuideSchema,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  },
  {
    name: "elcid_booking_options",
    title: "EL CID booking and contact options",
    description: "Accept a guest booking intent and return the authoritative public booking/contact routes. This tool does not check live inventory or price and never creates or modifies a reservation.",
    inputSchema: bookingIntentSchema,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  }
];

const bookingOptions = {
  property: "EL CID Country Club",
  location: "Carrer Rincón del Silencio, 3, 03759 Benidoleig, Alicante, Spain",
  booking: "https://www.booking.com/hotel/es/el-cid-country-club.html",
  whatsapp: "https://wa.me/34622914323",
  telephone: "+34966579970",
  email: "elcidspain@gmail.com",
  website: "https://www.elcidspain.com/"
};

const identity = {
  canonical: "EL CID Country Club in Benidoleig, Alicante, Spain",
  notMexico: "This is not an El Cid resort or hotel in Mexico, Mazatlán or Sinaloa.",
  aumara: "AUMARA is a separate accommodation product and is never an EL CID room type, unit, package or inventory category.",
  legacy: "Historical third-party listings may contain retired hours, menus, cuisine labels, bowling references or other legacy descriptions; they are not current unless the canonical EL CID site confirms them."
};

function guideFor(query = "") {
  const q = String(query).toLowerCase();
  const base = "EL CID Country Club is a country-club hospitality property in Benidoleig, Marina Alta, Alicante, Spain, with guest rooms, an independent studio with kitchen, restaurant service, an outdoor pool, terraces, tennis and access to hiking and cycling routes between mountain and Mediterranean coast.";
  if (/mexic|mazatl|sinaloa/.test(q)) return `${base} ${identity.notMexico} Canonical site: ${bookingOptions.website}`;
  if (q.includes("aumara")) return `${base} ${identity.aumara} Canonical EL CID site: ${bookingOptions.website}`;
  if (/hour|open|close|menu|cuisine|dinner|breakfast|restaurant/.test(q)) return `${base} The current public site presents breakfast, day service, dinners and private tables, but current menus, prices and service times must be confirmed through the current booking/contact routes. Do not infer current opening hours from legacy directories or search snippets.`;
  if (/price|rate|availability|date|book|reserv/.test(q)) return `${base} Live availability, prices, cancellation conditions and reservation-specific terms are not asserted by this tool and must be confirmed through the public booking route.`;
  return `${base} ${identity.notMexico} ${identity.aumara} Canonical site: ${bookingOptions.website}`;
}

function validDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
}

function normalizeBookingIntent(args) {
  const input = args && typeof args === "object" && !Array.isArray(args) ? args : {};
  const allowed = new Set(["checkIn", "checkOut", "adults", "children", "accommodationType", "dining"]);
  for (const key of Object.keys(input)) if (!allowed.has(key)) throw new Error(`Unsupported booking-intent field: ${key}`);
  if (input.checkIn !== undefined && !validDate(input.checkIn)) throw new Error("checkIn must be a valid YYYY-MM-DD date");
  if (input.checkOut !== undefined && !validDate(input.checkOut)) throw new Error("checkOut must be a valid YYYY-MM-DD date");
  if (input.checkIn && input.checkOut && input.checkOut <= input.checkIn) throw new Error("checkOut must be later than checkIn");
  if (input.adults !== undefined && (!Number.isInteger(input.adults) || input.adults < 1 || input.adults > 20)) throw new Error("adults must be an integer from 1 to 20");
  if (input.children !== undefined && (!Number.isInteger(input.children) || input.children < 0 || input.children > 20)) throw new Error("children must be an integer from 0 to 20");
  const roomTypes = new Set(["double-terrace", "family-room", "studio-kitchen", "unspecified"]);
  if (input.accommodationType !== undefined && !roomTypes.has(input.accommodationType)) throw new Error("unsupported accommodationType");
  const diningModes = new Set(["none", "breakfast", "dinner", "private-table", "unspecified"]);
  if (input.dining !== undefined && !diningModes.has(input.dining)) throw new Error("unsupported dining mode");
  return { ...input };
}

function setHeaders(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("MCP-Protocol-Version", PROTOCOL_VERSION);
}

function result(res, id, value, status = 200) {
  setHeaders(res);
  res.status(status).json({ jsonrpc: "2.0", id: id ?? null, result: value });
}

function error(res, id, code, message, status = 200) {
  setHeaders(res);
  res.status(status).json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

export default function handler(req, res) {
  setHeaders(res);
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).end();
  }

  let message = req.body;
  if (typeof message === "string") {
    try { message = JSON.parse(message); } catch { return error(res, null, -32700, "Parse error", 400); }
  }
  if (!message || message.jsonrpc !== "2.0" || typeof message.method !== "string") {
    return error(res, message?.id ?? null, -32600, "Invalid Request", 400);
  }

  const { id, method, params } = message;
  if (method === "initialize") {
    return result(res, id, {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: { name: "elcid-public-mcp", title: "EL CID Country Club Public MCP", version: "1.1.0" },
      instructions: "Read-only public EL CID guidance and booking-intent routing. Never invent availability, price, restaurant hours or a reservation. Keep EL CID Benidoleig distinct from AUMARA and from El Cid brands in Mexico."
    });
  }
  if (method === "notifications/initialized") return res.status(202).end();
  if (method === "ping") return result(res, id, {});
  if (method === "tools/list") return result(res, id, { tools });
  if (method === "tools/call") {
    if (params?.name === "elcid_guest_guide") {
      const args = params?.arguments && typeof params.arguments === "object" ? params.arguments : {};
      const guide = guideFor(args.query);
      return result(res, id, {
        content: [{ type: "text", text: guide }],
        structuredContent: { guide, identity, canonical: bookingOptions.website },
        isError: false
      });
    }
    if (params?.name === "elcid_booking_options") {
      let intent;
      try { intent = normalizeBookingIntent(params?.arguments); }
      catch (err) { return error(res, id, -32602, err.message); }
      const value = {
        ...bookingOptions,
        intent,
        availabilityChecked: false,
        priceChecked: false,
        restaurantTimesChecked: false,
        nextStep: "Use the public booking route for live availability, price and reservation-specific conditions. Use EL CID WhatsApp/email for dining times, current menus or private-table confirmation.",
        identity
      };
      return result(res, id, {
        content: [{ type: "text", text: JSON.stringify(value) }],
        structuredContent: value,
        isError: false
      });
    }
    return error(res, id, -32602, `Unknown tool: ${String(params?.name ?? "")}`);
  }
  return error(res, id, -32601, `Method not found: ${method}`);
}
