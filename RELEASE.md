# PyPI release checklist (v0.5.0)

**State: prepared, not published.** Do not dispatch the publish workflow until the account and trust relationship are ready. No API tokens belong in the repository.

## One-time setup (maintainer)

1. Create or sign into a PyPI account at https://pypi.org and enable two-factor authentication.
2. Check whether `open-seo-engine` is available as a PyPI project name. The GitHub repository name does not reserve the PyPI name. If already claimed, choose a new distribution name and update `pyproject.toml`, this checklist, and the workflow's release inputs before proceeding.
3. On GitHub, create an environment named **`pypi`** for `SunilTestLab/open-seo-engine`. Configure required reviewers for manual approval and restrict deployment branches to `main` (where available). Protect `main` with PR reviews and passing tests.
4. On PyPI, open **Account settings → Publishing → Add a new pending publisher** (for a first PyPI publication). Enter these **exact** values:

   - PyPI project name: `open-seo-engine`
   - GitHub owner: `SunilTestLab`
   - Repository name: `open-seo-engine`
   - Workflow filename: `publish-pypi.yml`
   - Environment name: `pypi`

   If the project already exists in your PyPI account, instead add the Trusted Publisher under its project's Publishing settings.
5. Confirm the pending publisher is present in PyPI before proceeding. The workflow uses short-lived GitHub OIDC credentials (not a long-lived `PYPI_API_TOKEN` secret).

## Verify before the first publication

Run locally from the repository root:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Verify the wheel and sdist contain `open_seo` source files, the MIT license, README and CLI entry point. Do not upload local `dist/` files; the workflow rebuilds them from reviewed `main`.

## First release — only after setup is complete

1. Merge the release-preparation changes to `main` and confirm CI passes.
2. Review `pyproject.toml` version `0.5.0` and the source in `main`.
3. In **Actions → Publish to PyPI (manual, approval required) → Run workflow**, select `main`, set **version** to `0.5.0`, and type **PUBLISH**.
4. Review the build job results and approve the protected **`pypi`** environment only if the publication is intended. Approval triggers an **irreversible public upload**.
5. Verify https://pypi.org/project/open-seo-engine/ and test installation from a fresh virtual environment.
6. Only after the successful publication, create a GitHub release/tag `v0.5.0` pointing to the same commit, with the release notes below.

## Draft v0.5.0 release notes

Initial public PyPI release of the standalone Open SEO Engine Python library: static-page SEO audit, bounded same-origin crawler with robots.txt and sitemap support, duplicate titles/descriptions and internal broken-link reports, JSON/CSV export, evidence-based SEO Glow-Up and AI Answerability Challenge, and optional multi-provider AI Brand Identity Crisis. This is experimental software and not a production-hardened multi-tenant crawler. API-provider calls are opt-in and can incur charges.

Shelfrank and Zapmetrics remain separate private products and are not part of this distribution.
