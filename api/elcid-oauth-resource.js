import { ISSUER, RESOURCE, SCOPE } from "../elcid-server/oauth-core.js";

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=300, s-maxage=300");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).end();
  }
  return res.status(200).json({
    resource: RESOURCE,
    authorization_servers: [ISSUER],
    scopes_supported: [SCOPE],
    bearer_methods_supported: ["header"],
    resource_name: "EL CID read-only agent resource",
    resource_documentation: `${ISSUER}/auth.md`,
  });
}
