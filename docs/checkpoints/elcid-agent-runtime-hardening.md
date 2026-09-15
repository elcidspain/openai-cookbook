# EL CID agent runtime hardening checkpoint

## Objective
Verify and harden the live EL CID agent runtime beyond the Cloudflare 100/100 discovery score.

## Status
in progress

## Scope
Allowed: EL CID public machine-readable guidance, MCP/A2A read-only runtime semantics, one manual verification script, and documentation for this execution.

Excluded: Beds24 data or credentials, booking writes, deployment/runtime configuration changes, scheduled monitoring, payments, external messaging, AUMARA production changes, and marketing/publicity.

## Evidence
- Live production Markdown negotiation, llms.txt, Agent Skill, MCP Server Card, A2A Agent Card, and OAuth discovery all returned HTTP 200 on 2026-09-15.
- Live MCP initialize, tools/list, and elcid_guest_guide tools/call returned HTTP 200.
- Live A2A message/send returned HTTP 200 with EL CID Country Club content.
- Current MCP tool schemas accept no inputs; current guidance separates AUMARA but does not explicitly defend all legacy/entity collisions.

## Tests
Run the new manual verifier against https://www.elcidspain.com and require: Markdown negotiation; llms/skill discovery; MCP initialize/list/call; typed booking-intent echo without fabricated availability/price; A2A entity disambiguation; OAuth metadata; DNS-AID/DNSSEC evidence where externally resolvable.

## Stop condition
A draft PR contains the scoped hardening plus a verifier that passes against the branch-compatible implementation and documents any checks that remain production-only until merge/deploy.

## Recovery point
Branch: agent/elcid-runtime-hardening from main. Next safe action: update only the scoped EL CID files, run focused checks, then open one draft PR. Do not merge or deploy in this execution.
