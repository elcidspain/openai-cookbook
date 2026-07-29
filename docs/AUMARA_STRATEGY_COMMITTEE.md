# AUMARA Strategy Committee Operating System

## Purpose

AUMARA is the control plane above its tools, connectors, people, agents, assets,
and legal entities. Tools are capabilities; they are not the operating system.

Strategy Committee decisions are executable commitments. A decision is not
complete when it is discussed or documented. It is complete only when it is
translated into an execution packet, assigned, verified, and reflected in the
current operating state.

## Core doctrine

**Monetization is the consequence of repeatable value.**

Repeatability does not mean repeating the same words or the same task. It means
that any selected value-producing action can be executed again with:

- lower cost;
- less context;
- fewer errors;
- shorter decision latency;
- stronger evidence;
- less human intervention;
- a better recovery point for the next cycle.

AUMARA reduces entropy through the following loop:

`Signal -> Decision -> Execution Packet -> Action -> Verification -> State Update -> Next Cycle`

The system must increase verified value per cycle. A PR, document, model, email,
or automation is evidence or infrastructure; it is not value by itself unless it
improves revenue, reduces operating cost or risk, shortens execution, or creates
a reusable capability.

## Roles and accountability

### Human principal / shareholder committee

- sets strategic intent and protected-action approvals;
- chooses risk appetite and capital allocation;
- resolves decisions that cannot be delegated safely;
- does not need to reconstruct already verified operational context.

### Lead manager / control-tower agent

- owns the current operating state;
- converts committee decisions and incoming signals into bounded execution
  packets;
- delegates to specialist agents and connected systems;
- verifies results rather than accepting untested claims;
- updates the state and recovery point after every completed action;
- escalates only decisions that require human authority or judgment;
- remains accountable for coordination even when execution is delegated.

If the lead manager states that a fact, decision, or recovery point will be
remembered, it must be written to an approved durable source. Conversation alone
is not durable memory.

### Specialist agents and external participants

- receive one execution packet at a time;
- operate only inside the packet scope;
- return evidence, blockers, and a recovery point;
- do not broaden scope or create adjacent work without a new decision.

### Connectors and tools

Connected tools should be treated as available capabilities and used directly
when needed. Capability does not equal authorization: protected writes still
require the approval rules in `AI_EXECUTION_POLICY.md`.

## Decision lifecycle

1. **Capture the signal.** A guest request, commercial enquiry, deadline,
   operational exception, financial issue, or strategic idea becomes a durable
   item rather than remaining in conversation.
2. **Classify value.** State how the item can increase revenue, reduce cost,
   reduce risk, improve conversion, or create a reusable capability.
3. **Decide.** Record owner, priority, authorization boundary, and success
   measure.
4. **Issue a packet.** Use `AUMARA_EXECUTION_PACKET.md`. A packet must fit on one
   page; otherwise the task must be split.
5. **Execute and verify.** Use focused evidence and deterministic checks where
   possible.
6. **Update state.** Record the verified outcome, remaining blocker, and exact
   recovery point in `AUMARA_CURRENT_OPERATING_STATE.md` or the approved live
   state store.
7. **Measure the cycle.** Record value, cost, context, elapsed time, errors, and
   human interventions when practical.

## Commercial signal rule

Every credible commercial signal must become a structured opportunity or task.
Examples include a guest asking the price of a house, an enquiry about a stay,
a request for a different room, a retreat lead, a food-and-beverage request, or
an upsell opportunity.

Minimum fields:

- source and timestamp;
- person or organisation;
- requested asset or service;
- dates, quantity, and stated constraints when known;
- estimated value or value hypothesis;
- owner and next action;
- decision deadline;
- deduplication key;
- evidence link;
- status.

No commercial signal should depend on the shareholder remembering it manually.

## Operating cadence

### Event driven

- capture new guest, commercial, operational, legal, tax, and financial signals;
- deduplicate and route them;
- execute safe read-only classification automatically;
- escalate protected writes or ambiguous decisions.

### Daily

Publish a compact red/amber/green control-tower status covering:

- guest and commercial exceptions;
- Gmail and communication queue;
- Beds24 and Bitrix24 status, reported separately;
- automation and integration health;
- reporting and filing deadlines;
- menu, pricing, inventory, and sales-readiness blockers;
- open execution packets, failed checks, and recovery points;
- the single highest-leverage next action.

### Weekly Strategy Committee

Review only changes, decisions, risks, value produced, and blocked items. Do not
reconstruct stable context or repeat the entire project history.

## Systems boundary: Bitrix24 is not Beds24

- **Bitrix24 / B24** is the CRM and commercial workflow system.
- **Beds24** is the PMS/channel-management and booking system.

Their credentials, scopes, health checks, queues, and write permissions must be
reported separately. A successful Beds24 authentication check does not prove
Bitrix24 connectivity.

## Metrics

The committee tracks outcomes rather than activity volume:

- **Verified Value per Cycle** — revenue, savings, risk reduction, or reusable
  capability supported by evidence;
- **Cost per Verified Result** — total execution cost for one accepted outcome;
- **Context Compression Ratio** — context required now divided by the context
  previously required for an equivalent verified result;
- **Human Intervention Rate** — manual corrections or escalations per completed
  cycle;
- **Decision Latency** — time from signal capture to authorised decision;
- **Signal-to-Action Conversion** — credible signals converted into owned,
  time-bound next actions;
- **Recovery Quality** — whether another authorised agent can resume without
  repeating completed investigation.

## Decisions currently in force

1. Monetization through repeatable value is the strategic objective.
2. Every committee decision must become an owned execution packet or an explicit
   rejected/deferred decision.
3. Every credible commercial signal must be captured, deduplicated, assigned,
   and followed through.
4. Daily operational status is required; the shareholder should not need to ask
   repeatedly what is happening.
5. Modelo 200 and other statutory deadlines are managed as time-critical
   operational risks, with evidence-based status and no unauthorised filing.
6. Menu, pricing, inventory, property presentation, and guest-facing assets are
   commercial infrastructure and must have owners, readiness criteria, and next
   actions.
7. Connected systems should be used as capabilities, but external writes,
   payments, filings, access changes, credentials, bookings, and messages remain
   protected actions.
8. Verified facts are reused. Unverified assumptions are labelled. Repeated
   investigation requires evidence that the existing recovery point is
   insufficient.
9. The lead manager is accountable for durable memory, delegation, verification,
   and state updates.
10. Committee decisions remain in force until explicitly superseded.

## Relationship to existing governance

This document defines the stable strategic and operating doctrine. It does not
replace:

- `AI_EXECUTION_POLICY.md` — task scope and authorisation boundaries;
- `CHECKPOINT_PROTOCOL.md` — durable handoff for one execution;
- `AUMARA_EXECUTION_PACKET.md` — one-page task contract;
- `AUMARA_CURRENT_OPERATING_STATE.md` — rolling verified state and priorities.
