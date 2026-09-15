import { ISSUER, RESOURCE, SCOPE, issueAuthorizationCode } from "./_elcid-oauth-core.js";

export default function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).end();
  }
  const {
    response_type: responseType,
    client_id: clientId = "",
    redirect_uri: redirectUri = "",
    code_challenge: codeChallenge = "",
    code_challenge_method: method,
    scope = SCOPE,
    resource = RESOURCE,
    state,
  } = req.query || {};
  if (responseType !== "code" || method !== "S256") {
    return res.status(400).json({ error: "invalid_request", error_description: "response_type=code and code_challenge_method=S256 are required" });
  }
  try {
    const code = issueAuthorizationCode({ clientId, redirectUri, codeChallenge, scope, resource });
    const callback = new URL(redirectUri);
    callback.searchParams.set("code", code);
    if (typeof state === "string" && state) callback.searchParams.set("state", state);
    callback.searchParams.set("iss", ISSUER);
    res.setHeader("Location", callback.href);
    return res.status(302).end();
  } catch (error) {
    return res.status(400).json({
      error: "invalid_request",
      error_description: error instanceof Error ? error.message : "Authorization request rejected",
    });
  }
}
