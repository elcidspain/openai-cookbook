const PROTOCOL_VERSION = "2025-06-18";

const tools = [
  {
    name: "elcid_guest_guide",
    title: "EL CID Country Club guest guide",
    description: "Return public EL CID stay, location, restaurant, contact and policy guidance. Read-only.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "elcid_booking_options",
    title: "EL CID booking and contact options",
    description: "Return the public Booking.com and contact routes shown by EL CID. This does not create or modify a reservation. Read-only.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
];

const guide = "EL CID Country Club is a small rural hotel in Benidoleig, Marina Alta, Alicante, Spain. The public site presents a double room with terrace, a family room, an independent studio with kitchen, a restaurant, outdoor pool, terraces, tennis, hiking and cycling access. Live availability, prices, cancellation conditions and service times must be confirmed through the public booking or contact routes. Canonical site: https://www.elcidspain.com/";

const bookingOptions = {
  property: "EL CID Country Club",
  location: "Carrer Rincón del Silencio, 3, 03759 Benidoleig, Alicante, Spain",
  booking: "https://www.booking.com/hotel/es/el-cid-country-club.html",
  whatsapp: "https://wa.me/34622914323",
  telephone: "+34966579970",
  email: "elcidspain@gmail.com",
  website: "https://www.elcidspain.com/",
};

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
      serverInfo: { name: "elcid-public-mcp", title: "EL CID Country Club Public MCP", version: "1.0.0" },
      instructions: "Read-only public hotel guidance and booking/contact discovery. These tools do not create, modify or cancel reservations.",
    });
  }
  if (method === "notifications/initialized") return res.status(202).end();
  if (method === "ping") return result(res, id, {});
  if (method === "tools/list") return result(res, id, { tools });
  if (method === "tools/call") {
    if (params?.name === "elcid_guest_guide") {
      return result(res, id, {
        content: [{ type: "text", text: guide }],
        structuredContent: { guide, canonical: bookingOptions.website },
        isError: false,
      });
    }
    if (params?.name === "elcid_booking_options") {
      return result(res, id, {
        content: [{ type: "text", text: JSON.stringify(bookingOptions) }],
        structuredContent: bookingOptions,
        isError: false,
      });
    }
    return error(res, id, -32602, `Unknown tool: ${String(params?.name ?? "")}`);
  }
  return error(res, id, -32601, `Method not found: ${method}`);
}
