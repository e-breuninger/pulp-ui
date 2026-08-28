# Configuration

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

## Behind a path prefix

Run uvicorn with `--root-path /ui` when the app is served under a subpath;
asset and link URLs follow it.
