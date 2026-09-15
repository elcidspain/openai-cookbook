# EL CID agent runtime hardening checkpoint

## Objective
Verify and harden the live EL CID agent runtime beyond the Cloudflare 100/100 discovery score.

## Status
complete

## Scope
Allowed: EL CID public machine-readable guidance, MCP/A2A read-only runtime semantics, one manual verification script, and documentation for this execution.

Excluded: Beds24 data or credentials, booking writes, production deployment/runtime configuration changes, scheduled monitoring, payments, external messaging, AUMARA production changes, and marketing/publicity.

## Evidence
- Live production Markdown negotiation, llms.txt, Agent Skill, MCP Server Card, A2A Agent Card, and OAuth discovery returned HTTP 200 on 2026-09-15.
- Live MCP initialize, tools/list and guest-guide call returned HTTP 200.
- Live A2A message/send returned HTTP 200.
- Production baseline on the new verifier: 4/14 PASS; OAuth and DNS-AID/DNSSEC were already live, while semantic/runtime hardening remained absent.
- Branch-compatible local HTTP harness: 14/14 PASS.
- READY Vercel preview for PR #158: 14/14 PASS end-to-end against `https://openai-cookbook-958n37w8t-elidspaincom.vercel.app`.

## Changes
- Added explicit Benidoleig vs Mexico/Mazatlán/Sinaloa disambiguation.
- Hardened AUMARA separation and legacy third-party data handling.
- Added typed MCP booking intent for dates, guests, accommodation type and dining intent.
- Made unchecked availability, price and restaurant times explicit in structured output.
- Added fail-closed invalid-date handling.
- Added a manual end-to-end verifier covering Markdown, skills, MCP, A2A, OAuth and DNS-AID/DNSSEC.

## Tests
- JS syntax and JSON parse checks: PASS.
- Local handler behavior tests: PASS.
- `node scripts/verify-elcid-agent-runtime.mjs` against current production: 4/14 PASS (expected pre-merge baseline).
- Same verifier against branch-compatible local harness: 14/14 PASS.
- Same verifier against the deployed PR preview: 14/14 PASS.

## Stop condition
Reached: draft PR #158 contains the scoped hardening and the deployed preview passes 14/14. Production confirmation is intentionally pending separate merge/deploy authorization.

## Recovery point
Branch: `agent/elcid-runtime-hardening`.
Draft PR: #158.
Base: `main` at `e2629ddbfed2e5cb8dd93b6e9bcdebb4aafd0788`.
Next safe action: authorize merge/deploy, then rerun the identical verifier against `https://www.elcidspain.com` and require 14/14 before declaring the runtime hardening live.
