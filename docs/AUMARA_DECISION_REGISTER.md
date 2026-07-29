# AUMARA Decision Register

This register contains decisions already made by the authorised AUMARA strategy committee. It is not a monitoring list and it is not a discussion log. Each active decision is a durable source of authority for downstream architecture, projects, execution packets, tasks, evidence, and metrics.

## Decision statuses

- `ACTIVE` — in force and must be implemented.
- `SUPERSEDED` — replaced by a later decision.
- `REVOKED` — explicitly cancelled.
- `COMPLETE` — fully implemented and evidenced; the resulting operating rule remains in force where applicable.

---

## AUMARA-SD-001 — Unified AUMARA Command Center

**Decision date:** 2026-07-29  
**Status:** ACTIVE  
**Authority:** AUMARA Strategy Committee  
**Decision class:** Strategic operating model

### Decision

AUMARA will operate through one unified control plane that converts signals from physical operations, people, connected systems, documents, communications, and financial/legal processes into structured state, owned actions, verified evidence, and role-appropriate views.

The target operating flow is:

`Signal -> Structured Record -> Owner -> Next Action -> Verification -> State Update -> Role-Based View`

The company will move away from fragmented chat-based monitoring as the primary operating interface. Chats and notifications remain delivery channels for exceptions, approvals, incidents, and urgent decisions; they are not the system of record.

### Strategic intent

Increase monetisation through repeatable value by reducing lost signals, context reconstruction, manual coordination, decision latency, operating cost, and execution error.

### Required capabilities

1. One durable current operating state.
2. One decision register.
3. One execution queue linked to decisions.
4. One evidence trail for completed work.
5. Role-based views for shareholders, committee members, managers, specialists, staff, and authorised external participants.
6. A mobile-first `Today` view and an anonymised wallboard view.
7. Separate status and health reporting for Bitrix24 and Beds24.
8. Event capture for commercial enquiries, guest requests, operational exceptions, deadlines, incidents, financial issues, legal/tax matters, menu and purchasing work, staffing, and technical automation.
9. Deduplication, ownership, next action, deadline, value hypothesis, evidence source, freshness, and escalation for every structured item.
10. Protected external writes remain subject to explicit authorisation.

### Source systems currently recognised

- Beds24 — PMS and booking operations.
- Bitrix24 — CRM and commercial workflow.
- Gmail — communications and inbound signals.
- Google Calendar — events, shifts, deadlines, and filings.
- Google Drive / Sheets — documents, reporting, calculations, and operating evidence.
- EPOS — restaurant sales and transaction data.
- GitHub — code, policies, execution evidence, and recovery points.
- AUMARA Staff — onsite work and shift execution.
- Airtable Control Tower — existing structured operational registries where already implemented.

These systems are capabilities and data sources. None of them alone is the AUMARA operating system.

### Initial implementation sequence

1. Confirm and map existing sources, registries, automations, dashboards, and duplicate monitors.
2. Define the canonical operating-state schema and source-of-truth rules.
3. Produce a read-only Command Center prototype with `Today`, `Executive`, `Operations`, and `Wallboard` views.
4. Connect existing sources incrementally, beginning with read-only status and freshness.
5. Add execution actions only after each write path is separately reviewed and authorised.
6. Measure context compression, human intervention, decision latency, signal-to-action conversion, and verified value per cycle.

### Immediate execution packets authorised

- `EP-001` — Current-state and source inventory.
- `EP-002` — Canonical operating-state schema.
- `EP-003` — Read-only Command Center visual prototype.

### Success criteria

- An authorised user can open one mobile page and understand the current company state without reconstructing it from chats.
- Each material signal has an owner, next action, status, deadline, source, and evidence.
- The system distinguishes verified, stale, blocked, and unknown information.
- Managers receive exceptions and decisions rather than repeated raw monitoring messages.
- Every implementation item can be traced back to this decision and forward to evidence and measurable value.

### Boundaries

This decision does not itself authorise sending messages, changing bookings, filing tax returns, making payments, changing access, creating credentials, deploying production systems, or modifying legal data.

### Durable links

- Strategic doctrine: `docs/AUMARA_STRATEGY_COMMITTEE.md`
- Current state: `docs/AUMARA_CURRENT_OPERATING_STATE.md`
- Execution packet template: `docs/AUMARA_EXECUTION_PACKET.md`
- Repository execution policy: `docs/AI_EXECUTION_POLICY.md`
- Checkpoint protocol: `docs/CHECKPOINT_PROTOCOL.md`
