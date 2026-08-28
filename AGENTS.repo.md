# Agent notes

Context for AI coding agents working in this repository. Humans want
[CONTRIBUTING.md](CONTRIBUTING.md) instead.

## What this is

A read-only FastAPI UI over a Pulp server's REST API. Server-rendered Jinja2
templates, no database, no write path to Pulp.

## Layout

- `app/main.py` — routes, template/static wiring, the shared httpx client's lifespan
- `app/pulp_client.py` — every call to Pulp; the interesting logic lives here
- `app/config.py` — pydantic-settings; env vars are the only configuration
- `app/templates/`, `app/static/` — the UI
- `tests/fake_pulp/` — fixtures plus a standalone stub Pulp server

## Conventions

- Python 3.14, managed with `uv`. `uv sync` to install, `uv run pytest` to test.
- Comments say *why*, never *what*. Much of `pulp_client.py` documents real Pulp
  API quirks; do not delete those comments when refactoring, and add a
  regression test when you work around a new one.
- Settings are read once at import time. `tests/conftest.py` sets the required
  Pulp env vars before any test module imports `app.main`, and clears the
  optional branding ones so a developer's own setup can't change what renders.
- Nothing deployment-specific in the templates: no internal hostnames, links or
  company names. Those belong in `PULP_UI_CUSTOM_DIR`, whose templates shadow the
  bundled ones; see the Branding section of the README.
- A new bundled template is automatically overridable, but a new hardcoded asset
  path is not. Route branding through the `branding` context processor in
  `app/main.py`.
- Never commit `.env`. It holds real credentials and is gitignored.

## Verifying a change

```bash
uv run pytest
```

The suite mocks Pulp, so it needs no network and no live server.
