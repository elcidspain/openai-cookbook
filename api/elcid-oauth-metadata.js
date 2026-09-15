import { ISSUER, RESOURCE, SCOPE } from "../elcid-server/oauth-core.js";

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=300, s-maxage=300");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).end();
  }
  return res.status(200).json({
    issuer: ISSUER,
    resource: RESOURCE,
    authorization_servers: [ISSUER],
    authorization_endpoint: `${ISSUER}/oauth/authorize`,
    token_endpoint: `${ISSUER}/oauth/token`,
    registration_endpoint: `${ISSUER}/oauth/register`,
    response_types_supported: ["code"],
    grant_types_supported: ["authorization_code"],
    token_endpoint_auth_methods_supported: ["none"],
    code_challenge_methods_supported: ["S256"],
    scopes_supported: [SCOPE],
    bearer_methods_supported: ["header"],
    service_documentation: `${ISSUER}/auth.md`,
    agent_auth: {
      skill: `${ISSUER}/auth.md`,
      register_uri: `${ISSUER}/oauth/register`,
      protected_resource_metadata: `${ISSUER}/.well-known/oauth-protected-resource`,
      identity_types_supported: ["anonymous"],
      credential_types_supported: ["oauth2_bearer"],
      grant_types_supported: ["authorization_code"],
      scopes_supported: [SCOPE],
    },
  });
}
