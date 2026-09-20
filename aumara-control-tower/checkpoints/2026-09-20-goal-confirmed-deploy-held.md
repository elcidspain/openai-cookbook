# Checkpoint: goal confirmed, deploy held

Status: complete

## Confirmed live (2026-09-20)

- `https://aumara.me/` → 200 HTML
- `https://www.aumara.me/` → 200 HTML
- `GET /.well-known/oauth-protected-resource` on apex → 200, `resource=https://aumara.me`
- `GET /.well-known/acp.json` on apex and www → 200 JSON, `protocol.name=acp`, `checkout_mode=human-mediated-only`
- Beds24 V1 run `35383953766`: `SUCCESS`, opened Fully flexible + Weekly. Fully flexible has Booking code `66887702`. Weekly has no `bookingcomRateCode`.

## Deploy hold

- `aumara.me` + `www.aumara.me` stay on `aumara-path-cut` only.
- `aumara-path-0827` does not hold those domains. Do not attach them to openai-cookbook.
- No new path-cut production deploy. Latest READY remains `dpl_6o4qWVmaQCVy5Yyth2Zs3QH7rniE` (`elcidspain/aumara` `1c32c1bb`). A later production attempt `dpl_H56VjbNFFC7in8fw8EQJpbpLs41x` is ERROR — do not retry from this cookbook execution.
- ACP is one Vercel routing rule on path-cut (`9e36be73-6fab-4d6e-8b5d-264871a0d3bb`), dest pinned to git SHA `c3043eb0`. No extra routes.

## Residual (not a deploy)

- V2 channels scope still missing.
- Weekly still needs a Booking rate id for a distinct extranet plan.
