# AUMARA Control Tower

This folder is the first operational kernel for AUMARA execution work.

Purpose:
- keep context structured;
- turn work into small command packets;
- preserve decisions and review trails;
- separate intent, execution, and approval.

Operating rule:
The human owner keeps intent and responsibility. Tools execute bounded tasks. Every important output should be reviewable.

Initial folders:
- docs
- prompts
- issues
- workflows

Status: Phase 0 initialized.

---

## Operating Formula

Owner of intent -> Control Tower -> bounded agent task -> review -> merge / release.

No magic. No waiting. No chaos.

## Immediate Backlog

1. Build repository skeleton.
2. Write control tower manifest.
3. Write agent rules.
4. Write Copilot / Claude execution prompt.
5. Create X / Twitter reply workflow archive.
6. Create AUMARA / EL CID command packet index.
7. Define document intake flow.
8. Define review and approval rules.

## Agent Rules Draft

- Give the agent a bounded task, not the whole project.
- Include context, expected output, constraints, and acceptance criteria.
- Require a reviewable result.
- Never treat agent output as final without human approval.
- Keep the source of truth in GitHub / Drive, not in a disappearing chat.

## First Command Packet Template

```md
# Command Packet

## Objective

## Context

## Inputs

## Constraints

## Output Required

## Acceptance Criteria

## Review Notes
```
