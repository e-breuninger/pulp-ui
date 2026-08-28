# Pulp UI

[![CI](https://github.com/e-breuninger/pulp-ui/actions/workflows/ci.yml/badge.svg)](https://github.com/e-breuninger/pulp-ui/actions/workflows/ci.yml)
[![Release](https://github.com/e-breuninger/pulp-ui/actions/workflows/release.yml/badge.svg)](https://github.com/e-breuninger/pulp-ui/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

This project is [**not** the Pulp UI](https://pulpproject.org/pulp-ui/) but a
custom built and very simple UI for developers.

It is a small, read-only FastAPI app that talks to a [Pulp](https://pulpproject.org/)
server's REST API and renders its distributions, content types and status as
plain server-rendered HTML. There is no database and no write path — point it at
a Pulp instance and it browses.

## Disclaimer

This UI was written with [Claude Code](https://claude.com/claude-code). Nearly
all of the code in this repository is AI-generated, reviewed by a human before
it landed and covered by the test suite — but reviewed code is not proven code.
Read it before you run it, and treat it as what it is: a small internal tool
published in case it is useful to someone else, not a product with a support
contract behind it. See the [MIT License](LICENSE) for the absence of warranty
in more formal terms.

Contributions made the same way are welcome; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Requirements

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A reachable Pulp server and credentials for it

## Development

1. `uv sync` to install all dependencies
2. `cp .env.example .env` and fill in your Pulp instance
3. Start the dev server:

    ```bash
    export $(cat .env)
    uv run uvicorn app.main:app --reload
    ```

Run the tests with `uv run pytest`. They mock the Pulp API, so no live server is
needed.

## Container

```bash
docker build -t pulp-ui .
docker run --rm -p 8081:8000 --env-file .env pulp-ui
```

Or `docker compose up --build`. Prebuilt images are published to
`ghcr.io/e-breuninger/pulp-ui`:

| Tag | Points at |
| --- | --- |
| `latest` | The most recent release. |
| `1.4.2`, `1.4`, `1` | A specific release, and the moving minor/major aliases. |
| `edge` | The tip of `main`, released or not. |
| `sha-<commit>` | One exact commit. |

Images are built for `linux/amd64` and `linux/arm64`, carry an SBOM and build
provenance, and are signed with cosign:

```bash
cosign verify ghcr.io/e-breuninger/pulp-ui:latest \
  --certificate-identity-regexp='^https://github.com/e-breuninger/pulp-ui/' \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

## Configuration

Everything is read from the environment.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `PULP_BASE_URL` | yes | — | Base URL of the Pulp instance, e.g. `https://pulp.example.com`. |
| `PULP_USERNAME` | yes | — | Pulp user for basic auth. |
| `PULP_PASSWORD` | yes | — | Password for that user. |
| `PULP_API_VERSION` | no | `v3` | Pulp REST API version segment. |
| `PULP_UI_CUSTOM_DIR` | no | — | Directory of templates and assets that override the bundled ones. |
| `PULP_UI_LOGO_URL` | no | bundled Pulp logo | URL used for the header logo and the favicon. |
| `PULP_UI_EXTRA_CSS_URL` | no | `custom.css` if present | Stylesheet loaded after the bundled one. |

## Branding

The UI ships deliberately generic and is meant to be labelled per deployment,
without forking it. Point `PULP_UI_CUSTOM_DIR` at a directory:

```text
custom/
├── footer.html          # replaces the bundled footer
├── index.html           # optional: replaces any bundled page
└── static/
    ├── custom.css       # picked up automatically, loaded last
    └── logo.svg
```

Nothing in it is required — every file is optional and falls back to the
bundled version. In a container, mount it read-only:

```bash
docker run --rm -p 8081:8000 --env-file .env \
  -v ./custom:/custom:ro -e PULP_UI_CUSTOM_DIR=/custom \
  -e PULP_UI_LOGO_URL=/custom-static/logo.svg \
  pulp-ui
```

### Templates

Any file in the directory shadows the bundled template of the same name. The
overridable ones are `base.html`, `footer.html`, `index.html`, `registry.html`,
`content_type.html` and `status.html`.

`footer.html` is the usual one to replace:

```html
<!-- custom/footer.html -->
<footer class="footer">
  <a href="https://wiki.example.com/pulp">Internal Docs</a>
  &middot;
  <a href="https://pulp.example.com/">Pulp Instance</a>
  &middot;
  Powered by Platform Engineering
</footer>
```

These are full Jinja2 templates, not plain snippets, so `{% extends %}`,
`{% block %}` and `{{ url_for(...) }}` all work. A page override that keeps the
surrounding chrome extends the bundled base:

```html
<!-- custom/index.html -->
{% extends "base.html" %}
{% block content %}
  <p>Ask #platform-support before deleting anything.</p>
  {{ super() }}
{% endblock %}
```

Keeping the `.footer`, `.topbar` and `.card` classes reuses the bundled styling;
dropping them gives you a blank slate.

### Styles

A `static/custom.css` in the directory is linked automatically, after the
bundled stylesheet, so its rules win. Re-theming is mostly a matter of
redefining the CSS variables from `app/static/style.css`:

```css
/* custom/static/custom.css */
:root { --brand: #005f73; --accent: #005f73; }
[data-theme="dark"] { --brand: #94d2bd; --accent: #94d2bd; }
```

Set `PULP_UI_EXTRA_CSS_URL` instead if the stylesheet lives somewhere else, such
as a CDN or a path served by a reverse proxy.

### Logo and favicon

Set `PULP_UI_LOGO_URL` to any URL; it is used for both the header mark and the
favicon. Files under the directory's `static/` are served at `/custom-static`,
so a logo shipped alongside the templates needs no separate hosting:

```bash
PULP_UI_CUSTOM_DIR=/custom
PULP_UI_LOGO_URL=/custom-static/logo.svg
```

## Releases

Releases are automatic. Every push to `main` runs commitizen over the commits
since the last tag and decides from their types whether a release is due:

| Commit types since the last tag | Result |
| --- | --- |
| A `feat` | Minor bump, e.g. 1.4.2 → 1.5.0 |
| A `fix` (and no `feat`) | Patch bump, e.g. 1.4.2 → 1.4.3 |
| Any `!` or `BREAKING CHANGE:` footer | Major bump, e.g. 1.4.2 → 2.0.0 |
| Only `docs`, `chore`, `ci`, `test`, `refactor` | No release; `edge` is rebuilt |

When there is one, CI bumps the version in `pyproject.toml` and `uv.lock`,
prepends the new section to [CHANGELOG.md](CHANGELOG.md), commits that as
`bump: version X → Y`, pushes an annotated `vX.Y.Z` tag, publishes the images,
and opens a GitHub release whose notes are that changelog section plus the image
references.

Nothing needs to be tagged or versioned by hand — the commit messages are the
input, which is why the format is enforced. To preview what the next release
would contain:

```bash
uv run cz bump --dry-run --changelog
```

The release workflow is skipped on forks, so contributing does not start
versioning or tagging your copy. Pull requests never trigger it either — a
release only ever happens from a push to `main` in this repository. A hard fork
that genuinely wants its own releases can drop the
`!github.event.repository.fork` guard on the `bump` job.

One repository setting this depends on: the workflow pushes the bump commit
straight to `main`, so if you protect the branch, allow the
`github-actions[bot]` actor to bypass it. Publishing itself needs no secrets —
GHCR authenticates with the built-in `GITHUB_TOKEN`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
