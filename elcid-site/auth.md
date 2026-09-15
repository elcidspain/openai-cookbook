# auth.md — EL CID Country Club agent access

EL CID exposes public read-only guest discovery anonymously and a separate OAuth-protected read-only proof surface. No guest account, payment credential, booking write permission, private guest data, or reservation mutation is available through this OAuth scope.

Resource server: `https://www.elcidspain.com`
Authorization server: `https://www.elcidspain.com`
Protected resource: `https://www.elcidspain.com/api/agent/protected`
Scope: `agent.read`

## Step 1 — Discover

Request the protected resource without a token. EL CID returns `401` with a Bearer challenge containing:

```http
resource_metadata="https://www.elcidspain.com/.well-known/oauth-protected-resource"
```

Fetch `https://www.elcidspain.com/.well-known/oauth-protected-resource`, then follow `authorization_servers[0]` to `https://www.elcidspain.com/.well-known/oauth-authorization-server`.

## Step 2 — Register the agent callback

```http
POST https://www.elcidspain.com/oauth/register
Content-Type: application/json

{
  "client_name": "My travel assistant",
  "redirect_uris": ["http://localhost:8400/callback"]
}
```

The response contains a signed `client_id`. HTTPS callbacks and loopback HTTP callbacks are accepted. Client authentication method is `none` because this flow is for public agents and the only scope exposes public read-only material.

## Step 3 — Create PKCE values

Generate a 43–128 character `code_verifier`. Set `code_challenge` to `BASE64URL(SHA256(code_verifier))`. Only `S256` is accepted.

## Step 4 — Authorize

Open:

```text
https://www.elcidspain.com/oauth/authorize?response_type=code&client_id=<CLIENT_ID>&redirect_uri=<REDIRECT_URI>&scope=agent.read&resource=https%3A%2F%2Fwww.elcidspain.com&code_challenge=<CHALLENGE>&code_challenge_method=S256&state=<STATE>
```

Because `agent.read` contains only public EL CID discovery data and no user-specific data, EL CID grants this narrow scope automatically and redirects to the registered callback with `code`, `state`, and `iss`.

## Step 5 — Exchange the code

```http
POST https://www.elcidspain.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&code=<CODE>&client_id=<CLIENT_ID>&redirect_uri=<REDIRECT_URI>&code_verifier=<VERIFIER>
```

A successful response returns a Bearer token valid for 600 seconds, scoped only to `agent.read` and audience-bound to `https://www.elcidspain.com`.

## Step 6 — Use the protected resource

```http
GET https://www.elcidspain.com/api/agent/protected
Authorization: Bearer <ACCESS_TOKEN>
```

On expiry or an invalid token, repeat discovery and the PKCE flow. The endpoint cannot create, hold, change, cancel, or charge a reservation.

## Anonymous public surfaces

OAuth is not required for the public website, `llms.txt`, agent skills, API catalog, MCP endpoint at `https://www.elcidspain.com/mcp`, or A2A endpoint at `https://www.elcidspain.com/a2a`.

Reservations remain in the public booking/contact routes published by EL CID.

## Machine-readable registration markers

```yaml
agent_auth:
  skill: https://www.elcidspain.com/auth.md
  register_uri: https://www.elcidspain.com/oauth/register
  protected_resource_metadata: https://www.elcidspain.com/.well-known/oauth-protected-resource
  authorization_server_metadata: https://www.elcidspain.com/.well-known/oauth-authorization-server
  identity_types_supported:
    - anonymous
  credential_types_supported:
    - oauth2_bearer
  grant_types_supported:
    - authorization_code
  scopes_supported:
    - agent.read
```

Last updated: 2026-09-15
