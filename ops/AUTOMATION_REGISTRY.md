# AUMARA Automation Registry

Cutover packets: `OPS_AUTOMATION_HYGIENE_001`, `OPS_AUTOMATION_HYGIENE_P1`.

This registry records only the workflows classified by these cleanup packets. Other workflows remain unchanged and are not implicitly reclassified.

## ACTIVE / protected from this cleanup

- `.github/workflows/beds24-aumara-access-audit.yml` — current AUMARA read-only access audit.
- `.github/workflows/aumara-beds24-continuous-notes.yml` — existing notes path; untouched.
- `.github/workflows/beds24-guest-message-ingest.yml` — manual read-only guest-message proof.
- `.github/workflows/beds24-elcid-auto-replies.yml` — manual no-send reply audit.

## MANUAL / ON DEMAND

- `.github/workflows/beds24-photo-sync-discovery.yml` — `workflow_dispatch` retained; 5-minute cron removed in P0.
- `.github/workflows/beds24-binding-inventory.yml` — `workflow_dispatch` retained; 5-minute cron removed in P0.
- `.github/workflows/beds24-finance-snapshot.yml` — retained for manual use; date parameterization is a separate change.
- `.github/workflows/beds24-ui-photo-upload-handshake.yml` — direct manual UI handshake remains available; the mislabeled issue-controller wrapper is archived in P1.
- `.github/workflows/beds24-photo-sync-vault-controller.yml` — direct manual photo-vault transfer remains available; P1 intentionally narrowed this workflow to manual `workflow_dispatch` only and removed issue-driven dispatch.

## RECOVERY / EXISTING

- `.github/workflows/beds24-recover-live-exchange-artifacts.yml` — direct recovery workflow retained unchanged in P1. It still has `workflow_dispatch` plus its existing file-scoped `push` trigger on changes to that workflow itself; no issue-controller wrapper remains live.

## ARCHIVED / non-runnable

P1 moved these legacy issue-driven controller wrappers out of `.github/workflows/` with byte-identical blobs:

- `beds24-binding-inventory-controller.yml`
- `beds24-photo-sync-controller.yml`
- `beds24-live-recovery-dispatch-controller.yml`

P0 moved all workflow files with explicit historical suffixes `20260823` or `20260825` to `ops/archive/github-actions/2026-08/` without content changes. Git history and blob contents remain preserved, but GitHub Actions no longer loads archived files as live workflows.

## Guardrails

- No guest-message workflow is changed by P1.
- P1 intentionally narrows the photo-vault runtime workflow to manual dispatch only; it does not execute that workflow.
- No booking, rate, property, photo, or credential mutation is performed by the cleanup itself.
- No credential or secret value is copied into this registry.
- No deployment is triggered by this registry.
- Re-enable an archived workflow only by an explicit PR that restores it to `.github/workflows/` and documents why it is still operationally required.
