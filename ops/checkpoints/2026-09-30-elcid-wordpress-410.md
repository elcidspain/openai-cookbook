# Checkpoint: EL CID stale WordPress 410s

| Field | Content |
| --- | --- |
| Objective | Return 410 for the approved stale indexed WordPress URLs on elcidspain.com, in one hop, without other site changes |
| Status | in progress |
| Scope | `vercel.json` routing only, `elcid-site/gone.txt`, route assertions in `elcid-site/check_site.py`. No page copy, no legal/privacy/cookies changes, no Beds24, Gmail, or project settings |
| Evidence | Production HEAD probe on 2026-09-30: listed paths were 404, trailing-slash forms were 308 to the 404. Indexed paths from the 2026-09-30 evening capture plus DuckDuckGo: `/about-us`, `/terms-conditions`, `/shop` (+ `/shop/cart`), `/en-gb/rooms`, `/ru-ru` and subpaths, `/experiences`, `/wine-club`, `/terroirs`, `/demo-design-system`, `/nuestra-historia`, `/restaurant-menu`, `/es-es/booking`, `/2025/07/31/hello-world`, `/2021/05/02/post001`, `post002`, `post003`, `/2021/05/03/post008`, `/product/seven-case-2`, `/product-category/uncategorized`. No distinct live successor URL, so none are 301s. Live pages remain `/`, `/legal.html`, `/privacy.html`, `/cookies.html` |
| Changes | 410 routes before a preserved trailing-slash 308. `trailingSlash: false` removed because that platform redirect ran before project routes and forced `308` then `404` |
| Tests | `python3 elcid-site/check_site.py` PASS. Preview `curl -I` on `https://openai-cookbook-46497ilcj-elidspaincom.vercel.app` (`dpl_8dnybPNzNP5bit3nhaZ5SCaQDU5S`, commit `f8056f35`): stale paths 410 in one hop; `/`, `/legal.html`, `/privacy.html`, `/cookies.html` 200; `/legal/` 308 to `/legal`; `/aumara` 308 to `https://www.aumara.me/`; `/en` and `/contact` stay 404. Production `curl -I` still pending |
| Stop condition | Merge to `main`, then the same `curl -I` list on `https://www.elcidspain.com` |
| Recovery point | Branch `cursor/elcid-stale-wordpress-410-6442`, PR https://github.com/elcidspain/openai-cookbook/pull/168. Do not reintroduce `trailingSlash: false` ahead of the 410 routes |
