# AUMARA domain lock

Canonical:
- `elcidspain/aumara` → Vercel project `aumara-path-cut` → `aumara.me`
- `openai-cookbook` → EL CID on `elcidspain.com` only → never attach AUMARA domains

Current physical state (2026-09-05):
- `aumara.me` + `www.aumara.me` are still aliases of `aumara-path-0827`
  (`prj_oVEHTsPMmVXduhJkXrRmMwDioA5B`), which remains git-linked to this repo.
- Production on 0827 is a reverse-proxy rewrite onto
  `https://aumara-path-cut.vercel.app` so the ads domain serves the real twin
  (flight, walkthrough, houses, Beds24 324882) until aliases can be moved.
- `ignoreCommand: exit 0` MUST stay. A git deploy from this repo onto 0827
  would overwrite AUMARA again.

Do not remove `ignoreCommand` while 0827 holds `aumara.me`.
Do not attach `aumara.me` to this repository's Vercel project.
Country Club lives on elcidspain.com only.
