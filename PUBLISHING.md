# First PyPI release checklist

## Release state

`open-seo-engine` is **not automatically published** by pushes or tags. Only a
manual invocation of `.github/workflows/publish-pypi.yml` can publish it.

## One-time account setup (maintainer only)

1. In GitHub `SunilTestLab/open-seo-engine`, create environment **`pypi`** under
   Settings → Environments. Add required reviewers if your plan supports it.
2. Sign in to [PyPI](https://pypi.org/) with a verified account and 2FA.
3. If no PyPI project called `open-seo-engine` exists, open your account's
   **Publishing** page and create a **pending Trusted Publisher**:

   | Field | Exact value |
   | --- | --- |
   | PyPI project name | `open-seo-engine` |
   | GitHub owner | `SunilTestLab` |
   | GitHub repository | `open-seo-engine` |
   | Workflow filename | `publish-pypi.yml` |
   | GitHub environment | `pypi` |

   If the project already exists and you control it, add the same publisher
   under the project's Publishing settings instead. If someone else owns the
   name, stop and choose a different package name before any release.
4. Do **not** add PyPI API tokens to GitHub Secrets. OIDC from the workflow is
   used for publishing.
5. Review the released source and confirm the version is not already on PyPI.
   PyPI versions are immutable: do not attempt to replace the same version.

## Trigger the first release

Once the above is complete, go to GitHub Actions → **Publish to PyPI** →
**Run workflow** on the reviewed `main` commit. Wait for the build/tests and
`pypi` environment approval. Verify the published project on PyPI and install
it in a fresh virtual environment:

```bash
python -m pip install open-seo-engine==0.5.0
open-seo --help
```

## Security / scope

- The publish workflow only runs manually; clicking **Run workflow** is a real
  external publication, not a preview.
- The Python package is an experimental, command-line technical SEO toolkit.
  It is not yet a browser-based SaaS platform or a hardened multi-tenant crawler.
- GitHub Packages and PyPI are different registries. Publishing to PyPI does
  not populate GitHub Packages.
