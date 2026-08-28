# Contributing

Thanks for taking the time. This is a small project, so the process is short.

## Ground rules

- By contributing you agree that your work is licensed under the
  [MIT License](LICENSE), the same terms as the rest of the project.
- Be civil. Assume the person on the other side is trying to help.

## AI-assisted contributions

Explicitly welcome. Generated code is judged by the same standard as
hand-written code, which in practice means:

- **It must be tested.** Ship tests that actually exercise the new behaviour and
  would fail without it. A PR whose tests only assert what the code trivially
  does is not tested.
- **You must understand it.** You are the author of what you open a PR with. Be
  able to explain why it works and what happens when it doesn't.
- **Check the invented parts.** Confirm the Pulp API fields, endpoints and
  library APIs it uses are real — plausible-looking ones that don't exist are
  the common failure mode here.
- Say in the PR description that a tool was involved. It is not held against
  you; it just tells reviewers where to look harder.

Unreviewed bulk output opened without running the tests will be closed.

## Reporting bugs and asking for features

Open an issue at
<https://github.com/e-breuninger/pulp-ui/issues>. For a bug, please include:

- what you did, what you expected, what happened instead
- the Pulp version you point the UI at, if relevant
- the relevant log output — but scrub URLs, usernames and passwords first

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and
Python 3.14.

```bash
uv sync
cp .env.example .env   # fill in a Pulp instance you can reach
export $(cat .env)
uv run uvicorn app.main:app --reload
```

Run the tests — they mock the Pulp API, so no live server is needed:

```bash
uv run pytest
```

Install the git hooks once, so linting and the commit-message check run locally
rather than failing in CI:

```bash
uv run pre-commit install
```

`tests/fake_pulp/` additionally provides a standalone stub server if you want to
click through the UI without a real Pulp.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
The commit-msg hook enforces it locally and CI re-checks every commit in a PR,
because hooks can be skipped and fork PRs never ran them.

```text
<type>[(optional scope)][!]: <description>

[optional body]
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`.
Scopes are free-form; `pulp-client`, `templates` and `deps` are the ones in use.

```text
feat(templates): let deployments override the footer
fix(pulp-client): follow http to https redirects from the gateway
docs: document the branding directory
```

The description is lower case, imperative and has no trailing period. Mark a
breaking change with `!` before the colon, or a `BREAKING CHANGE:` footer.

`uv run cz commit` walks you through it interactively if you'd rather not
remember the format.

## Pull requests

- Branch off `main` and keep one logical change per PR.
- Add or update tests for behaviour you change. New Pulp API quirks in
  `app/pulp_client.py` in particular should come with a regression test —
  several of the existing ones exist because a real Pulp returned something
  surprising.
- Keep to the surrounding style: comments explain *why* something is the way it
  is, not what the line does. Skip the comment if there is no why.
- Run `uv run pytest` before pushing. CI runs the same suite.
- If you add a dependency, commit the updated `uv.lock`.

## Releases

You do not need to bump a version, write a changelog entry or push a tag — all
three are derived from the commit messages when your PR lands on `main`. The
release workflow does not run on forks, so your copy stays untouched. See
[docs/releases.md](docs/releases.md) for which types release what.

The practical consequence: pick the type honestly. A `fix` on a user-visible bug
ships a patch release; the same change labelled `chore` ships nothing.

## What tends to get rejected

- Deployment-specific branding, hostnames or links in the templates. Those
  belong in `PULP_UI_CUSTOM_DIR` — see [docs/configuration.md](docs/configuration.md).
- Write operations against Pulp. This UI is deliberately read-only.
