# AUMARA domain lock

Canonical:
- `elcidspain/aumara` → Vercel project `aumara-path-cut` → `aumara.me`
- `openai-cookbook` → EL CID on `elcidspain.com` only → never attach AUMARA domains

Current physical state (2026-09-20):
- `aumara.me` + `www.aumara.me` are production aliases of `aumara-path-cut`
  (`prj_0Xoh6tbXYwqvlkN7jk4rSRnxgbkt` → `elcidspain/aumara`).
- `aumara-path-0827` no longer holds those domains. It stays git-linked to
  this repo; `ignoreCommand: exit 0` MUST stay so a cookbook push cannot
  become an AUMARA site build.
- Hold: do not retry failed path-cut production deploys from this repo, do
  not attach `aumara.me` here, do not add more routing rules beyond ACP.

Do not attach `aumara.me` to this repository's Vercel project.
Country Club lives on elcidspain.com only.
