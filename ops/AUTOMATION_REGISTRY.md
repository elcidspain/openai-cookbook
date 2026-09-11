# AUMARA Automation Registry

Cutover packet: `OPS_AUTOMATION_HYGIENE_001`

This registry records only the workflows classified by this cleanup. Other workflows remain unchanged and are not implicitly reclassified.

## ACTIVE / protected from this cleanup

- `.github/workflows/beds24-aumara-access-audit.yml` — current AUMARA read-only access audit.
- `.github/workflows/aumara-beds24-continuous-notes.yml` — existing notes path; untouched.
- `.github/workflows/beds24-guest-message-ingest.yml` — manual read-only guest-message proof.
- `.github/workflows/beds24-elcid-auto-replies.yml` — manual no-send reply audit.

## MANUAL / ON DEMAND

- `.github/workflows/beds24-photo-sync-discovery.yml` — `workflow_dispatch` retained; 5-minute cron removed.
- `.github/workflows/beds24-binding-inventory.yml` — `workflow_dispatch` retained; 5-minute cron removed.
- `.github/workflows/beds24-finance-snapshot.yml` — retained for manual use; date parameterization is a separate change.

## ONE-SHOT / pending reference audit

Kept live in this packet to avoid breaking an unknown manual control path:

- `.github/workflows/beds24-binding-inventory-controller.yml`
- `.github/workflows/beds24-photo-sync-controller.yml`
- `.github/workflows/beds24-live-recovery-dispatch-controller.yml`

## ARCHIVED / non-runnable

All workflow files with explicit historical suffixes `20260823` or `20260825` were moved from `.github/workflows/` to `ops/archive/github-actions/2026-08/` without content changes. Their Git history and blob contents remain preserved, but GitHub Actions will no longer load them as live workflows.

## Guardrails

- No guest/runtime Beds24 workflow was modified by this packet except the two discovery/inventory schedules above.
- No credentials or secret values are copied into this registry.
- No deployment is triggered by this registry.
- Re-enable an archived workflow only by an explicit PR that restores it to `.github/workflows/` and documents why it is still operationally required.
