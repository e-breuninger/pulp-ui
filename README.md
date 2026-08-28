# Pulp UI

[![CI](https://github.com/e-breuninger/pulp-ui/actions/workflows/ci.yml/badge.svg)](https://github.com/e-breuninger/pulp-ui/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A small, read-only web UI for browsing a [Pulp](https://pulpproject.org/)
server: its distributions, cached content and status. No database, no write path
to Pulp.

> This is **not** the official [Pulp UI](https://pulpproject.org/pulp-ui/). It is
> an unrelated, much simpler tool built for our developers, and it was written
> with [Claude Code](https://claude.com/claude-code) — read it before you run it.

## Running it

```bash
docker run --rm -p 8081:8000 \
  -e PULP_BASE_URL=https://pulp.example.com \
  -e PULP_USERNAME=admin -e PULP_PASSWORD=secret \
  ghcr.io/e-breuninger/pulp-ui:latest
```

Those three variables are all that is required. The UI is then on
<http://localhost:8081>.

Everything else is optional: the footer, logo and stylesheet can be replaced per
deployment without forking. See [docs/configuration.md](docs/configuration.md).

## Developing it

Needs [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync                       # install dependencies
uv run pre-commit install     # lint and commit-message hooks
cp .env.example .env          # point at a Pulp you can reach
export $(cat .env)
uv run uvicorn app.main:app --reload
```

`uv run pytest` runs the suite; it mocks the Pulp API, so no live server is
needed. `tests/fake_pulp/` also serves a stub Pulp if you want to click through
the UI without credentials.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request — commit
messages follow [Conventional Commits](https://www.conventionalcommits.org/) and
are enforced. Releases are automatic: [docs/releases.md](docs/releases.md).

Licensed under the [MIT License](LICENSE).
