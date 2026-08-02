# Policy Registry

This directory is the versioned policy boundary for the separate AUMARA and
EL CID guest products.

- `registry.yaml` pins one policy version and the three registry files.
- `shared.yaml` contains only cross-product safety and governance rules.
- `elcid.yaml` contains EL CID facts, reply fragments, action policy and source references.
- `aumara.yaml` contains AUMARA policy placeholders and source references.
- `schema.json` is the shared machine-readable schema.
- `../scripts/guest_reply_policy_runtime.py` loads verified EL CID reply fragments and fails closed on policy-version drift.

The `.yaml` files use JSON-compatible YAML so validation requires only the
Python standard library. Private operational values, guest data, credentials,
property identifiers, inventory identifiers, fees, and contact details must
not be committed. Store only approved source references or `PENDING`
placeholders, then resolve private values in the authorized runtime.

`pending` and `conflict` entries must keep both automation fields disabled.
Policy and template identifiers must remain inside their property namespace.
A reply template may be used only when its policy is `verified`,
`allowed_auto_reply` is true, and the runtime policy version exactly matches
`registry.yaml`.

The ChatGPT automation prompt must declare the same policy version as the
registry snapshot. A delivery failure changes only delivery state; it must not
rewrite the approved reply or restore a stale generic template.

Validate locally:

```bash
python aumara-control-tower/scripts/validate_policy_registry.py
python -m unittest discover \
  -s aumara-control-tower/tests \
  -p 'test_policy_registry_schema.py'
python -m unittest discover \
  -s aumara-control-tower/tests \
  -p 'test_guest_reply_policy_runtime.py'
```

To update the registry, change all affected files to one new
`policy_version`, record the change in `CHANGELOG.md`, update the automation
snapshot version, and keep unresolved or conflicting facts fail-closed.
