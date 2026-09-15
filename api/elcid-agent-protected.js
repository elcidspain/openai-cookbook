import { PROTECTED_ENDPOINT, SCOPE, cors, verifyAccessToken } from "./_elcid-oauth-core.js";

const resourceMetadata = "https://www.elcidspain.com/.well-known/oauth-protected-resource";

export default function handler(req, res) {
  cors(res, "GET, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET, OPTIONS");
    return res.status(405).end();
  }
  const authorization = String(req.headers.authorization || "");
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  const claims = token ? verifyAccessToken(token) : null;
  if (!claims) {
    res.setHeader("WWW-Authenticate", `Bearer realm="EL CID", error="invalid_token", scope="${SCOPE}", resource_metadata="${resourceMetadata}"`);
    return res.status(401).json({
      error: "invalid_token",
      error_description: "A valid short-lived EL CID agent.read bearer token is required",
      resource_metadata: resourceMetadata,
    });
  }
  return res.status(200).json({
    ok: true,
    resource: PROTECTED_ENDPOINT,
    scope: claims.scope,
    subject: claims.sub,
    property: "EL CID Country Club",
    access: "read-only",
    publicMcp: "https://www.elcidspain.com/mcp",
    publicA2a: "https://www.elcidspain.com/a2a",
    website: "https://www.elcidspain.com/",
    note: "This protected surface contains public discovery data only and cannot create, change, hold, cancel or charge a reservation.",
  });
}
