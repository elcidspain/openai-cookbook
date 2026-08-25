# Copilot Instructions for openai-cookbook

This repository contains runnable examples, notebooks, and reference articles for OpenAI APIs. Keep changes focused, minimal, and aligned with the existing cookbook structure.

## Repository structure

- Place notebooks and Python scripts under `examples/<topic>/`.
- Group related assets inside topic-specific subfolders and keep filenames descriptive and lowercase with dashes or underscores.
- Keep content discoverable by updating `registry.yaml` for new or relocated entries.
- Keep author metadata current in `authors.yaml` when adding or moving content.

## Coding and documentation expectations

- Write Python to PEP 8 with four-space indentation, descriptive names, and concise docstrings.
- Prefer clear examples over clever abstractions; document required environment variables instead of hard-coding secrets or API keys.
- Avoid introducing network calls in tests; use fakes or mocks where appropriate.
- For notebook changes, run them top-to-bottom and clear execution counts before committing.

## Validation and workflow

- Use a virtual environment for local work and install only the dependencies required by the relevant example.
- Validate notebooks with:
  - `python .github/scripts/check_notebooks.py`
- If a sample includes dependencies, use the example-specific `requirements.txt` rather than installing unrelated packages.

## Security and governance

- Never place secrets or private operational values in code, prompts, logs, commits, or pull request text.
- Do not change Gmail, Beds24, monitoring, deployment, access, payments, legal, tax, or external messaging without explicit task-specific authorization.
- Follow `docs/AI_EXECUTION_POLICY.md` and `docs/CHECKPOINT_PROTOCOL.md` for AI-assisted execution.

## AUMARA Beds24 authentication canon

For AUMARA / EL CID Beds24 automation, use API credentials as the default and authoritative authentication path.

- **Beds24 API v2 / bearer-token path:** use `BEDS24_REFRESH_CREDENTIAL` through the existing refresh/token exchange flow. Treat this value only as a Beds24 API refresh credential; never repurpose it as an encryption key, KEK, password vault key, or browser-login secret.
- **Beds24 legacy JSON/content endpoints:** when an existing endpoint still uses legacy authentication, use `BEDS24_API_KEY` together with `BEDS24_PROP_KEY`.
- **Do not use `BEDS24_PASSWORD` or `BEDS24_USERNAME` as an automation fallback.** They are not part of the canonical API execution path. Do not reset, rotate, request, or troubleshoot the Beds24 password unless the task explicitly requires an interactive Beds24 control-panel login and separately authorizes credential changes.
- If a requested Beds24 operation is not exposed through the available API path, stop with a precise `UI-only` blocker instead of attempting password/browser fallback.
- Do not tell the operator to change Beds24 credentials merely because an API operation failed. First inspect the existing token/refresh flow and the exact endpoint/auth mode already used by the project.
- Preserve credential names exactly as configured in GitHub Secrets/Environment; never print or commit secret values.

This section is the canonical project instruction for Beds24 authentication and overrides older ad-hoc browser-login workflows or password-based fallbacks.

## Pull request expectations

- Use concise, imperative commit messages.
- Include a short summary, motivation, and validation details in pull requests.
- Ensure metadata files stay in sync with new or relocated content.
