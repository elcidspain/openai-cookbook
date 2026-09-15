# EL CID runtime hardening verification results

Date: 2026-09-15

## Production baseline before this branch
Manual verifier against `https://www.elcidspain.com` passed 4/14 checks:
- PASS Markdown negotiation
- PASS MCP initialize (v1.0.0)
- PASS OAuth discovery
- PASS authenticated DNS-AID + DNSSEC (2/2 names)

The remaining 10 checks correctly failed because production still lacks the branch-only identity firewall, typed MCP intent schema, fail-closed date validation, and A2A stale/entity guards.

## Branch-compatible verification
The same verifier was run against a local HTTP harness serving the branch static files and branch MCP/A2A handlers while using the live OAuth discovery and live DNS-AID/DNSSEC chain.

Result: 14/14 PASS.

Verified behaviors:
- Markdown negotiation and machine-readable discovery
- EL CID Benidoleig vs Mexico/Mazatlán/Sinaloa disambiguation
- AUMARA kept as a separate product/inventory
- legacy opening-hours/menu/bowling claims treated as non-authoritative
- typed MCP booking intent for dates, guests, accommodation type and dining intent
- explicit `availabilityChecked: false` and `priceChecked: false`
- invalid date ranges fail closed with JSON-RPC `-32602`
- live OAuth discovery contract remains available
- authenticated DNS-AID/DNSSEC remains 2/2

No Beds24 access, booking writes, deployment, scheduled monitoring, external messaging or marketing action was performed.
