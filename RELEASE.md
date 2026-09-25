<!--
  ~ Copyright (c) 2025-2026 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

# Releasing MCP Compose

Pushing a version tag releases MCP Compose. The tag `v1.0.0` publishes
`mcp-compose` 1.0.0 to PyPI, pushes the `datalayer/mcp-compose:1.0.0` and
`datalayer/mcp-compose:latest` Docker images, and creates the GitHub release.

The workflow is [`.github/workflows/release.yml`](.github/workflows/release.yml).

## Release steps

1. **Bump the version** in [`mcp_compose/__version__.py`](mcp_compose/__version__.py)
   and merge that change to `main` through a pull request.

   ```python
   __version__ = "1.0.0"
   ```

2. **Tag the merged commit and push the tag.**

   ```bash
   git checkout main
   git pull origin main
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Watch the run** on the [Actions tab](https://github.com/datalayer/mcp-compose/actions/workflows/release.yml).
   If the `pypi` environment has required reviewers, approve the
   `Publish to PyPI` job when it waits for review.

4. **Check the results**:
   - PyPI: https://pypi.org/project/mcp-compose/
   - Docker Hub: https://hub.docker.com/r/datalayer/mcp-compose/tags
   - GitHub release: https://github.com/datalayer/mcp-compose/releases

The tag must equal `v` + `__version__`. If they differ, the workflow fails
before anything is built or published, so a mistyped tag publishes nothing.

## What the workflow does

| Job | What it does |
| --- | --- |
| `Build Python Package` | Checks the tag against `__version__`, builds the UI (Node.js 20) and the sdist and wheel, runs `twine check --strict`, checks that the wheel includes `mcp_compose/ui/dist/index.html`, and installs the wheel in a fresh venv as a smoke test. |
| `Publish to PyPI` | Publishes `dist/*` with [trusted publishing](https://docs.pypi.org/trusted-publishers/), which uses OIDC and needs no API token. Runs in the `pypi` environment. |
| `Build and Push Docker Image` | Builds the [`Dockerfile`](Dockerfile) for `linux/amd64` and `linux/arm64` and pushes `datalayer/mcp-compose:<version>` and `datalayer/mcp-compose:latest`. |
| `Create GitHub Release` | Creates the release for the tag, with generated notes and the sdist and wheel attached. Runs after both publish jobs succeed. |

`Publish to PyPI` sets `skip-existing: true`. You can therefore re-run a failed
release, for example after a Docker Hub error, and files already on PyPI are
skipped instead of failing the run.

## One-time setup

### PyPI: add the trusted publisher

A PyPI owner of the `mcp-compose` project does this once:

1. Go to https://pypi.org/manage/project/mcp-compose/settings/publishing/.
2. Under **Add a new publisher**, choose **GitHub** and enter:

   | Field | Value |
   | --- | --- |
   | Owner | `datalayer` |
   | Repository name | `mcp-compose` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. Click **Add**.

PyPI then accepts uploads only from the `release.yml` workflow of
`datalayer/mcp-compose`, and only when it runs in the `pypi` environment. No
PyPI API token is stored in GitHub. If an old `PYPI_TOKEN`-style secret exists
for this project, you can revoke it after the first release succeeds.

The environment name must match exactly. If it differs, the upload fails with
`invalid-publisher`.

### GitHub: create the `pypi` environment

1. Go to **Settings → Environments → New environment** and name it `pypi`.
2. Recommended protections:
   - **Deployment branches and tags**: choose **Selected branches and tags**
     and add the tag rule `v*`, so only release tags can deploy.
   - **Required reviewers**: add the maintainers who approve releases.

### Docker Hub: add the push credentials

1. In Docker Hub, go to **Account settings → Personal access tokens** and
   create a token with **Read & Write** access. Use an account that can push to
   `datalayer/mcp-compose`.
2. In GitHub, go to **Settings → Secrets and variables → Actions** and add
   these repository secrets (organization secrets also work):
   - `DOCKERHUB_USERNAME`: the Docker Hub username
   - `DOCKERHUB_TOKEN`: the access token

The GitHub release uses the built-in `GITHUB_TOKEN` and needs no setup.

## Rolling back

PyPI never accepts the same version twice, so a broken release is fixed by a
new release:

1. On PyPI, yank the broken version (**Manage project → Releases → Options →
   Yank**). Installs that pin the exact version still resolve it; other
   installs skip it.
2. On Docker Hub, point `latest` back to the previous good version, or delete
   the broken tag.
3. Delete or edit the GitHub release.
4. Fix the problem, bump to the next patch version, and tag again.
