import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { ELCID_OAUTH_BUILD_KEY } from "./_elcid-oauth-key.js";

export const ISSUER = "https://www.elcidspain.com";
export const RESOURCE = "https://www.elcidspain.com";
export const SCOPE = "agent.read";
export const PROTECTED_ENDPOINT = `${RESOURCE}/api/agent/protected`;
export const TOKEN_TTL_SECONDS = 600;
const CODE_TTL_SECONDS = 300;

function encodeJson(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

function safeEqual(a, b) {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  return aa.length === bb.length && timingSafeEqual(aa, bb);
}

function signature(kind, payload) {
  return createHmac("sha256", ELCID_OAUTH_BUILD_KEY).update(`${kind}.${payload}`).digest("base64url");
}

function seal(kind, value) {
  const payload = encodeJson(value);
  return `elcid1.${kind}.${payload}.${signature(kind, payload)}`;
}

function open(kind, token) {
  const parts = String(token || "").split(".");
  if (parts.length !== 4 || parts[0] !== "elcid1" || parts[1] !== kind) return null;
  if (!safeEqual(parts[3], signature(kind, parts[2]))) return null;
  try {
    return JSON.parse(Buffer.from(parts[2], "base64url").toString("utf8"));
  } catch {
    return null;
  }
}

function validRedirectUri(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:") return true;
    return url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  } catch {
    return false;
  }
}

export function registerClient(input = {}) {
  const name = typeof input.client_name === "string" && input.client_name.trim()
    ? input.client_name.trim().slice(0, 120)
    : "Agent client";
  const redirects = Array.isArray(input.redirect_uris)
    ? input.redirect_uris.filter((v) => typeof v === "string" && validRedirectUri(v)).slice(0, 8)
    : [];
  if (!redirects.length) throw new Error("redirect_uris must contain at least one HTTPS or loopback callback");
  const registration = { client_name: name, redirect_uris: redirects, iat: Math.floor(Date.now() / 1000) };
  return {
    client_id: seal("client", registration),
    client_name: name,
    redirect_uris: redirects,
    token_endpoint_auth_method: "none",
    grant_types: ["authorization_code"],
    response_types: ["code"],
  };
}

function readClient(clientId) {
  return open("client", clientId);
}

export function issueAuthorizationCode({ clientId, redirectUri, codeChallenge, scope = SCOPE, resource = RESOURCE }) {
  const client = readClient(clientId);
  if (!client || !client.redirect_uris.includes(redirectUri)) throw new Error("invalid_client_or_redirect_uri");
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(codeChallenge)) throw new Error("invalid_code_challenge");
  if (scope !== SCOPE || resource !== RESOURCE) throw new Error("invalid_scope_or_resource");
  const now = Math.floor(Date.now() / 1000);
  return seal("code", {
    client_id: clientId,
    redirect_uri: redirectUri,
    code_challenge: codeChallenge,
    scope,
    resource,
    iat: now,
    exp: now + CODE_TTL_SECONDS,
  });
}

export function exchangeAuthorizationCode({ code, clientId, redirectUri, codeVerifier }) {
  const grant = open("code", code);
  const now = Math.floor(Date.now() / 1000);
  if (!grant || grant.exp <= now) throw new Error("invalid_grant");
  if (grant.client_id !== clientId || grant.redirect_uri !== redirectUri) throw new Error("invalid_grant");
  if (!/^[A-Za-z0-9._~-]{43,128}$/.test(codeVerifier)) throw new Error("invalid_code_verifier");
  const challenge = createHash("sha256").update(codeVerifier).digest("base64url");
  if (!safeEqual(challenge, grant.code_challenge)) throw new Error("invalid_grant");
  return issueAccessToken(clientId);
}

function issueAccessToken(clientId) {
  const now = Math.floor(Date.now() / 1000);
  return {
    accessToken: seal("access", {
      iss: ISSUER,
      aud: RESOURCE,
      sub: clientId,
      scope: SCOPE,
      iat: now,
      exp: now + TOKEN_TTL_SECONDS,
    }),
    expiresIn: TOKEN_TTL_SECONDS,
  };
}

export function verifyAccessToken(token) {
  const claims = open("access", token);
  const now = Math.floor(Date.now() / 1000);
  if (!claims || claims.iss !== ISSUER || claims.aud !== RESOURCE) return null;
  if (claims.scope !== SCOPE || typeof claims.exp !== "number" || claims.exp <= now) return null;
  return claims;
}

export function cors(res, methods) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept");
  res.setHeader("Access-Control-Allow-Methods", methods);
  res.setHeader("Cache-Control", "no-store");
}
