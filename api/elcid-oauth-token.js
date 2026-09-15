import { RESOURCE, SCOPE, cors, exchangeAuthorizationCode } from "../elcid-server/oauth-core.js";

export default function handler(req, res) {
  cors(res, "POST, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).end();
  }
  const body = req.body || {};
  if (body.grant_type !== "authorization_code") {
    return res.status(400).json({ error: "unsupported_grant_type" });
  }
  try {
    const token = exchangeAuthorizationCode({
      code: String(body.code || ""),
      clientId: String(body.client_id || ""),
      redirectUri: String(body.redirect_uri || ""),
      codeVerifier: String(body.code_verifier || ""),
    });
    return res.status(200).json({
      access_token: token.accessToken,
      token_type: "Bearer",
      expires_in: token.expiresIn,
      scope: SCOPE,
      resource: RESOURCE,
    });
  } catch (error) {
    return res.status(400).json({
      error: "invalid_grant",
      error_description: error instanceof Error ? error.message : "Token exchange rejected",
    });
  }
}
