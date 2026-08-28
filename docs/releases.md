# Releases

Releases are automatic. Every push to `main` runs commitizen over the commits
since the last tag and decides from their types whether a release is due:

| Commit types since the last tag | Result |
| --- | --- |
| A `feat` | Minor bump, e.g. 1.4.2 → 1.5.0 |
| A `fix` (and no `feat`) | Patch bump, e.g. 1.4.2 → 1.4.3 |
| Any `!` or `BREAKING CHANGE:` footer | Major bump, e.g. 1.4.2 → 2.0.0 |
| Only `docs`, `chore`, `ci`, `test`, `refactor` | No release; `edge` is rebuilt |

When there is one, CI bumps the version in `pyproject.toml` and `uv.lock`,
prepends the new section to [CHANGELOG.md](../CHANGELOG.md), commits that as
`bump: version X → Y`, pushes an annotated `vX.Y.Z` tag, publishes the images,
and opens a GitHub release whose notes are that changelog section plus the image
references.

The first run on a fresh repository seeds a `v0.1.0` tag on the initial commit,
because an incremental changelog needs a previous tag to generate from. After
that the tags come from the releases themselves.

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

## Published images

Images are published to `ghcr.io/e-breuninger/pulp-ui`:

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
