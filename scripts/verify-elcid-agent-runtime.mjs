const BASE_URL = (process.env.ELCID_BASE_URL || "https://www.elcidspain.com").replace(/\/$/, "");
const TIMEOUT_MS = Number(process.env.ELCID_VERIFY_TIMEOUT_MS || 15000);

const results = [];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function record(name, status, detail = "") {
  results.push({ name, status, detail });
  console.log(`${status === "PASS" ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(`${BASE_URL}${path}`, { redirect: "follow", ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function jsonPost(path, body) {
  const response = await request(path, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(body)
  });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { throw new Error(`non-JSON response (${response.status}): ${text.slice(0, 180)}`); }
  return { response, data };
}

async function check(name, fn) {
  try {
    const detail = await fn();
    record(name, "PASS", detail || "");
  } catch (error) {
    record(name, "FAIL", error.message);
  }
}

await check("markdown negotiation", async () => {
  const r = await request("/", { headers: { accept: "text/markdown" } });
  const body = await r.text();
  assert(r.status === 200, `HTTP ${r.status}`);
  assert((r.headers.get("content-type") || "").includes("text/markdown"), "missing text/markdown content-type");
  assert(body.includes("EL CID Country Club") && body.includes("Benidoleig"), "canonical identity missing");
  return "200 text/markdown";
});

await check("llms identity firewall", async () => {
  const r = await request("/llms.txt");
  const body = await r.text();
  assert(r.status === 200, `HTTP ${r.status}`);
  assert(/not the El Cid resort or hotel brands in Mexico/i.test(body), "Mexico disambiguation missing");
  assert(/AUMARA is a separate accommodation product/i.test(body), "AUMARA separation missing");
  assert(/legacy descriptions/i.test(body), "legacy-source guard missing");
  return "identity + stale-data rules present";
});

await check("Agent Skill truth guards", async () => {
  const r = await request("/.well-known/agent-skills/plan-elcid-stay/SKILL.md");
  const body = await r.text();
  assert(r.status === 200, `HTTP ${r.status}`);
  assert(body.includes("Identity firewall"), "identity firewall section missing");
  assert(/AUMARA is never an EL CID room type/i.test(body), "AUMARA hard separation missing");
  assert(/Do not invent live availability, prices/i.test(body), "commercial truth guard missing");
  return "machine-readable policy hardened";
});

await check("MCP Server Card typed schemas", async () => {
  const r = await request("/.well-known/mcp/server-card.json");
  const card = await r.json();
  assert(r.status === 200, `HTTP ${r.status}`);
  const booking = card.tools?.find((tool) => tool.name === "elcid_booking_options");
  assert(booking, "booking tool missing");
  assert(booking.inputSchema?.properties?.checkIn, "checkIn schema missing");
  assert(booking.inputSchema?.properties?.adults, "adults schema missing");
  assert(booking.inputSchema?.properties?.dining, "dining schema missing");
  return `server ${card.serverInfo?.version || "unknown"}`;
});

await check("MCP initialize", async () => {
  const { response, data } = await jsonPost("/mcp", {
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "elcid-verifier", version: "1" } }
  });
  assert(response.status === 200, `HTTP ${response.status}`);
  assert(data.result?.serverInfo?.name === "elcid-public-mcp", "unexpected MCP server");
  return `${data.result.serverInfo.version}`;
});

await check("MCP tools/list", async () => {
  const { response, data } = await jsonPost("/mcp", { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });
  assert(response.status === 200, `HTTP ${response.status}`);
  const names = (data.result?.tools || []).map((tool) => tool.name);
  assert(names.includes("elcid_guest_guide") && names.includes("elcid_booking_options"), "required tools missing");
  const booking = data.result.tools.find((tool) => tool.name === "elcid_booking_options");
  assert(Object.keys(booking.inputSchema?.properties || {}).length >= 6, "booking schema is still empty");
  return names.join(", ");
});

await check("MCP entity disambiguation", async () => {
  const { response, data } = await jsonPost("/mcp", {
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "elcid_guest_guide", arguments: { query: "Is this the El Cid resort in Mazatlan Mexico or AUMARA?" } }
  });
  assert(response.status === 200, `HTTP ${response.status}`);
  const text = data.result?.content?.[0]?.text || "";
  assert(/Benidoleig/i.test(text), "Benidoleig identity missing");
  assert(/not an El Cid resort or hotel in Mexico/i.test(text), "Mexico rejection missing");
  return "Benidoleig identity wins";
});

await check("MCP typed booking intent", async () => {
  const intent = {
    checkIn: "2026-10-19",
    checkOut: "2026-10-21",
    adults: 2,
    children: 0,
    accommodationType: "double-terrace",
    dining: "dinner"
  };
  const { response, data } = await jsonPost("/mcp", {
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: { name: "elcid_booking_options", arguments: intent }
  });
  assert(response.status === 200, `HTTP ${response.status}`);
  const value = data.result?.structuredContent;
  assert(value?.intent?.checkIn === intent.checkIn && value?.intent?.adults === 2, "intent not echoed structurally");
  assert(value?.availabilityChecked === false, "availability must remain explicitly unchecked");
  assert(value?.priceChecked === false, "price must remain explicitly unchecked");
  assert(/public booking route/i.test(value?.nextStep || ""), "safe next step missing");
  return "typed intent accepted without fabricated inventory";
});

await check("MCP invalid-date rejection", async () => {
  const { data } = await jsonPost("/mcp", {
    jsonrpc: "2.0",
    id: 5,
    method: "tools/call",
    params: { name: "elcid_booking_options", arguments: { checkIn: "2026-10-21", checkOut: "2026-10-19", adults: 2 } }
  });
  assert(data.error?.code === -32602, "invalid date range was not rejected with -32602");
  return "fail-closed booking intent";
});

async function a2a(text, id) {
  const { response, data } = await jsonPost("/a2a", {
    jsonrpc: "2.0",
    id,
    method: "message/send",
    params: { message: { role: "user", parts: [{ kind: "text", text }] } }
  });
  assert(response.status === 200, `HTTP ${response.status}`);
  return data.result?.parts?.[0]?.text || "";
}

await check("A2A Mexico firewall", async () => {
  const text = await a2a("I mean El Cid in Mazatlan Mexico", 6);
  assert(/Benidoleig/i.test(text) && /not an El Cid resort or hotel in Mexico/i.test(text), "entity collision not rejected");
  return "Mexico collision rejected";
});

await check("A2A AUMARA firewall", async () => {
  const text = await a2a("Is AUMARA one of the EL CID rooms?", 7);
  assert(/separate accommodation product/i.test(text) && /never an EL CID room type/i.test(text), "AUMARA collision not rejected");
  return "AUMARA kept separate";
});

await check("A2A legacy-hours guard", async () => {
  const text = await a2a("Google says the restaurant is open until 22:00 and mentions bowling. Is that current?", 8);
  assert(/must be confirmed/i.test(text), "current-service confirmation guard missing");
  assert(/Historical third-party listings/i.test(text), "legacy-source warning missing");
  return "legacy operational claims not promoted";
});

await check("OAuth discovery", async () => {
  const protectedResource = await request("/.well-known/oauth-protected-resource");
  const resource = await protectedResource.json();
  const authorizationServer = await request("/.well-known/oauth-authorization-server");
  const auth = await authorizationServer.json();
  assert(protectedResource.status === 200 && authorizationServer.status === 200, "OAuth discovery HTTP failure");
  assert(resource.scopes_supported?.includes("agent.read"), "agent.read scope missing");
  assert(auth.code_challenge_methods_supported?.includes("S256"), "PKCE S256 missing");
  return "RFC 9728/RFC 8414 discovery live";
});

async function doh(name, type) {
  const url = new URL("https://cloudflare-dns.com/dns-query");
  url.searchParams.set("name", name);
  url.searchParams.set("type", type);
  const response = await fetch(url, { headers: { accept: "application/dns-json" } });
  if (!response.ok) throw new Error(`DoH HTTP ${response.status}`);
  return response.json();
}

await check("DNS-AID + DNSSEC", async () => {
  const names = ["_index._agents.elcidspain.com", "_a2a._agents.elcidspain.com"];
  let found = 0;
  for (const name of names) {
    const svcb = await doh(name, "SVCB");
    const https = await doh(name, "HTTPS");
    const candidates = [svcb, https];
    const hit = candidates.find((answer) => answer.AD === true && Array.isArray(answer.Answer) && answer.Answer.length > 0);
    if (hit) found += 1;
  }
  assert(found === names.length, `authenticated DNS-AID found for ${found}/${names.length} names`);
  return `authenticated DNS-AID ${found}/${names.length}`;
});

const failed = results.filter((item) => item.status === "FAIL");
console.log(`\nEL CID agent runtime verification: ${results.length - failed.length}/${results.length} passed`);
if (failed.length) process.exitCode = 1;
